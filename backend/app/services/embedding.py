import asyncio
from functools import partial

from sentence_transformers import SentenceTransformer

from app.config import settings

_model: SentenceTransformer | None = None


def load_model():
    """Load the SentenceTransformer embedding model into the global _model.

    Must be called before embed() or embed_async(). Uses settings.embedding_model.
    """
    global _model
    _model = SentenceTransformer(settings.embedding_model)


def embed(text: str) -> list[float]:
    """Compute the embedding vector for a single string (synchronous).

    Args:
        text: Input string to embed.

    Returns:
        List of floats (embedding dimension from the loaded model).

    Raises:
        RuntimeError: If load_model() has not been called.
    """
    if _model is None:
        raise RuntimeError("Embedding model not loaded")
    return _model.encode(text).tolist()


async def embed_async(text: str) -> list[float]:
    """Compute the embedding vector for a single string (non-blocking).

    Args:
        text: Input string to embed.

    Returns:
        List of floats (embedding dimension from the loaded model).

    Raises:
        RuntimeError: If load_model() has not been called.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(embed, text))
