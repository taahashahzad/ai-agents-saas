import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import agents, businesses, conversations, documents, health, invitations, knowledge, members, rag, users
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.limits import UploadSizeLimitMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level.upper())

    app = FastAPI(
        title="AI Agent SaaS - Backend API",
        version="1.0.0",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    app.state.settings = settings

    # Added BEFORE CORS so CORS wraps it (413 responses still carry CORS headers).
    app.add_middleware(UploadSizeLimitMiddleware, max_bytes=settings.max_upload_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,  # Bearer tokens are sent in a header, not cookies
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )
    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(users.router, prefix="/api/v1")
    app.include_router(businesses.router, prefix="/api/v1")
    app.include_router(members.router, prefix="/api/v1")
    app.include_router(invitations.business_router, prefix="/api/v1")
    app.include_router(invitations.router, prefix="/api/v1")
    app.include_router(documents.router, prefix="/api/v1")
    app.include_router(knowledge.router, prefix="/api/v1")
    app.include_router(rag.router, prefix="/api/v1")
    app.include_router(agents.router, prefix="/api/v1")
    app.include_router(conversations.router, prefix="/api/v1")
    return app


app = create_app()
