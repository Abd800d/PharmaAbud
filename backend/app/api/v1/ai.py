"""APH AI Assistant endpoints (§41–§43)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_optional_user, rate_limit
from app.db.session import get_db
from app.models import AiConversation, User
from app.schemas.ai import AiAskRequest, AiAskResponse
from app.services.rag import DISCLAIMER_AR, DISCLAIMER_EN, ask

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/ask", response_model=AiAskResponse, dependencies=[Depends(rate_limit())])
def ai_ask(payload: AiAskRequest, db: Session = Depends(get_db),
           user: User | None = Depends(get_optional_user)) -> AiAskResponse:
    result = ask(
        db,
        payload.question,
        user_id=user.id if user else None,
        device_id=payload.device_id,
        language=payload.language,
        conversation_id=payload.conversation_id,
    )
    return AiAskResponse(
        conversation_id=result["conversation_id"],
        message_id=result["message_id"],
        answer=result["answer"],
        citations=result["citations"],
        disclaimer=result["disclaimer"],
        provider=result["provider"],
        intent=result.get("intent", ""),
        retrieved_entities=result.get("retrieved_entities", []),
        grounded=result.get("grounded", False),
    )


@router.get("/conversations", response_model=dict)
def list_conversations(db: Session = Depends(get_db),
                       user: User | None = Depends(get_optional_user)) -> dict:
    stmt = select(AiConversation).order_by(AiConversation.created_at.desc()).limit(50)
    if user:
        stmt = stmt.where(AiConversation.user_id == user.id)
    rows = db.scalars(stmt).all()
    return {
        "items": [{
            "id": c.id, "title": c.title, "language": c.language,
            "created_at": c.created_at.isoformat(),
        } for c in rows],
        "disclaimer": DISCLAIMER_EN,
        "disclaimer_ar": DISCLAIMER_AR,
    }
