import json
import logging

import httpx

from app.config import settings
from app.services.tools import get_ollama_tools

logger = logging.getLogger(__name__)


async def _chat(messages: list[dict], max_tokens: int = 1024, temperature: float = 0) -> str:
    """Send a chat request to Ollama and return the assistant message content.

    Args:
        messages: List of message dicts with "role" and "content" (e.g. user/assistant).
        max_tokens: Maximum tokens for the model to generate.
        temperature: Sampling temperature (0 = deterministic; use 0 for structured outputs).

    Returns:
        The assistant reply text from the model.

    Raises:
        httpx.HTTPStatusError: If the Ollama API returns a non-2xx status.
    """
    msg = await _chat_with_tools(messages, tools=None, max_tokens=max_tokens, temperature=temperature)
    return msg.get("content", "")


async def _chat_with_tools(
    messages: list[dict],
    tools: list[dict] | None = None,
    max_tokens: int = 1024,
    temperature: float = 0.3,
) -> dict:
    """Send a chat request to Ollama with optional tool definitions.

    Args:
        messages: List of message dicts (system/user/assistant/tool).
        tools: Optional list of tool definitions (Ollama function-calling format).
        max_tokens: Maximum tokens to generate.
        temperature: Sampling temperature (0.0–1.0).

    Returns:
        The full message dict from the API, including "content" and optionally
        "tool_calls" if the model requested a tool invocation.

    Raises:
        httpx.HTTPStatusError: If the Ollama API returns a non-2xx status.
    """
    payload = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": temperature},
    }
    if tools:
        payload["tools"] = tools
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json=payload,
        )
        response.raise_for_status()
        return response.json()["message"]


def _parse_json(text: str):
    """Extract and parse a single JSON object or array from free-form text.

    Handles markdown code blocks (```json ... ```) and raw text containing
    JSON. Uses the first valid outermost { } or [ ] structure found.

    Args:
        text: Raw string that may contain JSON (possibly inside markdown).

    Returns:
        Parsed JSON as a dict or list.

    Raises:
        json.JSONDecodeError: If no valid JSON is found in the text.
    """
    text = text.strip()
    # Extract JSON from markdown code blocks anywhere in the response
    if "```" in text:
        parts = text.split("```")
        for i in range(1, len(parts), 2):
            block = parts[i]
            # Strip optional language tag (e.g. ```json)
            if block.startswith(("json", "JSON")):
                block = block.split("\n", 1)[1] if "\n" in block else block[4:]
            block = block.strip()
            if block:
                return json.loads(block)
    # Find the outermost JSON structure (whichever of { or [ appears first)
    obj_start = text.find("{")
    arr_start = text.find("[")
    candidates = []
    if obj_start != -1:
        candidates.append((obj_start, "{", "}"))
    if arr_start != -1:
        candidates.append((arr_start, "[", "]"))
    candidates.sort(key=lambda x: x[0])
    for _, start_char, end_char in candidates:
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    return json.loads(text)


COMPLEMENTARY_INTENTS = {"buy": ["sell"], "sell": ["buy"]}


async def extract_metadata(raw_text: str) -> dict:
    """Extract structured metadata from a raw user query using the LLM.

    Args:
        raw_text: The user's free-form query (e.g. "I want to buy a red bike").

    Returns:
        Dict with keys: intent, category, attributes, complementary_intents,
        required_match_attributes, preferred_match_attributes. complementary_intents
        is overridden from COMPLEMENTARY_INTENTS (not LLM output).
    """
    prompt = f"""Analyze this user query and extract structured metadata. Return ONLY valid JSON, no other text.

Query: "{raw_text}"

Return JSON with these fields:
- "intent": one of [buy, sell]
- "category": a short category label (e.g. "vehicles", "electronics", "sports", "software_engineering")
- "attributes": object with key attributes extracted from the query (e.g. {{"color": "white", "make": "Toyota"}})
- "complementary_intents": list of intents that would match this query (e.g. a "buy" query matches ["sell"])
- "required_match_attributes": list of attribute keys that MUST match for a good match
- "preferred_match_attributes": list of attribute keys that are nice-to-have"""

    result = _parse_json(await _chat([{"role": "user", "content": prompt}]))

    # Hardcode complementary intents — LLM is unreliable for this
    result["complementary_intents"] = COMPLEMENTARY_INTENTS.get(result.get("intent"), [])

    return result


MAX_CLARIFICATIONS = 5  # safety cap only; LLM decides when it's ready


async def synthesize_summary(history: list[dict]) -> str:
    """Summarize a conversation into one sentence describing the user's buy/sell intent.

    Args:
        history: List of message dicts with "role" and "content".

    Returns:
        A single-sentence summary (item, attributes, intent); excludes tool results
        and advice. Stripped of leading/trailing whitespace.
    """
    prompt = (
        "Summarize this marketplace query conversation into one clear, specific sentence "
        "that captures ONLY what the user wants to buy or sell — the item, its attributes, "
        "and their intent. Do NOT include tool results, marketplace observations, pricing data, "
        "or any advice/guidance context. Return ONLY the summary sentence.\n\nConversation:\n"
        + "\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in history
        )
    )
    return (await _chat([{"role": "user", "content": prompt}], max_tokens=256)).strip()


async def converse(history: list[dict]) -> dict:
    """Run one turn of the buy/sell query-building conversation with optional tools.

    The agent may ask a question, submit a final query, or request a tool call.
    After MAX_CLARIFICATIONS user messages, submission is forced.

    The LLM is sent: (1) a system prompt (role, rules, tool descriptions, output format),
    (2) the conversation history. When the previous turn was a tool call, history
    includes an assistant message with tool_calls and a tool message with the result
    (see example below).

    Args:
        history: Conversation so far; list of dicts with "role" and "content"
            (and "tool_calls" / tool results if applicable).

    Returns:
        One of:
        - {"action": "ask", "message": str}
        - {"action": "submit", "summary": str}
        - {"action": "tool_call", "tool": str, "args": dict}

    Example messages sent to the LLM (after one tool call and result):
        [
          {"role": "system", "content": "<long system prompt with rules and tool descriptions>"},
          {"role": "user", "content": "I want to sell my laptop"},
          {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "get_price_range", "arguments": {"category": "electronics", "keywords": "laptop"}}}]},
          {"role": "tool", "content": "Found 8 similar listing(s). Price range: $400–$1,200. Most common: ~$800."},
          {"role": "system", "content": "You just called a tool... You MUST now respond with an ASK action..."}
        ]
    """
    user_msg_count = sum(1 for m in history if m["role"] == "user")
    must_submit = user_msg_count >= MAX_CLARIFICATIONS

    system_prompt = (
        "You help users create precise buy/sell queries on a marketplace platform.\n\n"

        "Your job has TWO phases:\n"
        "1) Conversation phase — ask questions and optionally call tools to help the user.\n"
        "2) Submission phase — produce a clean buy/sell query describing ONLY the item.\n\n"

        "---------------------------------\n"
        "CONVERSATION STRATEGY\n"
        "---------------------------------\n"
        "Ask for the most product-specific attributes first.\n"
        "Generic attributes like price, condition, and location come AFTER the item is clear.\n\n"

        "Category guides:\n"
        "- Electronics/devices: model, year, specs → then condition, color, price\n"
        "- Vehicles: make, model, year, mileage → then condition, color, price\n"
        "- Furniture/home: item type, dimensions, material → then condition, color\n"
        "- Clothing/accessories: item type, brand, size\n"
        "- Food/grocery: item name, quantity\n"
        "- General goods: item name, brand/model\n\n"

        "You may ask 2-3 related attributes in one message.\n"
        "Never ask about something the user already mentioned.\n"
        "Never repeat a question.\n\n"

        "WHEN TO SUBMIT EARLY:\n"
        "- If the user says \"any\", \"anything\", \"doesn't matter\", \"I don't care\", or similar\n"
        "  for ANY attribute — accept it and do NOT ask again.\n"
        "- You need at MINIMUM: intent (buy/sell) + item description. Everything else is optional.\n"
        "- If the user has provided the item and intent, and has declined to specify details,\n"
        "  submit immediately. Do NOT keep asking for more details.\n"
        "- Aim for 1-3 questions total. Most queries should submit within 2-4 messages.\n\n"

        "---------------------------------\n"
        "TOOLS\n"
        "---------------------------------\n"
        "You have access to tools for marketplace data. Use them proactively when helpful.\n"
        "Tool results are PRIVATE INFORMATION and must NEVER appear in the final summary.\n\n"

        "CRITICAL TOOL RULES:\n"
        "1. After a tool call you MUST respond with an ASK message.\n"
        "2. NEVER submit immediately after a tool call.\n"
        "3. Tool results are private context. Summaries must NEVER include them.\n\n"

        "---------------------------------\n"
        "SUBMISSION RULES\n"
        "---------------------------------\n"
        "When enough information is gathered, submit a query.\n\n"

        "The submission MUST:\n"
        "- Be ONE sentence\n"
        "- Be written in first person, i.e. I want to buy/sell...\n"
        "- Describe ONLY what the user wants to buy or sell\n"
        "- Include item + attributes + quantity + price (if known)\n\n"

        "The submission MUST NOT include:\n"
        "- Tool results\n"
        "- Marketplace information\n"
        "- Price comparisons\n"
        "- Advice\n"
        "- Demand commentary\n"
        "- Any explanation\n\n"

        "GOOD examples:\n"
        "I want to buy three Honeycrisp apples for under $10.\n"
        "I want to sell 10 Honeycrisp apples for $5 each.\n"
        "I want to buy a medium suit for someone 5'11\" tall.\n\n"

        "BAD examples:\n"
        '\"Honeycrisp apples usually sell for $4-$6 so I want to buy...\"  ← NOT allowed\n'
        '\"Listings show that suits are expensive so I want to buy...\"  ← NOT allowed\n\n'

        "---------------------------------\n"
        "SCOPE RULES\n"
        "---------------------------------\n"
        "You are ONLY a buy/sell query builder. You MUST NOT:\n"
        "- Offer to set up notifications, alerts, or reminders\n"
        "- Offer to search external websites or services\n"
        "- Give legal, ethical, or moral advice about what users can/cannot buy or sell\n"
        "- Refuse to create a query based on the item type — accept any legal product\n"
        "- Discuss anything outside of building the buy/sell query\n\n"

        "If the user asks for something outside your scope, politely redirect:\n"
        '"I can only help you create buy/sell queries. Would you like to continue with your query?"\n\n'

        "---------------------------------\n"
        "OUTPUT FORMAT\n"
        "---------------------------------\n"
        "Respond with ONLY valid JSON:\n\n"

        '{"action": "ask", "message": "question"}\n'
        '{"action": "submit", "summary": "final buy/sell query"}\n'
    )

    messages = [{"role": "system", "content": system_prompt}] + history

    if must_submit:
        messages.append({
            "role": "system",
            "content": 'You MUST submit now. Return {"action": "submit", "summary": "..."} combining ALL conversation details.'
        })
        
    # Detect if we're responding to a tool result — force text-only response
    last_is_tool_result = any(
        m.get("role") == "tool" for m in history[-2:]
    )
    ollama_tools = None if (must_submit or last_is_tool_result) else get_ollama_tools()

    result = None
    for attempt in range(3):
        try:
            # Temperature 0 for deterministic tool choice and JSON output (easier to test)
            msg = await _chat_with_tools(messages, tools=ollama_tools, temperature=0)
        except Exception:
            continue

        # Native tool call from Ollama
        if msg.get("tool_calls"):
            tc = msg["tool_calls"][0]
            fn = tc.get("function", {})
            tool_name = fn.get("name", "")
            tool_args = fn.get("arguments", {})
            if isinstance(tool_args, str):
                try:
                    tool_args = json.loads(tool_args)
                except (json.JSONDecodeError, TypeError):
                    tool_args = {}
            return {"action": "tool_call", "tool": tool_name, "args": tool_args}

        # Text response — parse as JSON for ask/submit
        content = (msg.get("content") or "").strip()
        if not content:
            logger.warning("converse() attempt %d: empty content from LLM", attempt + 1)
            continue
        try:
            result = _parse_json(content)
            break
        except Exception:
            # If the LLM returned prose instead of JSON, treat it as an ask message
            if len(content) > 10 and "{" not in content:
                logger.debug("converse(): LLM returned prose, using as ask message")
                return {"action": "ask", "message": content}
            logger.warning("converse() attempt %d: malformed JSON from LLM: %.200s", attempt + 1, content)
            continue

    if result is None:
        if must_submit:
            summary = await synthesize_summary(history)
            return {"action": "submit", "summary": summary}
        return {"action": "ask", "message": "Could you tell me more about what you're looking for?"}

    # Forced fallback: LLM still didn't submit despite safety limit
    if must_submit and result.get("action") != "submit":
        summary = await synthesize_summary(history)
        return {"action": "submit", "summary": summary}

    return result


async def evaluate_candidates(source_query: dict, candidates: list[dict]) -> list[dict]:
    """Score each candidate query for compatibility with the source query using the LLM.

    Args:
        source_query: Dict with id, intent, raw_text, attributes,
            required_match_attributes, preferred_match_attributes.
        candidates: List of dicts with id, intent, raw_text, attributes.

    Returns:
        List of dicts with "id" (candidate id), "score" (0.0–1.0), "reasoning" (str).
        IDs are preserved or mapped by position if the LLM returns non-matching ids.
        Empty list if candidates is empty.
    """
    if not candidates:
        return []

    candidate_descriptions = "\n".join(
        f"  Candidate {i+1} (id={c['id']}): intent={c['intent']}, "
        f"text=\"{c['raw_text']}\", attributes={json.dumps(c.get('attributes', {}))}"
        for i, c in enumerate(candidates)
    )

    prompt = f"""You are scoring compatibility between buyer/seller pairs on a marketplace. The candidates have complementary intents (buyer paired with seller). Do NOT penalize because intents differ — that is expected.

Your only job: score how well the PRODUCT and attributes align.

Source query:
  intent={source_query['intent']}, text="{source_query['raw_text']}", attributes={json.dumps(source_query.get('attributes', {}))}
  Required match attributes: {json.dumps(source_query.get('required_match_attributes', []))}
  Preferred match attributes: {json.dumps(source_query.get('preferred_match_attributes', []))}

Candidates:
{candidate_descriptions}

Return a JSON array where each element has:
- "id": the EXACT candidate id string (copy it verbatim — do NOT modify, truncate, or reformat)
- "score": compatibility score from 0.0 to 1.0
- "reasoning": brief explanation (1-2 sentences)

Score guidelines:
- 0.9-1.0: Same specific product, key attributes (model, size, specs) align
- 0.7-0.9: Same product type, most attributes compatible
- 0.5-0.7: Same broad category but different specific product (e.g. MacBook vs iPhone — both electronics)
- 0.3-0.5: Related but clearly different products
- <0.3: Completely different product categories

CRITICAL RULE: If the products are from different categories entirely (e.g. food vs toys, electronics vs clothing, furniture vs vehicles), the score MUST be below 0.3. Examples:
- "buy toys" vs "sell apples" → different categories → score < 0.3
- "buy laptop" vs "sell cookies" → different categories → score < 0.3
- "buy jacket" vs "sell dining table" → different categories → score < 0.3

IMPORTANT: A buyer matched with a seller for the SAME product is a strong pair — score it high.
IMPORTANT: Check BOTH the raw_text AND the attributes object for attribute values.
IMPORTANT: Only penalize for missing required attributes if the information truly cannot be found anywhere in the candidate's raw_text or attributes."""

    results = _parse_json(await _chat([{"role": "user", "content": prompt}], max_tokens=2048))

    # Validate: if LLM returned results without matching IDs, map by position
    candidate_ids = {c["id"] for c in candidates}
    returned_ids = {r.get("id") for r in results if isinstance(r, dict)}
    if returned_ids and not returned_ids & candidate_ids and len(results) == len(candidates):
        for i, r in enumerate(results):
            r["id"] = candidates[i]["id"]

    return results
