"""Search endpoints (§9, §10, §18, §68, §75)."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import RecentSearch, SearchTermStat, utcnow
from app.schemas.search import BarcodeLookup, SearchQuery, SearchResponseOut, SuggestOut
from app.services.normalization import normalize_text
from app.services.ocr import match_candidates
from app.services.search import search as run_search, suggest

router = APIRouter(prefix="/search", tags=["search"])


def _track_query(db: Session, query: str, result_count: int, language: str = "en") -> None:
    """Privacy-conscious aggregate analytics only (§67)."""
    norm = normalize_text(query)
    if not norm:
        return
    stat = db.scalar(select(SearchTermStat).where(
        SearchTermStat.term_normalized == norm, SearchTermStat.language == language
    ))
    if stat is None:
        stat = SearchTermStat(term=query[:255], term_normalized=norm, language=language)
        db.add(stat)
    stat.hits = (stat.hits or 0) + 1
    if result_count == 0:
        stat.zero_results = (stat.zero_results or 0) + 1
    stat.last_seen_at = utcnow()
    db.flush()


@router.get("", response_model=SearchResponseOut)
def search_endpoint(
    q: str = Query("", max_length=255),
    kinds: str = Query("drug,product"),
    system_id: Optional[str] = None,
    therapeutic_group_id: Optional[str] = None,
    pharmacological_class_id: Optional[str] = None,
    dosage_form: Optional[str] = None,
    route: Optional[str] = None,
    manufacturer_id: Optional[str] = None,
    country_id: Optional[str] = None,
    verification_status: Optional[str] = None,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> SearchResponseOut:
    filters = {
        "system_id": system_id,
        "therapeutic_group_id": therapeutic_group_id,
        "pharmacological_class_id": pharmacological_class_id,
        "dosage_form": dosage_form,
        "route": route,
        "manufacturer_id": manufacturer_id,
        "country_id": country_id,
        "verification_status": verification_status,
    }
    filters = {k: v for k, v in filters.items() if v}
    resp = run_search(db, q, kinds=tuple(k.strip() for k in kinds.split(",") if k.strip()),
                      filters=filters, limit=limit, offset=offset)
    _track_query(db, q, resp.total)
    return SearchResponseOut(
        query=resp.query, total=resp.total, took_ms=resp.took_ms,
        suggestions=resp.suggestions,
        items=[{
            "kind": h.kind, "id": h.id, "name_en": h.name_en, "name_ar": h.name_ar,
            "subtitle": h.subtitle, "match_type": h.match_type, "score": h.score,
            "verification_status": h.verification_status, "is_demo": h.is_demo,
            "extra": h.extra,
        } for h in resp.items],
    )


@router.get("/suggest", response_model=SuggestOut)
def suggest_endpoint(q: str = Query("", max_length=120), db: Session = Depends(get_db)) -> SuggestOut:
    return SuggestOut(suggestions=suggest(db, q))


@router.post("/barcode", response_model=SearchResponseOut)
def barcode_lookup(payload: BarcodeLookup, db: Session = Depends(get_db)) -> SearchResponseOut:
    """Barcode → product. Unknown barcodes return empty results — never invented data (§18)."""
    resp = run_search(db, payload.barcode, kinds=("product",), limit=10)
    return SearchResponseOut(
        query=resp.query, total=resp.total, took_ms=resp.took_ms, suggestions=[],
        items=[{
            "kind": h.kind, "id": h.id, "name_en": h.name_en, "name_ar": h.name_ar,
            "subtitle": h.subtitle, "match_type": h.match_type, "score": h.score,
            "verification_status": h.verification_status, "is_demo": h.is_demo, "extra": h.extra,
        } for h in resp.items],
    )


@router.post("/ocr")
def ocr_search(text: str, db: Session = Depends(get_db)) -> dict:
    """OCR text → candidates → matches (§17). Confidence is always an estimate."""
    return match_candidates(db, text)
