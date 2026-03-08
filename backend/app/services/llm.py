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


async def extract_metadata(raw_text: str) -> dict:
    prompt = f"""Analyze this user query and extract structured metadata. Return ONLY valid JSON, no other text.

Query: "{raw_text}"

Return JSON with these fields:
- "intent": one of [buy, sell, meetup, job_seek, job_offer, housing_seek, housing_offer, service_seek, service_offer, event, other]
- "category": a short category label (e.g. "vehicles", "electronics", "sports", "software_engineering")
- "attributes": object with key attributes extracted from the query (e.g. {{"color": "white", "make": "Toyota"}})
- "complementary_intents": list of intents that would match this query (e.g. a "buy" query matches ["sell"])
- "required_match_attributes": list of attribute keys that MUST match for a good match
- "preferred_match_attributes": list of attribute keys that are nice-to-have"""

    return _parse_json(await _chat([{"role": "user", "content": prompt}]))


async def converse(history: list[dict]) -> dict:
    user_msg_count = sum(1 for m in history if m["role"] == "user")

    system_prompt = f"""You help users create search/match queries on a marketplace platform.

RULES:
1. You may ask AT MOST ONE follow-up question total. If the user has already answered a follow-up (there are {user_msg_count} user messages), you MUST submit.
2. Never ask about something the user already mentioned.
3. If the first message has enough context to understand what they want, submit immediately.
4. Keep follow-ups short and specific. Ask about the single most important missing detail only.
5. When submitting, combine ALL information from the conversation into one clear summary.

Respond with ONLY valid JSON:
- Need more info: {{"action": "ask", "message": "one short question"}}
- Ready: {{"action": "submit", "summary": "complete query combining all details from conversation"}}"""

    messages = [{"role": "system", "content": system_prompt}] + history

    if user_msg_count >= 2:
        messages.append({
            "role": "system",
            "content": "The user has answered your follow-up. You MUST submit now. Return {\"action\": \"submit\", \"summary\": \"...\"} combining all information."
        })

    result = _parse_json(await _chat(messages))

    # Force submission if user has answered the clarification question
    if user_msg_count >= 2 and result.get("action") != "submit":
        summary = "\n".join(m["content"] for m in history if m["role"] == "user")
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

    prompt = f"""You are scoring compatibility between marketplace query pairs. The candidates below have already been pre-filtered to have COMPLEMENTARY intents to the source — a buyer paired with a seller, a job seeker with a job poster, a renter with a landlord, etc. Complementary intents are CORRECT and EXPECTED. Do NOT penalize a candidate because its intent differs from the source.

Your only job: score how well the specific subject matter and attributes align.

Source query:
  intent={source_query['intent']}, text="{source_query['raw_text']}", attributes={json.dumps(source_query.get('attributes', {}))}
  Required match attributes: {json.dumps(source_query.get('required_match_attributes', []))}
  Preferred match attributes: {json.dumps(source_query.get('preferred_match_attributes', []))}

Candidates (each has a complementary intent to the source):
{candidate_descriptions}

Return a JSON array where each element has:
- "id": the candidate id
- "score": compatibility score from 0.0 to 1.0
- "reasoning": brief explanation (1-2 sentences)

Score guidelines:
- 1.0: Same specific item/role/subject, all key attributes align (e.g. "buy MacBook Pro" + "sell MacBook Pro")
- 0.7+: Same item/subject, most important attributes match
- 0.4-0.7: Related but key attributes differ (e.g. "buy MacBook Pro 16-inch M3" + "sell generic MacBook" — same product family but required specifics are missing)
- <0.4: Different item/subject entirely (e.g. "buy MacBook" + "sell iPhone")

IMPORTANT: A buyer matched with a seller for the same product is a perfect complementary pair — score it high.
IMPORTANT: If the source query lists required match attributes and the candidate is missing or vague on those attributes, cap the score at 0.6."""

    return _parse_json(await _chat([{"role": "user", "content": prompt}], max_tokens=2048))
