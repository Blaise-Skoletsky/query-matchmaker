import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends

logger = logging.getLogger(__name__)
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.query import Query
from app.services.auth import get_current_user
from app.services.embedding import embed_async
from app.services.llm import converse, extract_metadata, _synthesize_summary, MAX_CLARIFICATIONS
from app.services.matching import run_matching_pipeline, run_reverse_matching

router = APIRouter(prefix="/api/conversation", tags=["conversation"])


class ConversationRequest(BaseModel):
    history: list[dict]


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
            await run_reverse_matching(db, query)


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
    except Exception as e:
        logger.exception("converse() failed: %s", e)
        if user_msg_count >= MAX_CLARIFICATIONS:
            summary = await _synthesize_summary(body.history)
            result = {"action": "submit", "summary": summary}
        else:
            return ConversationResponse(
                action="ask",
                message="Sorry, I had trouble understanding that. Could you rephrase?",
            )

    if result.get("action") == "submit":
        summary = result.get("summary", body.history[-1].get("content", ""))

        embedding_vec = await embed_async(summary)
        try:
            metadata = await extract_metadata(summary)
        except Exception:
            metadata = {}

        query = Query(
            user_id=user.id,
            raw_text=summary,
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
