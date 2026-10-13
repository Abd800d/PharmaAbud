"""API v1 router — /api/v1 prefix, versioned, per-module tags."""
from fastapi import APIRouter

from app.api.v1 import (
    admin,
    ai,
    audit_logs,
    auth,
    compare,
    drugs,
    favorites,
    images,
    imports,
    monograph,
    products,
    reports,
    search,
    sync,
    taxonomy,
    translations,
    users,
)

api_router = APIRouter()
# NOTE: `compare` must be included BEFORE `drugs` so that /drugs/compare is not
# swallowed by the /drugs/{drug_id} path parameter route.
api_router.include_router(compare.router)
api_router.include_router(auth.router)
api_router.include_router(drugs.router)
api_router.include_router(monograph.router)
api_router.include_router(translations.router)
api_router.include_router(favorites.router)
api_router.include_router(products.router)
api_router.include_router(taxonomy.router)
api_router.include_router(search.router)
api_router.include_router(imports.router)
api_router.include_router(images.router)
api_router.include_router(users.users_router)
api_router.include_router(users.requests_router)
api_router.include_router(sync.router)
api_router.include_router(ai.router)
api_router.include_router(admin.router)
api_router.include_router(reports.router)
api_router.include_router(audit_logs.router)
