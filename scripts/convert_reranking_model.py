# convert_model.py
from optimum.onnxruntime import ORTModelForSequenceClassification
from transformers import AutoTokenizer
import logging
import os

# Set up simple logging to see progress
logging.basicConfig(level=logging.INFO)

# Define the original model from Hugging Face and the local path to save the ONNX version
# model_id = "BAAI/bge-reranker-v2-m3"
# onnx_path = "./bge-reranker-v2-m3-onnx"

model_id = "BAAI/bge-reranker-base"
onnx_path = "./bge-reranker-base-onnx"

# --- Main Conversion Logic ---
try:
    if os.path.exists(onnx_path):
        logging.warning(f"Directory '{onnx_path}' already exists. Skipping conversion.")
    else:
        logging.info(f"Loading tokenizer for '{model_id}'...")
        tokenizer = AutoTokenizer.from_pretrained(model_id)

        logging.info(f"Exporting '{model_id}' to ONNX format. This may take a few moments...")
        # This line downloads the model, converts it to ONNX, and applies optimizations.
        model = ORTModelForSequenceClassification.from_pretrained(model_id, export=True)

        logging.info(f"Saving ONNX model and tokenizer to '{onnx_path}'...")
        model.save_pretrained(onnx_path)
        tokenizer.save_pretrained(onnx_path)

        logging.info("✅ Model conversion and saving complete.")
        logging.info(f"Your optimized ONNX model is now ready in the '{onnx_path}' directory.")

except Exception as e:
    logging.error(f"An error occurred: {e}")