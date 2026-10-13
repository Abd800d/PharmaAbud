"""AbdulmajeedPharma (APH) — FastAPI application entry point.

Swagger/OpenAPI docs: /docs  ·  ReDoc: /redoc  ·  Admin SPA: /admin
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import AphError
from app.core.logging import get_logger, setup_logging

_app_logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    _app_logger.info("Starting %s v%s (%s)", settings.app_name, settings.app_version, settings.environment)
    yield
    _app_logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AbdulmajeedPharma (APH) API",
        description=(
            "Professional Pharmaceutical Drug Encyclopedia & Intelligent Drug Database — "
            "موسوعة عبدالمجيد للأدوية.\n\n"
            "© Dr. Abdulmajeed Abdullah Almakhedhi\n\n"
            "**Medical disclaimer:** APH is intended for educational and professional reference "
            "purposes. It does not replace official prescribing information, clinical judgment, "
            "or advice from a qualified healthcare professional."
        ),
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AphError)
    async def aph_error_handler(_request: Request, exc: AphError):
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_request: Request, exc: Exception):
        # never expose raw stack traces to clients (§72)
        _app_logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "server_error", "message": "An internal error occurred.", "details": {}}},
        )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/", include_in_schema=False)
    def root_redirect():
        from fastapi.responses import RedirectResponse

        return RedirectResponse(url="/admin/")

    @app.get("/health", tags=["ops"])
    def health() -> dict:
        return {
            "status": "ok",
            "app": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
        }

    # --- Admin SPA (self-contained static dashboard served from /admin) ---
    admin_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "admin")
    if os.path.isdir(admin_dir):
        app.mount("/admin", StaticFiles(directory=admin_dir, html=True), name="admin")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
