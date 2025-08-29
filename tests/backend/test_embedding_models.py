"""Test module for embedding models."""
import logging
import torch

from backend.common.embedding_models import BaseEmbeddingModel, FP16EmbeddingModel
from backend.config import Config
from tests.backend.base import initialise

log_handle = logging.getLogger(__name__)

def test_base_embedding_model(initialise):  # pylint: disable=unused-argument
    """Test base embedding model returns fp32 precision."""
    config = Config()
    base_embedding_model = BaseEmbeddingModel(config)
    text = "some text"
    em = base_embedding_model.get_embedding(text)
    assert len(em) == 1024
    # Check that the underlying model uses fp32 precision
    model_dtype = next(base_embedding_model._embedding_model.parameters()).dtype  # pylint: disable=protected-access
    assert model_dtype == torch.float32

def test_fp16_embedding_model(initialise):  # pylint: disable=unused-argument
    """Test FP16 embedding model returns fp16 precision."""
    config = Config()
    embedding_model = FP16EmbeddingModel(config)
    text = "my text"
    em = embedding_model.get_embedding(text)
    assert len(em) == 1024
    # Check that the underlying model uses fp16 precision
    model_dtype = next(embedding_model._embedding_model.parameters()).dtype  # pylint: disable=protected-access
    assert model_dtype == torch.float16
