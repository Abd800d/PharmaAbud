"""OCR-ready drug/package identification pipeline (§17).

Flow (architecture is complete; the OCR provider is pluggable):
  Camera image → preprocessing → OCR text extraction → candidate
  extraction → APH database matching → ranked candidates + confidence.

Confidence is ALWAYS shown as an estimate; recognition is never claimed
to be certain, and manual correction is always possible (§17).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from sqlalchemy.orm import Session

from app.services.search import SearchHit, search


@dataclass
class OcrCandidate:
    brand: str = ""
    generic: str = ""
    strength: str = ""
    dosage_form: str = ""
    manufacturer: str = ""
    confidence: float = 0.0
    raw_text: str = ""
    matched: List[Dict[str, Any]] = field(default_factory=list)


class OcrProvider(Protocol):
    def extract_text(self, image_bytes: bytes) -> str: ...


class ManualTextProvider:
    """Default provider: accepts text extracted on-device (or typed by the user).

    The mobile client may run on-device OCR (e.g. Google ML Kit) and submit
    the extracted text here — no image ever leaves the device unnecessarily.
    """

    def extract_text(self, image_bytes: bytes) -> str:
        return image_bytes.decode("utf-8", errors="replace") if isinstance(image_bytes, (bytes, bytearray)) else str(image_bytes)


_STRENGTH_RE = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*(mg|mcg|g|ml|iu|%)\b", re.IGNORECASE)
_FORM_KEYWORDS = {
    "tablet": "tablet", "tab": "tablet", "capsule": "capsule", "cap": "capsule",
    "syrup": "syrup", "suspension": "oral_suspension", "injection": "injection",
    "cream": "cream", "ointment": "ointment", "drops": "eye_drops", "spray": "nasal_spray",
    "inhaler": "inhaler",
}


def extract_candidates(text: str) -> OcrCandidate:
    """Parse candidate fields out of raw OCR text — guesses are labelled, not asserted."""
    cand = OcrCandidate(raw_text=text or "")
    clean = re.sub(r"\s+", " ", text or "")

    m = _STRENGTH_RE.search(clean)
    if m:
        cand.strength = f"{m.group(1)} {m.group(2).lower()}"
        cand.confidence += 0.2

    for word, form in _FORM_KEYWORDS.items():
        if re.search(rf"\b{word}\b", clean, re.IGNORECASE):
            cand.dosage_form = form
            cand.confidence += 0.1
            break

    # candidate "words" for name matching: longest tokens first
    tokens = [t for t in re.split(r"[^A-Za-z0-9\u0600-\u06FF\-/]+", clean) if len(t) >= 4]
    if tokens:
        cand.brand = tokens[0]
        cand.confidence += 0.1
    cand.confidence = min(cand.confidence, 0.9)  # never claim certainty
    return cand


def match_candidates(db: Session, text: str, limit: int = 5) -> Dict[str, Any]:
    """Full pipeline: OCR text → parsed candidates → APH database matches."""
    cand = extract_candidates(text)
    query = " ".join(x for x in [cand.brand, cand.strength, cand.dosage_form] if x) or (text or "")[:80]
    resp = search(db, query, limit=limit)
    matches = [
        {
            "kind": h.kind,
            "id": h.id,
            "name_en": h.name_en,
            "name_ar": h.name_ar,
            "subtitle": h.subtitle,
            "match_type": h.match_type,
            "score": round(h.score, 1),
            "verification_status": h.verification_status,
        }
        for h in resp.items
    ]
    cand.matched = matches
    return {
        "candidates": {
            "brand": cand.brand,
            "generic": cand.generic,
            "strength": cand.strength,
            "dosage_form": cand.dosage_form,
            "manufacturer": cand.manufacturer,
            "confidence": round(cand.confidence, 2),
        },
        "matches": matches,
        "note": "OCR results are estimates and may be incorrect. Please review and correct manually.",
    }
