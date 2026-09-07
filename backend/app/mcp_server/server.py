"""
Dummy MCP-style server exposing mock enterprise data:
employee directory, service catalog, incident records.

This is a simplified HTTP stand-in for a real MCP server (per the
spec: "not a high priority requirement" / can be simplified). It runs
as its own FastAPI process so it demonstrates the pattern of an agent
calling out to an *external* enterprise system rather than the
document knowledge base.
"""
from fastapi import FastAPI, Query

app = FastAPI(title="Dummy MCP Server")

EMPLOYEES = [
    {"id": "E001", "name": "Priya Fernando", "role": "Payments Engineer", "department": "payments"},
    {"id": "E002", "name": "Kasun Perera", "role": "SRE Lead", "department": "platform"},
    {"id": "E003", "name": "Amaya Silva", "role": "Compliance Officer", "department": "risk"},
]

SERVICES = [
    {"service_id": "SVC-PAY-01", "name": "Payment Gateway", "owner": "payments", "tier": "critical"},
    {"service_id": "SVC-AUTH-01", "name": "Auth Service", "owner": "platform", "tier": "critical"},
    {"service_id": "SVC-NOTIF-01", "name": "Notification Service", "owner": "platform", "tier": "standard"},
]

INCIDENTS = [
    {"incident_id": "INC-1042", "service_id": "SVC-PAY-01", "severity": "SEV1", "status": "resolved", "date": "2025-03-14"},
    {"incident_id": "INC-1077", "service_id": "SVC-PAY-01", "severity": "SEV2", "status": "resolved", "date": "2025-06-02"},
    {"incident_id": "INC-1090", "service_id": "SVC-AUTH-01", "severity": "SEV3", "status": "resolved", "date": "2025-07-20"},
]


def _filter(records: list[dict], q: str) -> list[dict]:
    if not q:
        return records
    q_lower = q.lower()
    return [r for r in records if any(q_lower in str(v).lower() for v in r.values())]


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/mcp/employees")
async def employees(q: str = Query(default="")):
    return {"resource": "employees", "results": _filter(EMPLOYEES, q)}


@app.get("/mcp/services")
async def services(q: str = Query(default="")):
    return {"resource": "services", "results": _filter(SERVICES, q)}


@app.get("/mcp/incidents")
async def incidents(q: str = Query(default="")):
    return {"resource": "incidents", "results": _filter(INCIDENTS, q)}
