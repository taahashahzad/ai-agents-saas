"""Environment-based configuration. No secrets are hard-coded anywhere."""
import os
from dataclasses import dataclass, field
from functools import lru_cache

from dotenv import load_dotenv

# Loads backend/.env for local development. Real environment variables win.
load_dotenv()


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _env(name: str) -> str | None:
    """Env var, trimmed (pasted secrets often carry a trailing newline/space); empty -> None."""
    value = os.getenv(name)
    value = value.strip() if value else None
    return value or None


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str
    cors_origins: list[str]
    firebase_credentials_path: str | None
    firebase_project_id: str | None
    check_token_revoked: bool
    log_level: str
    # Invitations are matched by email, so the email must be verified by Firebase.
    require_verified_email: bool = True
    invitation_ttl_days: int = 7
    # Phase 3: knowledge base files, stored in Cloudflare R2 (S3-compatible)
    max_upload_bytes: int = 10 * 1024 * 1024
    r2_account_id: str | None = None
    r2_access_key_id: str | None = field(default=None, repr=False)        # secret: never printed
    r2_secret_access_key: str | None = field(default=None, repr=False)    # secret: never printed
    r2_bucket_name: str | None = None
    r2_endpoint_url: str | None = None
    r2_region: str = "auto"
    openai_api_key: str | None = field(default=None, repr=False)
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4o-mini"
    qdrant_url: str | None = None
    qdrant_api_key: str | None = field(default=None, repr=False)
    qdrant_collection: str = "business_knowledge"
    rag_chunk_size: int = 1000
    rag_chunk_overlap: int = 150
    rag_top_k: int = 5
    rag_min_score: float = 0.2

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def r2_configured(self) -> bool:
        return all((self.r2_access_key_id, self.r2_secret_access_key, self.r2_bucket_name,
                    self.r2_endpoint_url))

    @property
    def rag_configured(self) -> bool:
        return bool(self.openai_api_key and self.qdrant_url)


@lru_cache
def get_settings() -> Settings:
    origins = _csv(os.getenv("CORS_ORIGINS", "http://localhost:5173,127.0.0.1:5173"))
    if "*" in origins:
        raise RuntimeError("CORS_ORIGINS must list explicit frontend origins; '*' is not allowed.")
    account_id = _env("R2_ACCOUNT_ID")
    endpoint = _env("R2_ENDPOINT_URL") or (
        f"https://{account_id}.r2.cloudflarestorage.com" if account_id else None)
    if endpoint and not endpoint.startswith("https://"):
        raise RuntimeError("R2_ENDPOINT_URL must start with https:// "
                           "(e.g. https://<ACCOUNT_ID>.r2.cloudflarestorage.com).")
    if endpoint:
        endpoint = endpoint.rstrip("/")
    qdrant_url = _env("QDRANT_URL")
    if qdrant_url and not qdrant_url.startswith(("https://", "http://")):
        raise RuntimeError("QDRANT_URL must start with https:// or http://.")
    embedding_model = _env("OPENAI_EMBEDDING_MODEL") or "text-embedding-3-small"
    if embedding_model not in {"text-embedding-3-small", "text-embedding-3-large"}:
        raise RuntimeError("OPENAI_EMBEDDING_MODEL must be text-embedding-3-small or text-embedding-3-large.")
    chunk_size = int(os.getenv("RAG_CHUNK_SIZE", "1000"))
    chunk_overlap = int(os.getenv("RAG_CHUNK_OVERLAP", "150"))
    if chunk_size < 1 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise RuntimeError("RAG_CHUNK_SIZE must be positive and RAG_CHUNK_OVERLAP must be smaller.")
    top_k = int(os.getenv("RAG_TOP_K", "5"))
    if not 1 <= top_k <= 20:
        raise RuntimeError("RAG_TOP_K must be between 1 and 20.")
    min_score = float(os.getenv("RAG_MIN_SCORE", "0.2"))
    if not 0 <= min_score <= 1:
        raise RuntimeError("RAG_MIN_SCORE must be between 0 and 1.")
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        cors_origins=origins,
        firebase_credentials_path=os.getenv("FIREBASE_CREDENTIALS_PATH") or None,
        firebase_project_id=os.getenv("FIREBASE_PROJECT_ID") or None,
        check_token_revoked=_bool(os.getenv("CHECK_TOKEN_REVOKED")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        require_verified_email=_bool(os.getenv("REQUIRE_VERIFIED_EMAIL"), default=True),
        invitation_ttl_days=max(1, int(os.getenv("INVITATION_TTL_DAYS", "7"))),
        # MAX_UPLOAD_MB is clamped to 1..50 MB because files are processed synchronously in memory.
        max_upload_bytes=int(min(50.0, max(1.0, float(os.getenv("MAX_UPLOAD_MB", "10")))) * 1024 * 1024),
        r2_account_id=account_id,
        r2_access_key_id=_env("R2_ACCESS_KEY_ID"),
        r2_secret_access_key=_env("R2_SECRET_ACCESS_KEY"),
        r2_bucket_name=_env("R2_BUCKET_NAME"),
        r2_endpoint_url=endpoint,
        r2_region=_env("R2_REGION") or "auto",
        openai_api_key=_env("OPENAI_API_KEY"),
        openai_embedding_model=embedding_model,
        openai_chat_model=_env("OPENAI_CHAT_MODEL") or "gpt-4o-mini",
        qdrant_url=qdrant_url,
        qdrant_api_key=_env("QDRANT_API_KEY"),
        qdrant_collection=_env("QDRANT_COLLECTION") or "business_knowledge",
        rag_chunk_size=chunk_size,
        rag_chunk_overlap=chunk_overlap,
        rag_top_k=top_k,
        rag_min_score=min_score,
    )
