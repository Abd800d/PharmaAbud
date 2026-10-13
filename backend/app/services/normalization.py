"""Data normalization utilities (§22).

Normalizes drug names, Arabic text, strengths, units, dosage forms,
routes, countries and manufacturers while preserving original values
on the import rows.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional, Tuple

# ------------------------------------------------------------------ Arabic
_ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06DC\u06DF-\u06E8\u06EA-\u06ED]")
_TATWEEL = "\u0640"


def normalize_arabic(text: str) -> str:
    """Normalize common Arabic orthographic variations for indexing/search.

    - strips harakat (diacritics) and tatweel
    - unifies alef variants (أ إ آ ٱ) -> ا
    - ى -> ي , ة -> ه , ؤ -> و , ئ -> ي
    - removes punctuation, collapses whitespace
    """
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = _ARABIC_DIACRITICS.sub("", t)
    t = t.replace(_TATWEEL, "")
    t = t.replace("\u0622", "\u0627").replace("\u0623", "\u0627").replace("\u0625", "\u0627").replace("\u0671", "\u0627")
    t = t.replace("\u0649", "\u064A").replace("\u0629", "\u0647")
    t = t.replace("\u0624", "\u0648").replace("\u0626", "\u064A")
    t = re.sub(r"[^\w\s\u0600-\u06FF]", " ", t)
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t


def contains_arabic(text: str) -> bool:
    return bool(re.search(r"[\u0600-\u06FF]", text or ""))


# ------------------------------------------------------------------ generic text
def normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace (both scripts)."""
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    if contains_arabic(t):
        t = normalize_arabic(t)
    else:
        t = t.lower()
        t = re.sub(r"[^a-z0-9\s\-\+/]", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
    return t


def name_key(text: str) -> str:
    """Comparison key: removes spaces/hyphens so 'amox-cillin' == 'amoxcillin'."""
    return re.sub(r"[\s\-_/\.]", "", normalize_text(text))


# ------------------------------------------------------------------ strengths
_UNIT_ALIASES = {
    "mg": "mg", "milligram": "mg", "milligrams": "mg", "ملجم": "mg", "مليغرام": "mg",
    "g": "g", "gm": "g", "gram": "g", "grams": "g", "غرام": "g",
    "mcg": "mcg", "µg": "mcg", "ug": "mcg", "microgram": "mcg", "micrograms": "mcg",
    "ml": "ml", "mL": "ml", "milliliter": "ml", "milliliters": "ml",
    "l": "l", "liter": "l", "liters": "l",
    "iu": "iu", "unit": "iu", "units": "iu", "وحدة": "iu",
    "%": "%", "percent": "%",
    "meq": "meq", "mEq": "meq",
    "mmol": "mmol",
    "units/ml": "units/ml",
}

# canonical conversions to a base unit where safe
_TO_MG = {"g": 1000.0, "mg": 1.0, "mcg": 0.001}
_TO_ML = {"l": 1000.0, "ml": 1.0}

_STRENGTH_RE = re.compile(
    r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*([a-zA-Zµ%/\u0600-\u06FF]+)?\s*$"
)


@dataclass
class NormalizedStrength:
    original: str
    value: Optional[float]
    unit: str
    canonical_mg: Optional[float]  # normalized to mg when possible
    canonical_ml: Optional[float]  # normalized to ml when possible
    valid: bool


def normalize_strength(raw: str) -> NormalizedStrength:
    """Normalize '500 mg', '500MG', '0.5 g' -> value=500, unit=mg, canonical_mg=500.

    Preserves the original string; invalid/unknown formats are flagged, not guessed.
    """
    original = raw or ""
    cleaned = original.strip().replace(",", ".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return NormalizedStrength(original, None, "", None, None, False)

    m = _STRENGTH_RE.match(cleaned)
    if not m:
        # try splitting compound strengths like "500mg/5ml"
        return NormalizedStrength(original, None, "", None, None, False)

    value = float(m.group(1))
    unit_raw = (m.group(2) or "").strip()
    unit = _UNIT_ALIASES.get(unit_raw, _UNIT_ALIASES.get(unit_raw.lower(), unit_raw.lower()))

    canonical_mg = None
    canonical_ml = None
    if unit in _TO_MG:
        canonical_mg = value * _TO_MG[unit]
    if unit in _TO_ML:
        canonical_ml = value * _TO_ML[unit]

    valid = bool(unit)
    return NormalizedStrength(original, value, unit, canonical_mg, canonical_ml, valid)


def parse_strength_field(raw: str) -> Tuple[str, str, str]:
    """Return (strength_display, strength_value, strength_unit)."""
    ns = normalize_strength(raw)
    if not ns.valid:
        return raw.strip(), "", ""
    return raw.strip(), _fmt(ns.value), ns.unit


def _fmt(v: Optional[float]) -> str:
    if v is None:
        return ""
    if float(v).is_integer():
        return str(int(v))
    return str(v)


# ------------------------------------------------------------------ taxonomy aliases
DOSAGE_FORM_ALIASES = {
    "tab": "tablet", "tabs": "tablet", "tablets": "tablet", "tablet": "tablet", "قرص": "tablet", "أقراص": "tablet", "اقراص": "tablet",
    "cap": "capsule", "caps": "capsule", "capsule": "capsule", "capsules": "capsule", "كبسولة": "capsule", "كبسولات": "capsule",
    "softgel": "softgel", "soft gelatin capsule": "softgel",
    "oral solution": "oral_solution", "solution": "oral_solution", "oral liquid": "oral_solution", "شراب": "oral_solution",
    "oral suspension": "oral_suspension", "suspension": "oral_suspension", "susp": "oral_suspension", "معلق": "oral_suspension",
    "syrup": "syrup", "شراب مركز": "syrup",
    "powder": "powder", "pwd": "powder", "مسحوق": "powder",
    "granules": "granules", "granule": "granules",
    "injection": "injection", "inj": "injection", "ampoule": "injection", "amp": "injection", "حقن": "injection",
    "infusion": "infusion", "iv infusion": "infusion", "محاليل وريدية": "infusion",
    "cream": "cream", "creme": "cream", "كريم": "cream",
    "ointment": "ointment", "oint": "ointment", "مرهم": "ointment",
    "gel": "gel", "جل": "gel",
    "lotion": "lotion", "لوشن": "lotion",
    "foam": "foam",
    "patch": "patch", "transdermal patch": "transdermal_system", "لاصقة": "patch",
    "suppository": "suppository", "supp": "suppository", "تحاميل": "suppository",
    "vaginal tablet": "vaginal_tablet", "pessary": "vaginal_tablet",
    "vaginal cream": "vaginal_cream",
    "eye drops": "eye_drops", "ophthalmic drops": "eye_drops", "قطرات عين": "eye_drops",
    "eye ointment": "eye_ointment", "ophthalmic ointment": "eye_ointment",
    "ear drops": "ear_drops", "otic drops": "ear_drops", "قطرات اذن": "ear_drops",
    "nasal spray": "nasal_spray", "spray": "nasal_spray", "بخاخ": "nasal_spray",
    "inhaler": "inhaler", "mdi": "inhaler", "dihaler": "inhaler", "بخاخ استنشاقي": "inhaler",
    "nebulizer solution": "nebulizer_solution", "nebules": "nebulizer_solution",
    "mouthwash": "mouthwash", " gargle": "mouthwash",
    "sublingual tablet": "sublingual_tablet", "sl": "sublingual_tablet",
    "buccal tablet": "buccal_tablet",
    "transdermal system": "transdermal_system", "tds": "transdermal_system",
    "implant": "implant",
    "other": "other",
}

ROUTE_ALIASES = {
    "oral": "oral", "po": "oral", "by mouth": "oral", "عن طريق الفم": "oral", "فموي": "oral",
    "iv": "intravenous", "intravenous": "intravenous", "وريدي": "intravenous",
    "im": "intramuscular", "intramuscular": "intramuscular", "عضلي": "intramuscular",
    "sc": "subcutaneous", "subcutaneous": "subcutaneous", "subcut": "subcutaneous", "تحت الجلد": "subcutaneous",
    "topical": "topical", "mucosal": "topical", "موضعي": "topical",
    "inhalation": "inhalation", "inhal": "inhalation", "respiratory (inhalation)": "inhalation",
    "ophthalmic": "ophthalmic", "eye": "ophthalmic",
    "otic": "otic", "ear": "otic",
    "nasal": "nasal", "intranasal": "nasal",
    "rectal": "rectal", "pr": "rectal",
    "vaginal": "vaginal",
    "transdermal": "transdermal",
    "sublingual": "sublingual",
    "buccal": "buccal",
    "intrathecal": "intrathecal",
    "epidural": "epidural",
    "other": "other",
}

COUNTRY_ALIASES = {
    "sa": "SA", "ksa": "SA", "saudi arabia": "SA", "saudi": "SA", "السعودية": "SA", "المملكة العربية السعودية": "SA",
    "ae": "AE", "uae": "AE", "united arab emirates": "AE", "الإمارات": "AE", "الامارات": "AE",
    "eg": "EG", "egypt": "EG", "مصر": "EG",
    "us": "US", "usa": "US", "united states": "US", "america": "US",
    "uk": "GB", "gb": "GB", "united kingdom": "GB", "britain": "GB",
    "de": "DE", "germany": "DE", "المانيا": "DE", "ألمانيا": "DE",
    "in": "IN", "india": "IN", "الهند": "IN",
    "jo": "JO", "jordan": "JO", "الاردن": "JO", "الأردن": "JO",
    "kw": "KW", "kuwait": "KW", "الكويت": "KW",
    "qa": "QA", "qatar": "QA", "قطر": "QA",
    "bh": "BH", "bahrain": "BH", "البحرين": "BH",
    "om": "OM", "oman": "OM", "عمان": "OM",
    "tr": "TR", "turkey": "TR", "تركيا": "TR",
    "fr": "FR", "france": "FR", "فرنسا": "FR",
    "ch": "CH", "switzerland": "CH",
    "jp": "JP", "japan": "JP",
    "cn": "CN", "china": "CN",
}


def normalize_dosage_form(raw: str) -> str:
    key = normalize_text(raw)
    return DOSAGE_FORM_ALIASES.get(key, DOSAGE_FORM_ALIASES.get(key.replace("_", " "), key.replace(" ", "_") if key else ""))


def normalize_route(raw: str) -> str:
    key = normalize_text(raw)
    return ROUTE_ALIASES.get(key, key.replace(" ", "_") if key else "")


def normalize_country(raw: str) -> str:
    key = normalize_text(raw)
    return COUNTRY_ALIASES.get(key, (raw or "").strip().upper())


def normalize_manufacturer(raw: str) -> str:
    t = re.sub(r"\b(ltd|llc|inc|corp|co|gmbh|s\.a\.|s\.p\.a|pharma|pharmaceuticals|pharmaceutical|labs|laboratories)\b",
               " ", normalize_text(raw))
    return re.sub(r"\s+", " ", t).strip()
