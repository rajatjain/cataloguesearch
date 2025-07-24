from sentence_transformers import SentenceTransformer
from typing import List
import logging

log_handle = logging.getLogger(__name__)

_models = dict()

def get_embedding_model(model_name: str) -> SentenceTransformer:
    """
    Retrieves a pre-trained SentenceTransformer model by name.
    If the model is already loaded, it returns the cached instance.

    Args:
        model_name (str): The name of the SentenceTransformer model to load.

    Returns:
        SentenceTransformer: The loaded SentenceTransformer model.
    """
    global _models
    if not model_name:
        log_handle.error("Model name cannot be empty.")
        raise ValueError("Model name must be provided.")
    if model_name not in _models:
        try:
            log_handle.info(f"Loading embedding model: {model_name}...")
            _models[model_name] = SentenceTransformer(model_name)
            log_handle.info(f"Embedding model '{model_name}' loaded successfully.")
        except Exception as e:
            log_handle.error(f"Failed to load embedding model '{model_name}': {e}")
            raise
    return _models[model_name]

def get_embedding(model_name :str, text: str) -> List[float]:
    """
    Generates a vector embedding for the given text using the specified model.

    Args:
        text (str): The input text to embed.
        model_name (str): The name of the SentenceTransformer model to use.

    Returns:
        List[float]: A list of floats representing the embedding vector.
                     Returns an empty list if the model is not loaded or text is empty.
    """
    model = get_embedding_model(model_name)
    try:
        # Do not return empty list for empty text.
        # This should return a vector embedding on empty text as well.
        embedding = model.encode(text).tolist()
        log_handle.debug(f"Generated embedding for text (first 10 dims): {embedding[:10]}...")
        return embedding
    except Exception as e:
        log_handle.error(f"Error generating embedding for text: '{text[:50]}...'. Error: {e}")
        return [0.0] * model.get_sentence_embedding_dimension()
