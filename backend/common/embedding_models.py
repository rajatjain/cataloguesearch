from sentence_transformers import SentenceTransformer, CrossEncoder
from typing import List, Dict, Any, Union
import logging
import os

from backend.common.reranker import ONNXReranker

log_handle = logging.getLogger(__name__)

_models = dict()

class BaseEmbeddingModel:
    def __init__(self, config):
        self.config = config
        self.embedding_model_name = config.EMBEDDING_MODEL_NAME
        self.reranker_model_name = config.RERANKING_MODEL_NAME
        self.reranker_onnx_path = config.RERANKER_ONNX_PATH
        # Eagerly load models on initialization
        self._embedding_model = self._load_embedding_model()
        self._reranker_model = self._load_reranker_model()
    
    def get_class(self, config: Dict[str, Any]) -> 'BaseEmbeddingModel':
        return self.__class__(config)
    
    def get_embedding(self, text: str) -> List[float]:
        try:
            embedding = self._embedding_model.encode(text).tolist()
            log_handle.debug(f"Generated embedding for text (first 10 dims): {embedding[:10]}...")
            return embedding
        except Exception as e:
            log_handle.error(f"Error generating embedding for text: '{text[:50]}...'. Error: {e}")
            return [0.0] * self._embedding_model.get_sentence_embedding_dimension()
    
    def get_reranking_model(self) -> ONNXReranker:
        return self._reranker_model
    
    def get_embedding_dimension(self) -> int:
        return self._embedding_model.get_sentence_embedding_dimension()
    
    def _load_embedding_model(self) -> SentenceTransformer:
        global _models
        model_key = f"{self.embedding_model_name}_{self.__class__.__name__}"
        
        if model_key not in _models:
            try:
                log_handle.info(f"Loading embedding model: {self.embedding_model_name}...")
                # For e2-medium, use basic CPU-only optimization
                model = SentenceTransformer(self.embedding_model_name, device='cpu')
                model.eval()
                for param in model.parameters():
                    param.requires_grad = False
                _models[model_key] = model
                log_handle.info(f"Embedding model '{self.embedding_model_name}' loaded successfully.")
            except Exception as e:
                log_handle.error(f"Failed to load embedding model '{self.embedding_model_name}': {e}")
                raise
        else:
            log_handle.info(f"Using pre-loaded embedding model: {self.embedding_model_name}")
        return _models[model_key]
    
    def _load_reranker_model(self) -> ONNXReranker:
        """
        Loads the ONNX reranker model. This is the only supported reranker.
        If the model path is not configured or the model is not found, this will raise a critical error.
        """
        global _models
        model_key = f"onnx_{self.reranker_onnx_path}"

        if model_key in _models:
            log_handle.info(f"Using pre-loaded ONNX reranker from: {self.reranker_onnx_path}")
            return _models[model_key]

        # The ONNX model is now a hard requirement. Fail fast if it's not configured or found.
        if not self.reranker_onnx_path or not os.path.exists(self.reranker_onnx_path):
            log_handle.critical(f"ONNX reranker path not configured or not found: '{self.reranker_onnx_path}'. This is a fatal error.")
            raise FileNotFoundError(f"Required ONNX reranker model not found at path: {self.reranker_onnx_path}")
        
        try:
            model = ONNXReranker(self.reranker_onnx_path)
            _models[model_key] = model
            return model
        except Exception as e:
            log_handle.critical(f"Fatal error loading ONNX reranker from '{self.reranker_onnx_path}': {e}", exc_info=True)
            raise

class FP16EmbeddingModel(BaseEmbeddingModel):
    def _load_embedding_model(self) -> SentenceTransformer:
        global _models
        model_key = f"{self.embedding_model_name}_{self.__class__.__name__}"
        
        if model_key not in _models:
            try:
                log_handle.info(f"Loading FP16 embedding model: {self.embedding_model_name}...")
                # Load with CPU-only and memory optimizations
                model = SentenceTransformer(self.embedding_model_name, device='cpu')
                # Convert to half precision for CPU
                model.half()
                # Set to eval mode to save memory
                model.eval()
                # Disable gradients to save memory
                for param in model.parameters():
                    param.requires_grad = False
                _models[model_key] = model
                log_handle.info(f"FP16 embedding model '{self.embedding_model_name}' loaded successfully.")
            except Exception as e:
                log_handle.error(f"Failed to load FP16 embedding model '{self.embedding_model_name}': {e}")
                raise
        else:
            log_handle.info(f"Using pre-loaded embedding model: {self.embedding_model_name}")
        return _models[model_key]

class Quantized8BitEmbeddingModel(BaseEmbeddingModel):
    def _load_embedding_model(self) -> SentenceTransformer:
        global _models
        model_key = f"{self.embedding_model_name}_{self.__class__.__name__}"
        
        if model_key not in _models:
            try:
                log_handle.info(f"Loading 8-bit quantized embedding model: {self.embedding_model_name}...")
                # For e2-medium, use CPU-only with basic optimizations instead of 8-bit quantization
                model = SentenceTransformer(self.embedding_model_name, device='cpu')
                # Set to eval mode to save memory
                model.eval()
                # Disable gradients to save memory
                for param in model.parameters():
                    param.requires_grad = False
                _models[model_key] = model
                log_handle.info(f"CPU-optimized embedding model '{self.embedding_model_name}' loaded successfully.")
            except Exception as e:
                log_handle.error(f"Failed to load embedding model '{self.embedding_model_name}': {e}")
                raise
        else:
            log_handle.info(f"Using pre-loaded embedding model: {self.embedding_model_name}")
        return _models[model_key]

def get_embedding_model_factory(config) -> BaseEmbeddingModel:
    model_type = config.EMBEDDING_MODEL_TYPE
    
    if model_type == "fp16":
        return FP16EmbeddingModel(config)
    elif model_type == "quantized_8bit":
        return Quantized8BitEmbeddingModel(config)
    else:
        return BaseEmbeddingModel(config)
