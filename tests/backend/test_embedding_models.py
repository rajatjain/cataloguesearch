"""Test module for embedding models."""
import logging
import torch

from backend.common.embedding_models import BaseEmbeddingModel, FP16EmbeddingModel, Quantized8BitEmbeddingModel, get_embedding_model_factory
from backend.config import Config
from tests.backend.base import initialise

log_handle = logging.getLogger(__name__)

def test_base_embedding_model(initialise):  # pylint: disable=unused-argument
    """Test base embedding model returns fp32 precision."""
    config = Config()
    config.settings()["vector_embeddings"]["embedding_model_type"] = "base"
    embedding_model = get_embedding_model_factory(config)
    text = "some text"
    em = embedding_model.get_embedding(text)
    assert len(em) == 1024
    # Check that the underlying model uses fp32 precision
    model_dtype = next(embedding_model._embedding_model.parameters()).dtype  # pylint: disable=protected-access
    assert model_dtype == torch.float32
    # Assert that the model is of correct class
    assert isinstance(embedding_model, BaseEmbeddingModel)
    assert not isinstance(embedding_model, FP16EmbeddingModel)
    assert not isinstance(embedding_model, Quantized8BitEmbeddingModel)

def test_fp16_embedding_model(initialise):  # pylint: disable=unused-argument
    """Test FP16 embedding model returns fp16 precision."""
    config = Config()
    config.settings()["vector_embeddings"]["embedding_model_type"] = "fp16"
    embedding_model = get_embedding_model_factory(config)
    text = "my text"
    em = embedding_model.get_embedding(text)
    assert len(em) == 1024
    # Check that the underlying model uses fp16 precision
    model_dtype = next(embedding_model._embedding_model.parameters()).dtype  # pylint: disable=protected-access
    assert model_dtype == torch.float16
    # Assert that the model is of correct class
    assert isinstance(embedding_model, FP16EmbeddingModel)
    assert isinstance(embedding_model, BaseEmbeddingModel)  # FP16 inherits from Base
    assert not isinstance(embedding_model, Quantized8BitEmbeddingModel)

def test_quantized_8bit_embedding_model(initialise):  # pylint: disable=unused-argument
    """Test Quantized8Bit embedding model functionality."""
    config = Config()
    config.settings()["vector_embeddings"]["embedding_model_type"] = "quantized_8bit"
    embedding_model = get_embedding_model_factory(config)
    text = "test quantized embedding"
    em = embedding_model.get_embedding(text)
    assert len(em) == 1024
    assert isinstance(em, list)
    assert all(isinstance(x, float) for x in em)
    # Verify model is loaded and parameters exist
    assert hasattr(embedding_model, '_embedding_model')
    assert embedding_model._embedding_model is not None  # pylint: disable=protected-access
    # Verify embedding dimension method works
    assert embedding_model.get_embedding_dimension() == 1024
    # Assert that the model is of correct class
    assert isinstance(embedding_model, Quantized8BitEmbeddingModel)
    assert isinstance(embedding_model, BaseEmbeddingModel)  # Quantized8Bit inherits from Base
    assert not isinstance(embedding_model, FP16EmbeddingModel)

def test_quantized_8bit_batch_embeddings(initialise):  # pylint: disable=unused-argument
    """Test Quantized8Bit embedding model batch processing."""
    config = Config()
    config.settings()["vector_embeddings"]["embedding_model_type"] = "quantized_8bit"
    embedding_model = get_embedding_model_factory(config)
    texts = ["first text", "second text", "third text"]
    embeddings = embedding_model.get_embeddings_batch(texts, batch_size=2)
    assert len(embeddings) == 3
    assert all(len(em) == 1024 for em in embeddings)
    assert all(isinstance(em, list) for em in embeddings)
    assert all(all(isinstance(x, float) for x in em) for em in embeddings)
    # Assert that the model is of correct class
    assert isinstance(embedding_model, Quantized8BitEmbeddingModel)
    assert isinstance(embedding_model, BaseEmbeddingModel)  # Quantized8Bit inherits from Base
    assert not isinstance(embedding_model, FP16EmbeddingModel)
