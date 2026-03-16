"""Tests for app.services.embedding."""
from unittest.mock import patch, MagicMock
import numpy as np

import pytest


class TestEmbedding:

    def test_embed_model_not_loaded_raises(self):
        from app.services import embedding
        original = embedding._model
        try:
            embedding._model = None
            with pytest.raises(RuntimeError, match="not loaded"):
                embedding.embed("test")
        finally:
            embedding._model = original

    def test_embed_returns_floats(self):
        from app.services import embedding
        original = embedding._model
        try:
            mock_model = MagicMock()
            mock_model.encode.return_value = np.array([0.1, 0.2, 0.3])
            embedding._model = mock_model
            result = embedding.embed("test text")
            assert isinstance(result, list)
            assert all(isinstance(x, float) for x in result)
        finally:
            embedding._model = original

    @pytest.mark.asyncio
    async def test_embed_async_delegates(self):
        from app.services import embedding
        original = embedding._model
        try:
            mock_model = MagicMock()
            mock_model.encode.return_value = np.array([0.5, 0.6])
            embedding._model = mock_model
            result = await embedding.embed_async("test")
            assert isinstance(result, list)
            mock_model.encode.assert_called_once_with("test")
        finally:
            embedding._model = original

    def test_load_model_sets_global(self):
        from app.services import embedding
        original = embedding._model
        try:
            with patch("app.services.embedding.SentenceTransformer") as mock_st:
                mock_st.return_value = MagicMock()
                embedding.load_model()
                assert embedding._model is not None
                mock_st.assert_called_once()
        finally:
            embedding._model = original
