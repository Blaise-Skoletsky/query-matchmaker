from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.services.embedding import load_model
from app.routers import auth, queries, matches, chat, conversation
from app.ws.manager import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    print("Loading embedding model...")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, load_model)
    print("Embedding model loaded.")
    await manager.startup()
    yield
    await manager.shutdown()


app = FastAPI(title="MatchMaker API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(queries.router)
app.include_router(matches.router)
app.include_router(chat.router)
app.include_router(conversation.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
