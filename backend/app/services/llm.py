import json

import httpx

from app.config import settings


async def _chat(messages: list[dict], max_tokens: int = 1024) -> str:
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": messages,
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
        )
        response.raise_for_status()
        return response.json()["message"]["content"]


def _parse_json(text: str):
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


MAX_CLARIFICATIONS = 8  # safety cap only; LLM decides when it's ready


async def _synthesize_summary(history: list[dict]) -> str:
    prompt = (
        "Summarize this marketplace query conversation into one clear, specific sentence "
        "that captures everything the user wants — item/need, constraints, and any details "
        "they provided in answers. Return ONLY the summary sentence.\n\nConversation:\n"
        + "\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in history
        )
    )
    return (await _chat([{"role": "user", "content": prompt}], max_tokens=256)).strip()


async def converse(history: list[dict]) -> dict:
    user_msg_count = sum(1 for m in history if m["role"] == "user")
    must_submit = user_msg_count >= MAX_CLARIFICATIONS

    # Build explicit list of topics already asked
    asked = [m["content"] for m in history if m["role"] == "assistant"]
    asked_note = ""
    if asked:
        items = "\n".join(f"  {i+1}. {q}" for i, q in enumerate(asked))
        asked_note = f"\nYou have already asked:\n{items}\nDo NOT ask about any of these topics again.\n"

    system_prompt = (
        "You help users create precise buy/sell queries on a marketplace platform.\n\n"
        "STRATEGY: Ask for the most product-specific details first — the attributes that differentiate "
        "one listing from another. Generic details (condition, location, price) come AFTER you know "
        "what the specific item/need is.\n\n"
        "Category guides — ask the key attributes first:\n"
        "- Electronics/devices: exact model, year, storage/specs → then condition, color, price\n"
        "- Vehicles: make, model, year, mileage → then condition, color, price\n"
        "- Furniture/home: item type, dimensions, material → then condition, color, price\n"
        "- Clothing/accessories: item type, brand, size → then condition, color, price\n"
        "- Sports/outdoor: item type, brand, size/spec → then condition, price\n"
        "- General goods: item name, brand/model → then condition, price\n\n"
        "RULES:\n"
        "1. You MAY ask 2-3 closely related attributes in one question to save turns. "
        "Example: 'What year, storage size, and color is it?' — not three separate turns.\n"
        "2. Never ask about something the user already mentioned.\n"
        f"3. Never repeat a topic you already asked about.{asked_note}"
        "4. Submit as soon as you have enough specific detail for a high-quality match.\n"
        "5. When submitting, write ONE coherent summary incorporating ALL details from the conversation in first-person (e.g. 'I want to buy...', 'I am, selling...')\n\n"
        + ("You MUST submit now — safety limit reached.\n\n" if must_submit else "")
        + 'Respond with ONLY valid JSON:\n'
        '- {"action": "ask", "message": "your question(s)"}\n'
        '- {"action": "submit", "summary": "complete query combining all details"}'
    )

    messages = [{"role": "system", "content": system_prompt}] + history

    if must_submit:
        messages.append({
            "role": "system",
            "content": 'You MUST submit now. Return {"action": "submit", "summary": "..."} combining ALL conversation details.'
        })

    result = None
    for attempt in range(3):
        raw = await _chat(messages)
        if not raw.strip():
            continue
        try:
            result = _parse_json(raw)
            break
        except Exception:
            continue

    if result is None:
        if must_submit or user_msg_count > 0:
            summary = await _synthesize_summary(history)
            return {"action": "submit", "summary": summary}
        return {"action": "ask", "message": "Could you tell me more about what you're looking for?"}

    # Forced fallback: LLM still didn't submit despite safety limit
    if must_submit and result.get("action") != "submit":
        summary = await _synthesize_summary(history)
        return {"action": "submit", "summary": summary}

    return result


async def evaluate_candidates(source_query: dict, candidates: list[dict]) -> list[dict]:
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
