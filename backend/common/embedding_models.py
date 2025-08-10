from sentence_transformers import SentenceTransformer, CrossEncoder
from typing import List, Dict, Any, Union
import logging
import os
from backend.config import Config
from backend.common.reranker import ONNXReranker

log_handle = logging.getLogger(__name__)

_models = dict()
_device = None

def _get_device():
    """
    Determines the optimal compute device. Forces CPU if in a Docker environment,
    otherwise auto-detects GPU/MPS. Conditionally imports torch to avoid
    loading it in the CPU-only Docker environment.
    """
    global _device
    if _device:
        return _device

    # If ENVIRONMENT is set, we're in Docker, so force CPU and avoid torch import.
    if Config.is_docker_environment():
        _device = 'cpu'
        log_handle.info(f"Running in Docker environment ('{os.getenv('ENVIRONMENT')}'). Forcing CPU.")
    else:
        # Not in Docker, so we can try to use GPU. Import torch only when needed.
        try:
            import torch
            if torch.cuda.is_available():
                _device = 'cuda'
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                _device = 'mps'
            else:
                _device = 'cpu'
            log_handle.info(f"Auto-detected best available device: {_device}")
        except ImportError:
            log_handle.warning("torch is not installed. Falling back to CPU. For GPU support, please install torch.")
            _device = 'cpu'

    return _device

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

    def get_embeddings_batch(self, texts: List[str], batch_size: int = 8) -> List[List[float]]:
        """
        Generates embeddings for a batch of texts. This is much more efficient
        than calling get_embedding for each text individually.
        """
        try:
            log_handle.debug(f"Generating embeddings for a batch of {len(texts)} texts...")
            # The encode method of SentenceTransformer is highly optimized for batching.
            embeddings = self._embedding_model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=True
            )
            return embeddings.tolist()
        except Exception as e:
            log_handle.error(f"Error generating batch embeddings. Error: {e}", exc_info=True)
            # Return a list of zero vectors matching the input length
            return [[0.0] * self.get_embedding_dimension()] * len(texts)
    
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
                device = _get_device()
                model = SentenceTransformer(self.embedding_model_name, device=device)
                model.eval()
                for param in model.parameters():
                    param.requires_grad = False
                _models[model_key] = model
                log_handle.info(
                    f"Embedding model '{self.embedding_model_name}' loaded successfully on device '{device}'.")
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
                device = _get_device()
                model = SentenceTransformer(self.embedding_model_name, device=device)

                # FP16 is beneficial on CUDA/MPS, but not always on CPU.
                if device != 'cpu':
                    model.half()
                    log_handle.info("Converted model to FP16 (half precision).")

                # Set to eval mode to save memory
                model.eval()
                # Disable gradients to save memory
                for param in model.parameters():
                    param.requires_grad = False
                _models[model_key] = model
                log_handle.info(
                    f"FP16 embedding model '{self.embedding_model_name}' loaded successfully on device '{device}'.")
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
                device = _get_device()
                model = SentenceTransformer(self.embedding_model_name, device=device)
                # Set to eval mode to save memory
                model.eval()
                # Disable gradients to save memory
                for param in model.parameters():
                    param.requires_grad = False
                _models[model_key] = model
                log_handle.info(
                    f"CPU-optimized embedding model '{self.embedding_model_name}' loaded successfully on device '{device}'.")
            except Exception as e:
                log_handle.error(f"Failed to load embedding model '{self.embedding_model_name}': {e}")
                raise
        else:
            log_handle.info(f"Using pre-loaded embedding model: {self.embedding_model_name}")
        return _models[model_key]

def get_embedding_model_factory(config) -> BaseEmbeddingModel:
    model_type = config.EMBEDDING_MODEL_TYPE
    factory_key = f"factory_{model_type}"

    global _models
    if factory_key in _models:
        log_handle.info(f"Using pre-loaded embedding model factory of type: {model_type}")
        return _models[factory_key]

    log_handle.info(f"Creating new embedding model factory of type: {model_type}")
    if model_type == "fp16":
        factory_instance = FP16EmbeddingModel(config)
    elif model_type == "quantized_8bit":
        factory_instance = Quantized8BitEmbeddingModel(config)
    else:
        factory_instance = BaseEmbeddingModel(config)

    _models[factory_key] = factory_instance
    return factory_instance
