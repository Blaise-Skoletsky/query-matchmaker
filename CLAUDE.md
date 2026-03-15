# CLAUDE.md

MatchMaker — a buy/sell marketplace where users submit natural-language queries and get matched with buyers/sellers via AI.

## Architecture
- **Frontend**: SvelteKit 5 (TypeScript) on port 5173
- **Backend**: FastAPI (Python, async) on port 8000
- **Database**: PostgreSQL 16 + pgvector (Docker)
- **Embeddings**: all-MiniLM-L6-v2 (sentence-transformers, 384-dim)
- **LLM**: Ollama (local, free — default model: qwen2.5:14b)

## Two-Stage Matching Pipeline
1. **Stage 1**: Vector similarity search pre-filtered by complementary intent (pgvector)
2. **Stage 2**: Ollama LLM evaluates top candidates and scores compatibility

## Agentic Query Conversation
The `converse()` function in `backend/app/services/llm.py` drives multi-turn query refinement:
- LLM decides when it has enough context to submit (no hard message cap)
- Safety cap: `MAX_CLARIFICATIONS = 5` user messages — forces submission via `synthesize_summary()`
- Tracks previously asked topics and injects them into the system prompt to prevent repetition
- No context panel on the frontend — location, budget, condition, urgency are gathered conversationally

## Dev Commands
```bash
# Start database
docker compose up -d

# Backend
cd backend
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev

# Tests
cd backend && pytest
```

## Key Env Vars
Set in `backend/.env`:
- `DATABASE_URL` — PostgreSQL connection (default: postgresql+asyncpg://matchmaker:matchmaker@localhost:5432/matchmaker)
- `OLLAMA_BASE_URL` — Ollama server (default: http://localhost:11434)
- `OLLAMA_MODEL` — Ollama model name (default: qwen2.5:14b)
- `JWT_SECRET` — JWT signing secret

## Project Structure
- `backend/app/models/` — SQLAlchemy ORM (user, query, match, chat)
- `backend/app/routers/` — FastAPI endpoints (auth, queries, matches, chat)
- `backend/app/services/` — Business logic (auth, embedding, llm, matching)
- `backend/app/ws/` — WebSocket connection manager
- `frontend/src/routes/` — SvelteKit pages
- `frontend/src/lib/` — API client, WebSocket client, stores

## Coding Practices
 - Don't be uncessearily verbose.
 - Ask clarifying questions
 - When you add new features, create tests. Don't create unncesseary tests. 