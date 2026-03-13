import json
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
from app.services.tools import execute_tool, check_user_queries

router = APIRouter(prefix="/api/conversation", tags=["conversation"])

MAX_TOOL_CALLS = 3


class ConversationRequest(BaseModel):
    history: list[dict]


class ConversationResponse(BaseModel):
    action: str
    message: str | None = None
    query_id: str | None = None
    tools_used: list[dict] | None = None


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
    history = list(body.history)
    tools_used: list[dict] = []

    # ReAct loop: let the LLM call tools, then continue conversation
    just_called_tool = False

    for _ in range(MAX_TOOL_CALLS + 1):
        try:
            result = await converse(history)
        except Exception as e:
            logger.exception("converse() failed: %s", e)
            if user_msg_count >= MAX_CLARIFICATIONS:
                summary = await _synthesize_summary(history)
                result = {"action": "submit", "summary": summary}
            else:
                return ConversationResponse(
                    action="ask",
                    message="Sorry, I had trouble understanding that. Could you rephrase?",
                    tools_used=tools_used or None,
                )

        # Structural guardrail: block submit right after tool call
        if just_called_tool and result.get("action") == "submit":
            result = {
                "action": "ask",
                "message": result.get("summary", "Based on what I found, could you confirm the details?"),
            }
            just_called_tool = False
            break

        just_called_tool = False

        if result.get("action") != "tool_call":
            break

        # Execute the tool
        tool_name = result.get("tool", "")
        tool_args = result.get("args", {})
        tool_result = await execute_tool(db, user.id, tool_name, tool_args)

        tools_used.append({
            "tool": tool_name,
            "args": tool_args,
            "result": tool_result,
        })

        # Append tool interaction to history in Ollama's expected format
        history.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": tool_name, "arguments": tool_args}}],
        })
        history.append({"role": "tool", "content": tool_result})
        history.append({
            "role": "system",
            "content": (
                "You just called a tool and received results above. "
                "You MUST now respond with an ASK action that naturally shares "
                "these findings with the user. Do NOT submit yet."
            ),
        })
        just_called_tool = True

    if result.get("action") == "submit":
        summary = result.get("summary", history[-1].get("content", ""))

        # Duplicate check: warn if user already has a similar active query
        # Skip if we already warned (assistant's previous message contains the warning)
        already_warned = any(
            m.get("role") == "assistant" and "similar active query" in (m.get("content") or "")
            for m in history
        )
        if not already_warned:
            existing = await check_user_queries(db, user.id)
            if "no active queries" not in existing.lower():
                summary_lower = summary.lower()
                summary_intent = "sell" if "sell" in summary_lower else "buy" if "buy" in summary_lower else None
                summary_words = {w.lower() for w in summary.split() if len(w) >= 3}
                for line in existing.split("\n"):
                    if "]" not in line:
                        continue
                    # Extract intent from "[buy]" or "[sell]" tag
                    bracket_content = line.split("[", 1)[-1].split("]", 1)[0].strip().lower() if "[" in line else ""
                    # Only flag if intents match (buy-buy or sell-sell)
                    if summary_intent and bracket_content and summary_intent != bracket_content:
                        continue
                    query_text = line.split("]", 1)[-1].strip().lower()
                    overlap = sum(1 for w in summary_words if w in query_text)
                    if overlap >= 3:
                        return ConversationResponse(
                            action="ask",
                            message=(
                                f"You already have a similar active query: {line.strip()}. "
                                "Would you like to continue and create a new one anyway?"
                            ),
                            tools_used=tools_used or None,
                        )

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
            tools_used=tools_used or None,
        )

    return ConversationResponse(
        action="ask",
        message=result.get("message", "Could you tell me more about what you're looking for?"),
        tools_used=tools_used or None,
    )
