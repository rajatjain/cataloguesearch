import logging
import time
import torch
from optimum.onnxruntime import ORTModelForSequenceClassification
from transformers import AutoTokenizer

log_handle = logging.getLogger(__name__)
class ONNXReranker:
    """A reusable class to handle the ONNX reranker model."""
    def __init__(self, model_path: str):
        log_handle.info(f"Loading ONNX model from '{model_path}'...")
        self.model = ORTModelForSequenceClassification.from_pretrained(model_path)
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        log_handle.info("Reranker model loaded successfully.")

    def predict(self, sentence_pairs: list[list[str]], batch_size: int = 4):
        """Reranks a list of sentence pairs and returns their scores."""
        start_time = time.time()
        with torch.no_grad():
            inputs = self.tokenizer(
                sentence_pairs,
                padding=True,
                truncation=True,
                return_tensors="pt",
                max_length=512,
            )
            outputs = self.model(**inputs)
            scores = torch.sigmoid(outputs.logits.squeeze()).cpu().numpy()
        end_time = time.time()
        log_handle.info(f"Reranking took {end_time - start_time:.2f} seconds")
        return scores