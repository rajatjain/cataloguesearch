# -*- coding: utf-8 -*-
"""
This script generates vector embeddings for a list of text paragraphs using
four different AI models and indexes them into an OpenSearch instance.

It uses a ThreadPoolExecutor for parallel processing to improve performance.
"""

# ==============================================================================
# SETUP INSTRUCTIONS
# ==============================================================================
#
# 1.  **Install requirements:**
#     pip install -r requirements.txt
#
# 2.  **Authenticate with Google Cloud:**
#     This is required for the Google model. Ensure you are logged in via:
#     `gcloud auth application-default login`
#
# 3.  **Fill in the configuration below.**
#
# ==============================================================================

import concurrent.futures
import os
from typing import List, Tuple, Dict, Any

import numpy as np
import torch
import yaml
from opensearchpy import OpenSearch, helpers
from sentence_transformers import SentenceTransformer, models
from tqdm import tqdm
from vertexai.language_models import TextEmbeddingModel
import vertexai

# --- CONFIGURATION - PLEASE FILL THESE IN ---
PROJECT_ID = "jaincatalogue"  # Your Google Cloud project ID for the Google model
LOCATION = "us-central1"            # The region for your Vertex AI model
OPENSEARCH_INDEX_NAME = "hindi_scriptures" # The name of your OpenSearch index
PROCCESSOR_ID = "eafa6f76ad214fd9"
# --- END OF CONFIGURATION ---

# --- Global model cache to avoid reloading models in each thread ---
MODELS = {}

MODEL_CONFIG = {
    'google': {
        'name': 'text-multilingual-embedding-002',
        'field': 'embedding_google'
    },
    'e5_large': {
        'name': 'intfloat/multilingual-e5-large',
        'field': 'embedding_e5_large'
    },
    'bge_m3': {
        'name': 'BAAI/bge-m3',
        'field': 'embedding_bge_m3'
    },
    'indic_bert': {
        'name': 'ai4bharat/indic-bert',
        'field': 'embedding_indic_bert'
    }
}

_client = None

def get_opensearch_client():
    global _client
    if _client:
        return _client
    try:
        client = OpenSearch(
            hosts=[{'scheme': 'https', 'host': "localhost", 'port': 9200}],
            http_auth=("admin", "Admin@Password123!"),
            use_ssl=True,
            verify_certs=False,
            ssl_assert_hostname=False,
            ssl_show_warn=False
        )
        if not client.ping():
            raise ConnectionError("Failed to ping OpenSearch.")
        _client = client
        print("OpenSearch client initialized and cached successfully.")
    except Exception as e:
        raise
    return _client

def delete_index():
    global OPENSEARCH_INDEX_NAME
    client = get_opensearch_client()
    index_name = OPENSEARCH_INDEX_NAME
    try:
        if client.indices.exists(index=index_name):
            client.indices.delete(index=index_name)
            print(f"Index '{index_name}' deleted successfully.")
        else:
            print(f"Index '{index_name}' does not exist.")
    except Exception as e:
        print(f"Error deleting index '{index_name}': {e}")
        raise

def create_index_if_not_exists():
    client = get_opensearch_client()
    config_path = os.path.join(os.path.dirname(__file__), "opensearch-config.yaml")
    with open(config_path, 'r', encoding='utf-8') as file:
        yaml_config = yaml.safe_load(file)
    index_name = OPENSEARCH_INDEX_NAME
    settings = yaml_config.get('settings', {})
    mappings = yaml_config.get('mappings', {})
    try:
        if not client.indices.exists(index=index_name):
            client.indices.create(index=index_name, body={"settings": settings, "mappings": mappings})
            print(f"Index '{index_name}' created.")
    except Exception as e:
        print(f"Error creating index '{index_name}': {e}")
        raise

def initialize_models():
    """
    Initializes all embedding models and stores them in the global cache.
    """
    print("Initializing all embedding models...")

    # 1. Initialize Google Model
    try:
        print(f"Initialising google model with PROJECT_ID: {PROJECT_ID}")
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        MODELS['google'] = TextEmbeddingModel.from_pretrained(MODEL_CONFIG['google']['name'])
        print("Google model initialized.")
    except Exception as e:
        print(f"Failed to initialize Google model: {e}")
        MODELS['google'] = None

    # 2. Initialize Open Source Models
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device '{device}' for open-source models.")

    # FIX: Iterate only over the open-source models
    for key in ['e5_large', 'bge_m3', 'indic_bert']:
        if key in MODEL_CONFIG:
            name = MODEL_CONFIG[key]['name']
            try:
                # Handle indic-bert specifically to add a pooling layer
                if key == 'indic_bert':
                    word_embedding_model = models.Transformer(name)
                    pooling_model = models.Pooling(word_embedding_model.get_word_embedding_dimension())
                    MODELS[key] = SentenceTransformer(modules=[word_embedding_model, pooling_model], device=device)
                    print(f"{name} model initialized with explicit MEAN pooling.")
                else:
                    MODELS[key] = SentenceTransformer(name, device=device)
                    print(f"{name} model initialized.")
            except Exception as e:
                print(f"Failed to initialize {name} model: {e}")
                MODELS[key] = None

    print("Model initialization complete.")


def generate_embeddings_for_paragraph(para_tuple: Tuple[str, str]) -> Dict[str, Any]:
    para_id, para_text = para_tuple
    document = {"document_id": para_id, "text_content": para_text}

    if MODELS.get('google'):
        try:
            embedding_values = MODELS['google'].get_embeddings([para_text])[0].values
            # FIX: Normalize the Google vector before indexing
            embedding_np = np.array(embedding_values, dtype=np.float32)
            norm = np.linalg.norm(embedding_np)
            normalized_embedding = (embedding_np / norm).tolist()
            document[MODEL_CONFIG['google']['field']] = normalized_embedding
        except Exception as e:
            print(f"Error with Google model on doc {para_id}: {e}")

    for key in ['e5_large', 'bge_m3', 'indic_bert']:
        if MODELS.get(key):
            embedding = MODELS[key].encode(para_text, normalize_embeddings=True)
            document[MODEL_CONFIG[key]['field']] = embedding.tolist()

    return document

def bulk_index_to_opensearch(client: OpenSearch, documents: List[Dict[str, Any]], index_name: str):
    if not client:
        print("OpenSearch client not available. Skipping indexing.")
        return
    print(f"Starting bulk indexing of {len(documents)} documents into '{index_name}'...")
    actions = [{"_index": index_name, "_id": doc["document_id"], "_source": doc} for doc in documents]
    try:
        success, failed = helpers.bulk(client, actions, chunk_size=100, request_timeout=60)
        print(f"Successfully indexed {success} documents.")
        if failed:
            print(f"Failed to index {len(failed)} documents.")
    except Exception as e:
        print(f"An error occurred during bulk indexing: {e}")

def load_paragraphs(fname):
    with open(fname, 'r', encoding='utf-8') as file:
        raw_content = file.read()
    para_tuple = []
    paragraphs = raw_content.split("---")
    for i, para in enumerate(paragraphs):
        para_text = para.strip()
        if para_text:
            para_id = f"{os.path.basename(fname)}_{i}"
            para_tuple.append((para_id, para_text))
    return para_tuple

def main():
    client = get_opensearch_client()
    delete_index()
    create_index_if_not_exists()
    initialize_models()
    fname = "/Users/r0j08wt/cataloguesearch/documentai_output/SS01.txt"
    paragraphs = load_paragraphs(fname)
    print(f"Generating embeddings for {len(paragraphs)} paragraphs using 8 threads...")
    processed_docs = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_to_para = {executor.submit(generate_embeddings_for_paragraph, para): para for para in paragraphs}
        for future in tqdm(concurrent.futures.as_completed(future_to_para), total=len(paragraphs)):
            try:
                processed_docs.append(future.result())
            except Exception as e:
                para_id = future_to_para[future][0]
                print(f"Error processing paragraph {para_id}: {e}")
    if processed_docs:
        bulk_index_to_opensearch(client, processed_docs, OPENSEARCH_INDEX_NAME)
    print("Process finished.")

if __name__ == "__main__":
    main()
