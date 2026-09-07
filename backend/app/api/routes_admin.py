"""
Admin API.
Restricted exclusively to Role.ADMINISTRATOR.
Exposes:
- User management (list, add, modify)
- Roles & permissions inspector
- Knowledge base management (list documents, upload, delete, reindex)
- System configuration (LLM, vector store, rate limits)
- System and audit logs
"""
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.app.auth.models import (
    Permission,
    ROLE_PERMISSIONS,
    Role,
    User,
    get_all_users,
    get_roles_permissions_matrix,
)
from backend.app.auth.rbac import require_permission
from backend.app.auth.security import add_or_update_user, get_current_user, require_role
from backend.app.config import get_settings
from backend.app.logging_config import get_audit_logs, get_logger, log_event
from backend.app.retrieval.document_loader import delete_document, list_documents, save_document
from backend.app.retrieval.hybrid_search import HybridRetriever

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_role([Role.ADMINISTRATOR]))],
)
logger = get_logger("api.admin")


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: Role
    department: str = "general"


class UploadDocumentRequest(BaseModel):
    content: str
    title: str
    department: str = "general"
    document_type: str = "incident"
    access_level: str = "internal"  # internal, restricted, confidential
    created_date: str = "2025-01-01"


class ConfigUpdateRequest(BaseModel):
    llm_temperature: float | None = None
    rate_limit_capacity: int | None = None
    rate_limit_refill_rate: float | None = None


# --- 👥 Manage Users ---
@router.get("/users")
async def list_all_users(admin: User = Depends(get_current_user)):
    return {"users": get_all_users()}


@router.post("/users")
async def create_or_update_user(payload: CreateUserRequest, admin: User = Depends(get_current_user)):
    created = add_or_update_user(
        username=payload.username,
        password=payload.password,
        role=payload.role,
        department=payload.department,
    )
    log_event(
        logger,
        "user_created_or_updated",
        admin=admin.username,
        target_user=created.username,
        target_role=created.role.value,
    )
    return {"status": "success", "user": {"username": created.username, "role": created.role.value, "department": created.department}}


# --- 🔐 Manage Roles / Permissions ---
@router.get("/roles")
async def list_roles_and_permissions(admin: User = Depends(get_current_user)):
    return {
        "matrix": get_roles_permissions_matrix(),
        "all_permissions": [p.value for p in Permission],
        "all_roles": [r.value for r in Role],
    }


# --- 📚 Manage Knowledge Base, Upload & Delete ---
@router.get("/documents")
async def get_documents_catalog(admin: User = Depends(get_current_user)):
    retriever = HybridRetriever.instance()
    docs = list_documents()
    return {
        "documents": docs,
        "total_documents": len(docs),
        "total_chunks": len(retriever.chunks),
    }


@router.post("/documents/upload")
async def upload_document(payload: UploadDocumentRequest, admin: User = Depends(get_current_user)):
    if payload.access_level not in {"internal", "restricted", "confidential"}:
        raise HTTPException(status_code=400, detail="access_level must be internal, restricted, or confidential")

    doc_id = save_document(
        content=payload.content,
        title=payload.title,
        department=payload.department,
        document_type=payload.document_type,
        access_level=payload.access_level,
        created_date=payload.created_date,
    )
    retriever = HybridRetriever.instance()
    total_chunks = retriever.reindex()

    log_event(
        logger,
        "document_uploaded",
        admin=admin.username,
        doc_id=doc_id,
        total_chunks=total_chunks,
    )
    return {"status": "success", "doc_id": doc_id, "total_chunks": total_chunks}


@router.delete("/documents/{doc_id}")
async def remove_document(doc_id: str, admin: User = Depends(get_current_user)):
    deleted = delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")

    retriever = HybridRetriever.instance()
    total_chunks = retriever.reindex()

    log_event(logger, "document_deleted", admin=admin.username, doc_id=doc_id)
    return {"status": "deleted", "doc_id": doc_id, "total_chunks": total_chunks}


@router.post("/reindex")
async def trigger_reindex(admin: User = Depends(get_current_user)):
    require_permission(admin.role, "admin_reindex")
    retriever = HybridRetriever.instance()
    chunks_count = retriever.reindex()
    log_event(logger, "admin_reindex_executed", admin=admin.username, chunks=chunks_count)
    return {"status": "reindexed", "total_chunks": chunks_count}


# --- ⚙️ System Configuration ---
@router.get("/config")
async def get_system_config(admin: User = Depends(get_current_user)):
    settings = get_settings()
    return {
        "llm_provider": settings.llm_provider,
        "groq_model": settings.groq_model,
        "openai_model": settings.openai_model,
        "anthropic_model": settings.anthropic_model,
        "temperature": settings.temperature,
        "pinecone_active": bool(settings.pinecone_api_key),
        "pinecone_index": settings.pinecone_index_name,
        "rate_limit_capacity": settings.rate_limit_capacity,
        "rate_limit_refill_rate": settings.rate_limit_refill_rate,
        "jwt_expire_minutes": settings.jwt_expire_minutes,
        "langchain_tracing": bool(settings.langchain_tracing_v2),
    }


@router.post("/config")
async def update_system_config(payload: ConfigUpdateRequest, admin: User = Depends(get_current_user)):
    settings = get_settings()
    if payload.llm_temperature is not None:
        settings.temperature = max(0.0, min(1.0, payload.llm_temperature))
    if payload.rate_limit_capacity is not None:
        settings.rate_limit_capacity = max(1, payload.rate_limit_capacity)
    if payload.rate_limit_refill_rate is not None:
        settings.rate_limit_refill_rate = max(0.1, payload.rate_limit_refill_rate)

    log_event(
        logger,
        "system_config_updated",
        admin=admin.username,
        temperature=settings.temperature,
        capacity=settings.rate_limit_capacity,
    )
    return {
        "status": "updated",
        "temperature": settings.temperature,
        "rate_limit_capacity": settings.rate_limit_capacity,
        "rate_limit_refill_rate": settings.rate_limit_refill_rate,
    }


# --- 📋 View System / Audit Logs ---
@router.get("/logs")
async def fetch_audit_logs(limit: int = 100, admin: User = Depends(get_current_user)):
    logs = get_audit_logs(limit=limit)
    return {"logs": logs, "count": len(logs)}
