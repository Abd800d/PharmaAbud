"""APH AI Assistant — Retrieval-Augmented Generation (§41–§43).

Pipeline:
  User Question → Intent Detection → APH Database Retrieval →
  Verified Source Retrieval → Context Construction → AI Response →
  Citations → Safety/Quality Layer

Ground rules enforced here:
  * Prefer verified APH data (§42).
  * Cite ONLY sources actually retrieved (§43).
  * Never fabricate dosage recommendations or drug facts (§42).
  * When the knowledge base lacks the answer, say so explicitly.
  * Always attach the medical disclaimer.

The default generator is fully extractive (offline): it composes answers
strictly from retrieved database content, so it cannot hallucinate facts
that were not retrieved. An OpenAI-compatible generator can be enabled via
configuration; it receives the same grounded context and safety wrapper.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models import (
    AiCitation,
    AiConversation,
    AiMessage,
    ContentSource,
    Drug,
    DrugSource,
    Product,
    Source,
)
from app.services.normalization import contains_arabic, normalize_text

DISCLAIMER_EN = (
    "APH is intended for educational and professional reference purposes. It does not replace "
    "official prescribing information, clinical judgment, or advice from a qualified healthcare "
    "professional. Always verify current official product information before making clinical decisions."
)
DISCLAIMER_AR = (
    "موسوعة عبدالمجيد للأدوية مخصصة للأغراض التعليمية والمرجعية المهنية فقط. لا تغني عن معلومات "
    "الوصفة الرسمية أو الحكم السريري أو استشارة مختص صحي مؤهل. تحقق دائماً من معلومات المنتج الرسمية "
    "الحديثة قبل اتخاذ قرارات سريرية."
)

UNAVAILABLE_EN = "The requested information could not be verified in the APH database."
UNAVAILABLE_AR = "تعذر التحقق من المطلوب في قاعدة بيانات موسوعة عبدالمجيد للأدوية."

# question intent -> monograph section names (as built by retrieval) to include
INTENT_SECTIONS: Dict[str, List[str]] = {
    "mechanism": ["mechanism", "pharmacodynamics"],
    "pharmacokinetics": ["pharmacokinetics"],
    "indications": ["indications"],
    "dosage": ["dosages"],
    "contraindications": ["contraindications"],
    "warnings": ["warnings", "precautions"],
    "side_effects": ["side_effects"],
    "interactions": ["interactions", "food_interactions"],
    "pregnancy": ["pregnancy"],
    "lactation": ["lactation"],
    "administration": ["administration"],
    "monitoring": ["monitoring"],
    "overdose": ["overdose"],
    "products": ["products"],
    "alternatives": ["alternatives"],
    "classification": ["classification"],
    "overview": ["overview", "mechanism", "classification", "indications"],
    "compare": ["overview", "mechanism", "indications", "products"],
}

INTENT_KEYWORDS: Dict[str, List[str]] = {
    "mechanism": ["mechanism", "action", "how does", "آلية", "العمل"],
    "pharmacokinetics": ["pharmacokinetic", "absorption", "metabolism", "half life", "kinetics"],
    "indications": ["indication", "used for", "uses", "treat", "استطباب", "الاستخدام", "يعالج"],
    "dosage": ["dose", "dosage", "dosing", "جرعة", "الجرعة"],
    "contraindications": ["contraindication", "should not", "موانع", "المحظورات"],
    "warnings": ["warning", "precaution", "تحذير", "احتياط"],
    "side_effects": ["side effect", "adverse", "adverse effect", "اثار جانبية", "أعراض جانبية"],
    "interactions": ["interaction", "interacts", "تداخل"],
    "pregnancy": ["pregnancy", "pregnant", "الحمل", "حامل"],
    "lactation": ["lactation", "breastfeeding", "nursing", "الرضاعة"],
    "administration": ["administration", "how to take", "طريقة الاستعمال"],
    "monitoring": ["monitor", "monitoring", "المتابعة"],
    "overdose": ["overdose", "toxicity", "جرعة زائدة"],
    "products": ["product", "brand", "commercial", "منتجات", "تجاري"],
    "alternatives": ["alternative", "equivalent", "substitute", "بدائل", "بديل"],
    "classification": ["class", "classification", "group", "تصنيف"],
    "overview": ["what is", "overview", "about", "ما هو", "تعريف"],
    "compare": ["compare", "versus", "vs", "difference", "قارن", "الفرق"],
}


@dataclass
class RetrievedSection:
    section: str
    text_en: str
    text_ar: str
    source_names: List[str] = field(default_factory=list)


@dataclass
class RetrievedEntity:
    entity_type: str            # drug | product
    entity_id: str
    label: str
    label_ar: str
    verification_status: str
    sections: List[RetrievedSection] = field(default_factory=list)
    sources: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class RagAnswer:
    answer: str
    answer_ar: str
    citations: List[Dict[str, Any]]
    disclaimer: str
    provider: str
    retrieved_entities: List[str]
    grounded: bool            # True when at least one fact was retrieved


def detect_intent(query: str) -> Tuple[str, List[str]]:
    """Return (intent, matched_keywords). Multiple intents default to first match."""
    q = normalize_text(query)
    best_intent, best_hits = "overview", []
    for intent, keywords in INTENT_KEYWORDS.items():
        hits = [k for k in keywords if normalize_text(k) in q]
        if len(hits) > len(best_hits):
            best_intent, best_hits = intent, hits
    return best_intent, best_hits


def retrieve_entities(db: Session, query: str, limit: int = 3) -> List[RetrievedEntity]:
    """Locate drugs/products the question is about, then pull their sections."""
    from app.services.search import search as apg_search

    resp = apg_search(db, query, kinds=("drug", "product"), limit=limit)
    entities: List[RetrievedEntity] = []
    for hit in resp.items[:limit]:
        if hit.kind == "drug":
            entities.append(_load_drug_context(db, hit.id))
        else:
            entities.append(_load_product_context(db, hit.id))
    return entities


def _load_drug_context(db: Session, drug_id: str) -> RetrievedEntity:
    drug = db.get(Drug, drug_id)
    if drug is None:
        return RetrievedEntity("drug", drug_id, "", "", "")
    sections = [
        RetrievedSection("overview", drug.overview_en, drug.overview_ar),
        RetrievedSection("mechanism", drug.mechanism_en or drug.pharmacodynamics_en, drug.mechanism_ar or drug.pharmacodynamics_ar),
        RetrievedSection("pharmacokinetics", drug.pharmacokinetics_en, drug.pharmacokinetics_ar),
        RetrievedSection("classification", _classification_line(drug), ""),
    ]
    sections.extend(_child_sections(db, drug))
    # commercial products of this drug (§11 equivalent products)
    product_lines_en = [
        f"{p.brand_name_en} ({p.strength} {p.dosage_form})"
        for p in db.scalars(select(Product).where(Product.drug_id == drug.id).limit(15)).all()
    ]
    if product_lines_en:
        sections.append(RetrievedSection("products", "; ".join(product_lines_en), ""))
    sources = _drug_sources(db, drug.id)
    return RetrievedEntity("drug", drug.id, drug.generic_name_en, drug.generic_name_ar,
                           drug.verification_status, sections, sources)


def _child_sections(db: Session, drug: Drug) -> List[RetrievedSection]:
    from app.models import (DrugAdministration, DrugContraindication, DrugDosage, DrugFoodInteraction,
                            DrugIndication, DrugInteraction, DrugLactation, DrugMonitoring,
                            DrugOverdose, DrugPregnancy, DrugPrecaution, DrugSideEffect, DrugWarning)

    out: List[RetrievedSection] = []

    def collect(model, section, en_attr="text_en", ar_attr="text_ar"):
        rows = db.scalars(select(model).where(model.drug_id == drug.id).limit(30)).all()
        if rows:
            en = "; ".join(getattr(r, en_attr) for r in rows if getattr(r, en_attr, ""))
            ar = "; ".join(getattr(r, ar_attr) for r in rows if getattr(r, ar_attr, ""))
            if en or ar:
                out.append(RetrievedSection(section, en, ar))

    collect(DrugIndication, "indications")
    collect(DrugContraindication, "contraindications")
    collect(DrugWarning, "warnings")
    collect(DrugPrecaution, "precautions")
    collect(DrugSideEffect, "side_effects")
    collect(DrugInteraction, "interactions")
    collect(DrugFoodInteraction, "food_interactions")
    collect(DrugMonitoring, "monitoring")

    doses = db.scalars(select(DrugDosage).where(DrugDosage.drug_id == drug.id).limit(20)).all()
    if doses:
        out.append(RetrievedSection(
            "dosages",
            " | ".join(f"{d.population}: {d.text_en}" for d in doses),
            " | ".join(f"{d.population}: {d.text_ar}" for d in doses),
        ))

    admins = db.scalars(select(DrugAdministration).where(DrugAdministration.drug_id == drug.id).limit(10)).all()
    if admins:
        out.append(RetrievedSection(
            "administration",
            "; ".join(a.text_en for a in admins if a.text_en),
            "; ".join(a.text_ar for a in admins if a.text_ar),
        ))

    preg = db.scalars(select(DrugPregnancy).where(DrugPregnancy.drug_id == drug.id).limit(1)).first()
    if preg:
        out.append(RetrievedSection("pregnancy", preg.text_en, preg.text_ar))
    lact = db.scalars(select(DrugLactation).where(DrugLactation.drug_id == drug.id).limit(1)).first()
    if lact:
        out.append(RetrievedSection("lactation", lact.text_en, lact.text_ar))
    od = db.scalars(select(DrugOverdose).where(DrugOverdose.drug_id == drug.id).limit(1)).first()
    if od:
        out.append(RetrievedSection("overdose", od.text_en, od.text_ar))
    return out


def _classification_line(drug: Drug) -> str:
    parts = [drug.drug_class, drug.pharmacological_class_name, drug.therapeutic_class_name, drug.atc_code]
    return " / ".join(p for p in parts if p)


def _drug_sources(db: Session, drug_id: str) -> List[Dict[str, str]]:
    links = db.scalars(select(DrugSource).where(DrugSource.drug_id == drug_id).limit(20)).all()
    out = []
    for link in links:
        src = db.get(Source, link.source_id)
        if src:
            out.append({
                "source_id": src.id, "name": src.name, "url": src.url,
                "section": link.section, "source_type": src.source_type,
                "last_verified": src.retrieved_date or "",
            })
    # field-level sources (§25)
    for cs in db.scalars(select(ContentSource).where(
        ContentSource.entity_type == "drug", ContentSource.entity_id == drug_id
    ).limit(20)).all():
        src = db.get(Source, cs.source_id)
        if src:
            out.append({
                "source_id": src.id, "name": src.name, "url": src.url,
                "section": cs.section, "source_type": src.source_type,
                "last_verified": src.retrieved_date or "",
            })
    # de-duplicate by (source_id, section)
    seen, unique = set(), []
    for s in out:
        key = (s["source_id"], s["section"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(s)
    return unique


def _load_product_context(db: Session, product_id: str) -> RetrievedEntity:
    product = db.get(Product, product_id)
    if product is None:
        return RetrievedEntity("product", product_id, "", "", "")
    ings = ", ".join(i.ingredient_name_en for i in product.ingredients) or "—"
    section = RetrievedSection(
        "products",
        f"{product.brand_name_en} — {product.strength} {product.dosage_form}; "
        f"active ingredient(s): {ings}; route: {product.route or '—'}",
        f"{product.brand_name_ar or product.brand_name_en} — {product.strength} {product.dosage_form}",
    )
    sources = []
    if product.drug_id:
        sources = _drug_sources(db, product.drug_id)
    return RetrievedEntity("product", product.id, product.brand_name_en, product.brand_name_ar,
                           product.verification_status, [section], sources)


def build_context(entities: Sequence[RetrievedEntity], intent: str, max_chars: int) -> str:
    wanted = INTENT_SECTIONS.get(intent, INTENT_SECTIONS["overview"])
    blocks: List[str] = []
    for ent in entities:
        header = f"### {ent.label} ({ent.label_ar}) [{ent.entity_type}; verification: {ent.verification_status}]"
        body_parts = []
        for sec in ent.sections:
            if sec.section in wanted or intent in ("compare", "overview"):
                text = sec.text_en or sec.text_ar
                if text:
                    body_parts.append(f"[{sec.section}] {text}")
        if body_parts:
            blocks.append(header + "\n" + "\n".join(body_parts))
    context = "\n\n".join(blocks)
    return context[:max_chars]


# ---------------------------------------------------------------- generators
class ExtractiveGenerator:
    """Default provider: composes an answer strictly from retrieved sections."""

    name = "extractive"

    def generate(self, question: str, intent: str, entities: Sequence[RetrievedEntity], language: str) -> Tuple[str, str, bool]:
        grounded = False
        en_parts: List[str] = []
        ar_parts: List[str] = []
        for ent in entities:
            en_parts.append(f"**{ent.label}**" + (f" ({ent.label_ar})" if ent.label_ar else ""))
            ar_parts.append(f"**{ent.label_ar or ent.label}**")
            for sec in ent.sections:
                if intent != "compare" and sec.section not in INTENT_SECTIONS.get(intent, []):
                    continue
                if sec.text_en:
                    en_parts.append(f"- {sec.section.replace('_', ' ').title()}: {sec.text_en}")
                    grounded = True
                if sec.text_ar:
                    ar_parts.append(f"- {sec.text_ar}")
        if not grounded:
            return UNAVAILABLE_EN, UNAVAILABLE_AR, False
        answer_en = "\n".join(en_parts)
        answer_ar = "\n".join(ar_parts) if ar_parts else answer_en
        return answer_en, answer_ar, True


class OpenAICompatibleGenerator:
    """Optional external LLM behind the same grounded-context contract."""

    name = "openai_compatible"

    def generate(self, question: str, intent: str, entities: Sequence[RetrievedEntity], language: str) -> Tuple[str, str, bool]:
        import json
        import urllib.request

        settings = get_settings()
        context = build_context(entities, intent, settings.ai_max_context_chars)
        if not context.strip():
            return UNAVAILABLE_EN, UNAVAILABLE_AR, False
        prompt = (
            "You are the APH pharmaceutical assistant. Answer ONLY from the provided context. "
            "If the context lacks the answer, reply exactly: " + UNAVAILABLE_EN + "\n\n"
            f"CONTEXT:\n{context}\n\nQUESTION: {question}"
        )
        req = urllib.request.Request(
            settings.ai_openai_base_url.rstrip("/") + "/chat/completions",
            data=json.dumps({
                "model": settings.ai_openai_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            }).encode(),
            headers={"Authorization": f"Bearer {settings.ai_openai_api_key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode())
            text = payload["choices"][0]["message"]["content"]
            grounded = UNAVAILABLE_EN not in text
            return text, text, grounded
        except Exception:
            return UNAVAILABLE_EN, UNAVAILABLE_AR, False


def _get_generator():
    settings = get_settings()
    if settings.ai_provider == "openai_compatible" and settings.ai_openai_api_key:
        return OpenAICompatibleGenerator()
    return ExtractiveGenerator()


def ask(
    db: Session,
    question: str,
    *,
    user_id: Optional[str] = None,
    device_id: str = "",
    language: str = "en",
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    question = (question or "").strip()
    if not question:
        return {"answer": "Please provide a question.", "citations": [], "disclaimer": DISCLAIMER_EN}
    if contains_arabic(question):
        language = "ar"

    intent, _keywords = detect_intent(question)
    entities = retrieve_entities(db, question)

    generator = _get_generator()
    answer_en, answer_ar, grounded = generator.generate(question, intent, entities, language)

    # --- citations: ONLY from actually retrieved sources (§43) ---
    citations: List[Dict[str, Any]] = []
    seen = set()
    for ent in entities:
        for src in ent.sources:
            key = (src.get("source_id"), src.get("section"))
            if key in seen:
                continue
            seen.add(key)
            citations.append({
                "source_id": src.get("source_id", ""),
                "source_name": src.get("name", ""),
                "source_url": src.get("url", ""),
                "section": src.get("section", ""),
                "entity_type": ent.entity_type,
                "entity_id": ent.entity_id,
                "last_verified_date": src.get("last_verified", ""),
            })

    if not grounded:
        answer_en = UNAVAILABLE_EN
        answer_ar = UNAVAILABLE_AR

    disclaimer = DISCLAIMER_AR if language == "ar" else DISCLAIMER_EN
    final_answer = answer_ar if language == "ar" else answer_en

    # --- persist conversation / message / citations ---
    conv = None
    if conversation_id:
        conv = db.get(AiConversation, conversation_id)
    if conv is None:
        conv = AiConversation(user_id=user_id, device_id=device_id, language=language,
                              title=question[:120])
        db.add(conv)
        db.flush()

    msg = AiMessage(
        conversation_id=conv.id,
        role="assistant",
        content=final_answer,
        language=language,
        provider=generator.name,
        safety_note=disclaimer,
    )
    db.add(msg)
    db.flush()
    for cit in citations:
        db.add(AiCitation(
            message_id=msg.id,
            source_id=cit.get("source_id") or None,
            source_name=cit.get("source_name", ""),
            source_url=cit.get("source_url", ""),
            section=cit.get("section", ""),
            entity_type=cit.get("entity_type", ""),
            entity_id=cit.get("entity_id", ""),
        ))
    db.add(AiMessage(conversation_id=conv.id, role="user", content=question, language=language))

    return {
        "conversation_id": conv.id,
        "message_id": msg.id,
        "answer": final_answer,
        "answer_en": answer_en,
        "answer_ar": answer_ar,
        "citations": citations,
        "disclaimer": disclaimer,
        "provider": generator.name,
        "intent": intent,
        "retrieved_entities": [f"{e.entity_type}:{e.entity_id}" for e in entities],
        "grounded": grounded,
    }
