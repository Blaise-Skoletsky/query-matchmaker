import uuid

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.query import Query
from app.services.auth import get_current_user
from app.services.embedding import embed_async
from app.services.llm import converse, extract_metadata
from app.services.matching import run_matching_pipeline

router = APIRouter(prefix="/api/conversation", tags=["conversation"])


class ConversationRequest(BaseModel):
    history: list[dict]
    location: str | None = None
    budget: str | None = None
    condition: str | None = None
    urgency: str | None = None


class ConversationResponse(BaseModel):
    action: str
    message: str | None = None
    query_id: str | None = None


async def _run_matching_bg(query_id: uuid.UUID):
    from app.database import async_session
    async with async_session() as db:
        query = await db.get(Query, query_id)
        if query:
            await run_matching_pipeline(db, query)


@router.post("", response_model=ConversationResponse)
async def chat_turn(
    body: ConversationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    user_msg_count = sum(1 for m in body.history if m["role"] == "user")

    try:
        result = await converse(body.history)
    except Exception:
        # If user has answered a clarification, submit anyway instead of asking again
        if user_msg_count >= 2:
            summary = "\n".join(m["content"] for m in body.history if m["role"] == "user")
            result = {"action": "submit", "summary": summary}
        else:
            return ConversationResponse(
                action="ask",
                message="Sorry, I had trouble understanding that. Could you rephrase?",
            )

    if result.get("action") == "submit":
        summary = result.get("summary", body.history[-1].get("content", ""))

        # Enrich summary with context panel details
        context_parts = []
        if body.location:
            context_parts.append(f"Location: {body.location}")
        if body.budget:
            context_parts.append(f"Budget/Price: {body.budget}")
        if body.condition:
            context_parts.append(f"Condition: {body.condition}")
        if body.urgency:
            context_parts.append(f"Urgency: {body.urgency}")
        if context_parts:
            summary = summary + "\n" + ". ".join(context_parts) + "."

        embedding_vec = await embed_async(summary)
        try:
            metadata = await extract_metadata(summary)
        except Exception:
            metadata = {}

        query = Query(
            user_id=user.id,
            raw_text=summary,
            location=body.location,
            intent=metadata.get("intent"),
            category=metadata.get("category"),
            attributes=metadata.get("attributes"),
            complementary_intents=metadata.get("complementary_intents"),
            required_match_attributes=metadata.get("required_match_attributes"),
            preferred_match_attributes=metadata.get("preferred_match_attributes"),
            embedding=embedding_vec,
            group_size=2,
        )
        db.add(query)
        await db.commit()
        await db.refresh(query)

        background_tasks.add_task(_run_matching_bg, query.id)

        return ConversationResponse(
            action="submitted",
            message=f"Query submitted: \"{summary}\". I'm now looking for matches...",
            query_id=str(query.id),
        )

    return ConversationResponse(
        action="ask",
        message=result.get("message", "Could you tell me more about what you're looking for?"),
    )
