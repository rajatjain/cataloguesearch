import os

from huggingface_hub import login
from sentence_transformers import SentenceTransformer
from typing import List
import logging
import torch
from transformers import AutoTokenizer, AutoModel
log_handle = logging.getLogger(__name__)

_models = dict()

def get_embedding_model(model_name: str):
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
    if model_name == "AI4Bharat/indic-bert":
        _get_model_tokenizer()
        return get_incibert_embedding(text)
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

# --- Load Model and Tokenizer ---
# Load the IndicBERT model and tokenizer from Hugging Face.
# This might take a few minutes on the first run as it downloads the model.
_tokenizer = None
_model = None

def _get_model_tokenizer():
    global _tokenizer, _model
    if _tokenizer is not None and _model is not None:
        return _tokenizer, _model
    if _tokenizer is None and _model is None:
        login(os.environ.get("HF_TOKEN"))
        log_handle.info("Loading IndicBERT tokenizer...")
        _tokenizer = AutoTokenizer.from_pretrained("ai4bharat/indic-bert")
        log_handle.info("IndicBERT tokenizer loaded successfully.")
        log_handle.info("Loading IndicBERT model...")
        _model = AutoModel.from_pretrained("ai4bharat/indic-bert")
        log_handle.info("IndicBERT model loaded successfully.")

    return _tokenizer, _model

def get_incibert_embedding(text: str) -> List[float]:
    """Generates a 768-dimension embedding for the given text using IndicBERT."""
    log_handle.info("Generating embedding for text using IndicBERT...")
    tokenizer, model = _get_model_tokenizer()

    # Tokenize the input text
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)

    # Get model outputs (no gradient calculation needed)
    with torch.no_grad():
        outputs = model(**inputs)

    # Perform mean pooling to get a single vector for the entire text
    # This averages the token embeddings from the last hidden layer.
    sentence_embedding = outputs.last_hidden_state.mean(dim=1).squeeze()

    return sentence_embedding.tolist()