# MatchMaker

A query-matching platform where users submit natural-language requests and get matched via AI. Built with a two-stage matching pipeline: vector similarity search followed by LLM-powered compatibility scoring.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌────────────┐
│  SvelteKit   │────▶│   FastAPI     │────▶│ PostgreSQL │
│  Frontend    │◀────│   Backend     │◀────│ + pgvector │
│  :5173       │     │   :8000       │     │            │
└─────────────┘     └──────┬───────┘     └────────────┘
                           │
                    ┌──────┴───────┐
                    │    Redis     │
                    │  (Pub/Sub)   │
                    └──────┬───────┘
                           │
                    ┌──────┴───────┐
                    │   Ollama     │
                    │  (LLM)      │
                    └──────────────┘
```

| Layer | Tech | Purpose |
|-------|------|---------|
| Frontend | SvelteKit 5 (TypeScript) | UI, chat interface, query management |
| Backend | FastAPI (Python, async) | REST API, WebSocket, background agents |
| Database | PostgreSQL 16 + pgvector | Storage, vector similarity search (HNSW) |
| Embeddings | all-MiniLM-L6-v2 | 384-dim sentence embeddings |
| LLM | Ollama (mistral) | Metadata extraction, compatibility scoring, moderation |
| Pub/Sub | Redis 7 | Real-time WebSocket message fanout |

## Two-Stage Matching Pipeline

1. **Vector Pre-filter** — pgvector cosine similarity search, filtered by complementary intent (buy↔sell, job_seek↔job_offer, etc.)
2. **LLM Scoring** — Ollama evaluates top candidates for subject-matter compatibility (0.0–1.0), creates matches above threshold (0.7)

## Background Agents

Six autonomous agents run on configurable intervals:

| Agent | Interval | Description |
|-------|----------|-------------|
| **Query Expiration** | 5 min | Expires queries past `expires_at` or older than 30 days |
| **Match Reprocessing** | 2 min | Retries failed matching pipelines (up to 3 attempts) |
| **Content Moderation** | 1 min | LLM-based sweep for spam, abuse, illegal content |
| **Analytics Snapshot** | 1 hour | Aggregates daily platform metrics |
| **Notifications** | Event-driven | Creates in-app notifications for matches, accepts, rejects |
| **Recommendations** | On-demand | Surfaces similar queries, trending categories, demand gaps |

Agent status is exposed at `GET /api/agents/status`.

## API Endpoints

### Auth
- `POST /api/auth/register` — Register (returns JWT)
- `POST /api/auth/login` — Login (returns JWT)
- `GET /api/auth/me` — Current user

### Queries
- `POST /api/queries` — Create query (triggers moderation + matching)
- `GET /api/queries` — List user's queries
- `GET /api/queries/{id}` — Get query
- `GET /api/queries/{id}/trace` — Matching pipeline trace
- `DELETE /api/queries/{id}` — Cancel query

### Matches
- `GET /api/matches` — List user's matches
- `POST /api/matches/{id}/accept` — Accept (creates chatroom, notifies)
- `POST /api/matches/{id}/reject` — Reject (notifies other party)

### Chat
- `GET /api/chatrooms` — List chatrooms
- `GET /api/chatrooms/{id}` — Chatroom details
- `GET /api/chatrooms/{id}/messages` — Message history
- `WS /ws/chat/{room_id}?token=...` — Real-time WebSocket chat

### Conversation
- `POST /api/conversation` — Multi-turn guided query creation

### Notifications
- `GET /api/notifications` — List notifications (`?unread_only=true`)
- `GET /api/notifications/count` — Unread/total count
- `POST /api/notifications/{id}/read` — Mark read
- `POST /api/notifications/read-all` — Mark all read

### Recommendations
- `GET /api/recommendations/similar` — Queries matching user's interests
- `GET /api/recommendations/trending` — Trending categories
- `GET /api/recommendations/demand-gaps` — Supply/demand imbalances

### Analytics
- `GET /api/analytics/latest` — Latest daily snapshot
- `GET /api/analytics/snapshots` — Historical snapshots

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js 18+
- Ollama with `mistral` model pulled

### Setup

```bash
# Start PostgreSQL + Redis
docker compose up -d

# Backend
cd backend
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

### Environment Variables

Set in `backend/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://matchmaker:matchmaker@localhost:5432/matchmaker` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server |
| `OLLAMA_MODEL` | `mistral` | LLM model name |
| `JWT_SECRET` | `dev-secret-change-in-production` | JWT signing key |
| `MATCH_SCORE_THRESHOLD` | `0.7` | Minimum score to create a match |
| `CANDIDATE_LIMIT` | `50` | Max vector search candidates |
| `LLM_EVAL_LIMIT` | `10` | Max candidates sent to LLM |

## Project Structure

```
backend/
├── app/
│   ├── agents/           # Background agents
│   │   ├── scheduler.py  # Central agent scheduler
│   │   ├── expiration.py  # Query expiration
│   │   ├── reprocessing.py# Match retry logic
│   │   ├── moderation.py  # Content moderation
│   │   ├── analytics.py   # Metrics aggregation
│   │   ├── notifications.py # In-app notifications
│   │   └── recommendations.py # Query suggestions
│   ├── models/            # SQLAlchemy ORM models
│   ├── routers/           # FastAPI endpoints
│   ├── schemas/           # Pydantic request/response models
│   ├── services/          # Business logic (auth, embedding, LLM, matching)
│   └── ws/                # WebSocket connection manager
├── alembic/               # Database migrations
└── tests/                 # pytest test suite

frontend/
├── src/
│   ├── routes/            # SvelteKit pages
│   └── lib/               # API client, WebSocket client, stores
└── static/
```

## Testing

```bash
cd backend
pytest
```

Tests cover LLM scoring, metadata extraction, all background agents, and the scheduler.
