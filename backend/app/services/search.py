"""APH pharmaceutical search engine (§9, §10, §83).

Ranking (descending):
  1. Exact generic match      2. Exact active-ingredient match
  3. Exact brand match        4. Exact Arabic match
  5. Synonym match            6. Prefix match
  7. Partial match            8. Fuzzy (typo-tolerant) match
Barcode / registration-number lookups are treated as exact identifiers.

Implementation: indexed SQL candidate retrieval + deterministic Python
re-ranking. This works on PostgreSQL and SQLite; PostgreSQL deployments
additionally get pg_trgm/tsvector indexes (see alembic migration) so the
candidate phase stays fast at 500k+ products. The client API contract is
independent of the underlying search technology (future OpenSearch swap).
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    BodySystem,
    Drug,
    DrugClassification,
    DrugSynonym,
    Manufacturer,
    Product,
    ProductIngredient,
    TherapeuticGroup,
)
from app.services.normalization import contains_arabic, name_key, normalize_arabic, normalize_text

# match-type -> base score
SCORE_EXACT_GENERIC = 100.0
SCORE_EXACT_INGREDIENT = 90.0
SCORE_EXACT_BRAND = 85.0
SCORE_EXACT_ARABIC = 80.0
SCORE_SYNONYM = 70.0
SCORE_PREFIX = 60.0
SCORE_PARTIAL = 40.0
SCORE_FUZZY = 20.0
SCORE_BARCODE = 110.0

FUZZY_THRESHOLD = 0.72
CANDIDATE_LIMIT = 400

# words too generic to drive SQL candidate retrieval (search intent words)
_STOPWORDS = {
    "what", "which", "how", "does", "do", "is", "are", "the", "of", "for", "and",
    "or", "to", "in", "on", "a", "an", "me", "my", "tell", "about", "with", "use",
    "used", "treat", "treatment", "drug", "drugs", "medicine", "product", "products",
    "brand", "generic", "dose", "dosing", "dosage", "effect", "effects", "side",
    "interaction", "interactions", "indication", "indications",
    "ما", "هو", "هي", "عن", "ال", "في", "من", "على", "إلى",
}


def _query_tokens(query_norm: str) -> List[str]:
    """Most informative tokens first: longer, non-stopword terms drive retrieval."""
    tokens = [t for t in query_norm.split() if t]
    informative = [t for t in tokens if t not in _STOPWORDS and len(t) >= 3]
    informative.sort(key=len, reverse=True)
    return (informative or tokens)[:4]


@dataclass
class SearchHit:
    kind: str                  # "drug" | "product"
    id: str
    name_en: str
    name_ar: str
    subtitle: str              # class / strength+form / manufacturer
    match_type: str
    score: float
    verification_status: str
    is_demo: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResponse:
    query: str
    total: int
    items: List[SearchHit]
    took_ms: int = 0
    suggestions: List[str] = field(default_factory=list)


def _ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _score_text(query_norm: str, query_key: str, candidates: Sequence[tuple[str, float]]) -> tuple[str, float]:
    """Score query against (value, base_score) candidates; return best (match_type, score).

    Both the full query and its individual tokens are scored, so long natural
    questions ("What is the mechanism of action of enalapril?") still produce
    an exact generic match on the entity token.
    """
    query_variants: List[tuple[str, str]] = [(query_norm, query_key)]
    for token in query_norm.split():
        if len(token) >= 3 and token != query_norm:
            query_variants.append((token, token))

    best_type, best_score = "", 0.0
    for value, base in candidates:
        v_norm = normalize_text(value)
        if not v_norm:
            continue
        v_key = name_key(value)
        for qn, qk in query_variants:
            if qn == v_norm or qk == v_key:
                s = base
                mtype = _match_label(base)
            elif v_norm.startswith(qn) or v_key.startswith(qk):
                s = SCORE_PREFIX + base * 0.1
                mtype = "prefix"
            elif qn in v_norm or qk in v_key:
                s = SCORE_PARTIAL + base * 0.1
                mtype = "partial"
            else:
                r = max(_ratio(qk, v_key), _ratio(qn, v_norm))
                if r < FUZZY_THRESHOLD:
                    continue
                s = SCORE_FUZZY + r * 10
                mtype = "fuzzy"
            if s > best_score:
                best_type, best_score = mtype, s
    return best_type, best_score


def _match_label(base: float) -> str:
    return {
        SCORE_EXACT_GENERIC: "exact_generic",
        SCORE_EXACT_INGREDIENT: "exact_ingredient",
        SCORE_EXACT_BRAND: "exact_brand",
        SCORE_EXACT_ARABIC: "exact_arabic",
        SCORE_SYNONYM: "exact_synonym",
    }.get(base, "exact")


def _fuzzy_label(base: float, score: float) -> str:
    if score >= SCORE_PREFIX:
        return "prefix"
    if score >= SCORE_PARTIAL:
        return "partial"
    return "fuzzy"


def build_drug_search_fields(db: Session, drug: Drug) -> None:
    """Maintain denormalized search_text columns on write."""
    parts_en = [drug.generic_name_en, drug.scientific_name, drug.drug_class,
                drug.pharmacological_class_name, drug.therapeutic_class_name, drug.atc_code]
    parts_ar = [drug.generic_name_ar]
    for syn in drug.synonyms:
        (parts_ar if syn.language == "ar" else parts_en).append(syn.term)
    drug.search_text = " ".join(normalize_text(p) for p in parts_en if p)
    drug.search_text_ar = " ".join(normalize_arabic(p) for p in parts_ar if p)


def build_product_search_fields(product: Product) -> None:
    parts = [product.brand_name_en, product.brand_name_ar, product.strength,
             product.dosage_form, product.barcode, product.registration_number]
    for ing in product.ingredients:
        parts.append(ing.ingredient_name_en)
        parts.append(ing.ingredient_name_ar)
    if product.manufacturer is not None:
        parts.append(product.manufacturer.name_en)
    product.search_text = " ".join(normalize_text(p) for p in parts if p)


def _drug_candidates(db: Session, query_norm: str, query_ar: bool, filters: Dict[str, Any]) -> List[Drug]:
    stmt: Select = select(Drug).options(
        selectinload(Drug.synonyms),
        selectinload(Drug.classifications),
        selectinload(Drug.products).selectinload(Product.manufacturer),
    )
    conds = []
    for t in _query_tokens(query_norm):
        like = f"%{t}%"
        prefix = f"{t[:4]}%" if len(t) >= 4 else f"{t}%"
        conds.append(or_(
            Drug.search_text.like(like),
            Drug.search_text.like(prefix),  # typo/prefix fallback for fuzzy candidates
            Drug.search_text_ar.like(like),
            Drug.generic_name_en.ilike(like),
            Drug.generic_name_ar.ilike(like),
            Drug.atc_code.ilike(like),
        ))
    if not conds:
        conds.append(Drug.id == Drug.id)  # no-op: browse mode
    stmt = stmt.where(or_(*conds))
    stmt = _apply_drug_filters(stmt, filters)
    stmt = stmt.limit(CANDIDATE_LIMIT)
    return list(db.scalars(stmt).all())


def _product_candidates(db: Session, query_norm: str, filters: Dict[str, Any]) -> List[Product]:
    stmt: Select = select(Product).options(
        selectinload(Product.ingredients),
        selectinload(Product.manufacturer),
        selectinload(Product.drug),
    )
    conds = []
    for t in _query_tokens(query_norm):
        like = f"%{t}%"
        prefix = f"{t[:4]}%" if len(t) >= 4 else f"{t}%"
        conds.append(or_(
            Product.search_text.like(like),
            Product.search_text.like(prefix),
            Product.brand_name_en.ilike(like),
            Product.brand_name_ar.ilike(like),
            Product.barcode.ilike(like),
            Product.registration_number.ilike(like),
        ))
    if not conds:
        conds.append(Product.id == Product.id)
    stmt = stmt.where(or_(*conds))
    stmt = _apply_product_filters(stmt, filters)
    stmt = stmt.limit(CANDIDATE_LIMIT)
    return list(db.scalars(stmt).all())


def _apply_drug_filters(stmt: Select, filters: Dict[str, Any]) -> Select:
    if filters.get("verification_status"):
        stmt = stmt.where(Drug.verification_status == filters["verification_status"])
    if filters.get("system_id"):
        stmt = stmt.where(
            Drug.id.in_(select(DrugClassification.drug_id).where(DrugClassification.body_system_id == filters["system_id"]))
        )
    if filters.get("therapeutic_group_id"):
        stmt = stmt.where(
            Drug.id.in_(select(DrugClassification.drug_id).where(
                DrugClassification.therapeutic_group_id == filters["therapeutic_group_id"]))
        )
    if filters.get("pharmacological_class_id"):
        stmt = stmt.where(
            Drug.id.in_(select(DrugClassification.drug_id).where(
                DrugClassification.pharmacological_class_id == filters["pharmacological_class_id"]))
        )
    return stmt


def _apply_product_filters(stmt: Select, filters: Dict[str, Any]) -> Select:
    if filters.get("dosage_form"):
        stmt = stmt.where(Product.dosage_form == filters["dosage_form"])
    if filters.get("route"):
        stmt = stmt.where(Product.route == filters["route"])
    if filters.get("manufacturer_id"):
        stmt = stmt.where(Product.manufacturer_id == filters["manufacturer_id"])
    if filters.get("country_id"):
        stmt = stmt.where(or_(
            Product.manufacturer_country_id == filters["country_id"],
            Product.marketing_country_id == filters["country_id"],
        ))
    if filters.get("verification_status"):
        stmt = stmt.where(Product.verification_status == filters["verification_status"])
    return stmt


def search(
    db: Session,
    query: str,
    *,
    kinds: Sequence[str] = ("drug", "product"),
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 25,
    offset: int = 0,
) -> SearchResponse:
    import time

    started = time.perf_counter()
    filters = filters or {}
    q = (query or "").strip()
    query_norm = normalize_text(q)
    query_ar = contains_arabic(q)
    query_key = name_key(q)

    if not q:
        return SearchResponse(query=q, total=0, items=[])

    hits: List[SearchHit] = []

    # ---- identifier shortcuts (barcode / registration number) ----
    if re.fullmatch(r"[0-9\-\s]{8,20}", q):
        for p in db.scalars(select(Product).where(or_(Product.barcode == q.replace(" ", ""), Product.gtin == q.replace(" ", ""))).limit(5)).all():
            hits.append(SearchHit(
                kind="product", id=p.id, name_en=p.brand_name_en, name_ar=p.brand_name_ar,
                subtitle=f"{p.strength} {p.dosage_form}".strip(),
                match_type="barcode", score=SCORE_BARCODE,
                verification_status=p.verification_status, is_demo=p.is_demo,
                extra={"barcode": p.barcode, "drug_id": p.drug_id},
            ))

    # ---- drugs ----
    if "drug" in kinds:
        for drug in _drug_candidates(db, query_norm, query_ar, filters):
            candidates: list[tuple[str, float]] = [
                (drug.generic_name_en, SCORE_EXACT_GENERIC),
                (drug.scientific_name, SCORE_EXACT_GENERIC * 0.95),
                (drug.generic_name_ar, SCORE_EXACT_ARABIC),
            ]
            for ing in db.scalars(select(ProductIngredient).where(ProductIngredient.drug_id == drug.id).limit(20)).all():
                candidates.append((ing.ingredient_name_en, SCORE_EXACT_INGREDIENT))
            for syn in drug.synonyms:
                candidates.append((syn.term, SCORE_SYNONYM))
            mtype, score = _score_text(query_norm, query_key, candidates)
            if score <= 0:
                continue
            hits.append(SearchHit(
                kind="drug", id=drug.id, name_en=drug.generic_name_en, name_ar=drug.generic_name_ar,
                subtitle=drug.pharmacological_class_name or drug.therapeutic_class_name or drug.drug_class,
                match_type=mtype, score=score,
                verification_status=drug.verification_status, is_demo=drug.is_demo,
                extra={"atc_code": drug.atc_code, "systems": [c.body_system_id for c in drug.classifications]},
            ))

    # ---- products ----
    if "product" in kinds:
        for product in _product_candidates(db, query_norm, filters):
            candidates = [
                (product.brand_name_en, SCORE_EXACT_BRAND),
                (product.brand_name_ar, SCORE_EXACT_ARABIC),
                (product.brand_name_en + " " + product.strength, SCORE_EXACT_BRAND * 0.9),
            ]
            for ing in product.ingredients:
                candidates.append((ing.ingredient_name_en, SCORE_EXACT_INGREDIENT))
            if product.manufacturer is not None:
                candidates.append((product.manufacturer.name_en, SCORE_PARTIAL))
            # identifiers win outright — they are not fuzzy-matched
            raw_id = q.replace(" ", "")
            if product.barcode and (raw_id == product.barcode or query_norm == normalize_text(product.barcode)):
                mtype, score = "barcode", SCORE_BARCODE
            elif product.gtin and raw_id == product.gtin:
                mtype, score = "barcode", SCORE_BARCODE
            elif product.registration_number and query_norm == normalize_text(product.registration_number):
                mtype, score = "registration_number", SCORE_BARCODE * 0.9
            else:
                mtype, score = _score_text(query_norm, query_key, candidates)
            if score <= 0:
                continue
            hits.append(SearchHit(
                kind="product", id=product.id, name_en=product.brand_name_en, name_ar=product.brand_name_ar,
                subtitle=f"{product.strength} {product.dosage_form} — {product.manufacturer.name_en if product.manufacturer else ''}".strip(" —"),
                match_type=mtype, score=score,
                verification_status=product.verification_status, is_demo=product.is_demo,
                extra={"drug_id": product.drug_id, "barcode": product.barcode},
            ))

    # de-duplicate, sort by score then name
    seen: set[tuple[str, str]] = set()
    unique: List[SearchHit] = []
    for h in sorted(hits, key=lambda x: (-x.score, x.name_en.lower())):
        key = (h.kind, h.id)
        if key in seen:
            continue
        seen.add(key)
        unique.append(h)

    total = len(unique)
    page = unique[offset: offset + limit]
    suggestions = _suggestions(db, query_norm) if total == 0 else []
    took = int((time.perf_counter() - started) * 1000)
    return SearchResponse(query=q, total=total, items=page, took_ms=took, suggestions=suggestions)


def _suggestions(db: Session, query_norm: str, limit: int = 5) -> List[str]:
    """Spelling suggestions when nothing matched (typo correction aid)."""
    if len(query_norm) < 3:
        return []
    out: List[tuple[float, str]] = []
    for d in db.scalars(select(Drug.generic_name_en).limit(2000)).all():
        r = _ratio(query_norm, normalize_text(d))
        if r >= 0.55:
            out.append((r, d))
    for p in db.scalars(select(Product.brand_name_en).limit(2000)).all():
        r = _ratio(query_norm, normalize_text(p))
        if r >= 0.55:
            out.append((r, p))
    out.sort(key=lambda x: -x[0])
    seen: set[str] = set()
    result: List[str] = []
    for _, name in out:
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        result.append(name)
        if len(result) >= limit:
            break
    return result


def suggest(db: Session, prefix: str, limit: int = 8) -> List[Dict[str, str]]:
    """Instant-search suggestions (prefix based)."""
    p = (prefix or "").strip()
    if not p:
        return []
    norm = normalize_text(p)
    like = f"{norm}%"
    out: List[Dict[str, str]] = []
    for d in db.scalars(
        select(Drug).where(or_(Drug.generic_name_en.ilike(f"{p}%"), Drug.search_text.like(like))).limit(limit)
    ).all():
        out.append({"kind": "drug", "id": d.id, "text": d.generic_name_en, "text_ar": d.generic_name_ar})
    for prod in db.scalars(
        select(Product).where(or_(Product.brand_name_en.ilike(f"{p}%"), Product.search_text.like(like))).limit(limit)
    ).all():
        out.append({"kind": "product", "id": prod.id, "text": prod.brand_name_en, "text_ar": prod.brand_name_ar})
    return out[: limit * 2]


def equivalent_products(
    db: Session,
    drug_id: str,
    *,
    strength: Optional[str] = None,
    dosage_form: Optional[str] = None,
    route: Optional[str] = None,
) -> List[Product]:
    """Pharmaceutical equivalents: same active ingredient (the drug), optionally
    matching strength / dosage form / route. Labelled 'Equivalent Product' —
    NEVER 'therapeutic alternative' (§11)."""
    stmt = select(Product).options(selectinload(Product.manufacturer), selectinload(Product.ingredients)).where(
        Product.drug_id == drug_id, Product.status == "active"
    )
    if strength:
        stmt = stmt.where(Product.strength == strength)
    if dosage_form:
        stmt = stmt.where(Product.dosage_form == dosage_form)
    if route:
        stmt = stmt.where(Product.route == route)
    return list(db.scalars(stmt).all())
