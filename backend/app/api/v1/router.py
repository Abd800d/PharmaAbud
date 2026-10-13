"""API v1 router aggregation."""
from fastapi import APIRouter

from app.api.v1 import admin, ai, auth, drugs, images, imports, products, search, sync, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(drugs.router)
api_router.include_router(products.router)

from app.api.v1 import taxonomy  # noqa: E402

api_router.include_router(taxonomy.router)
api_router.include_router(search.router)
api_router.include_router(imports.router)
api_router.include_router(images.router)
api_router.include_router(users.users_router)
api_router.include_router(users.requests_router)
api_router.include_router(users.audit_router)
api_router.include_router(sync.router)
api_router.include_router(ai.router)
api_router.include_router(admin.router)
