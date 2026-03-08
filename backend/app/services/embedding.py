import asyncio
from functools import partial

from sentence_transformers import SentenceTransformer

from app.config import settings

_model: SentenceTransformer | None = None


def load_model():
    global _model
    _model = SentenceTransformer(settings.embedding_model)


def embed(text: str) -> list[float]:
    if _model is None:
        raise RuntimeError("Embedding model not loaded")
    return _model.encode(text).tolist()


async def embed_async(text: str) -> list[float]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(embed, text))
