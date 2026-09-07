"""
Central application configuration.

All environment-driven settings live here so every module imports
one source of truth instead of scattering os.getenv() calls.
"""
from functools import lru_cache
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

# Explicitly load into os.environ for libraries (LangChain/LangSmith, etc.)
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(ENV_PATH), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-6"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    groq_api_key: str = ""

    # Vector DB
    pinecone_api_key: str = ""
    pinecone_environment: str = "us-east-1"
    pinecone_index_name: str = "enterprise-kb"

    # LangSmith
    langchain_tracing_v2: bool = True
    langchain_api_key: str = ""
    langchain_project: str = "enterprise-ai-assistant"

    # Security
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 120

    # Rate limiting
    rate_limit_capacity: int = 20
    rate_limit_refill_per_sec: float = 0.5

    # MCP
    mcp_server_url: str = "http://localhost:8100"

    # App
    backend_url: str = "http://localhost:8000"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
