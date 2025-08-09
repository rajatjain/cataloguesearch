import logging
import os
from typing import Any, Dict, List

from fastapi import Body, FastAPI, HTTPException, Request, Query
from fastapi.responses import FileResponse
from langdetect import detect
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.common.embedding_models import get_embedding_model_factory
from backend.common.opensearch import get_opensearch_client, get_metadata
from backend.config import Config
from backend.common.language_detector import LanguageDetector
from backend.search.index_searcher import IndexSearcher
from backend.search.result_ranker import ResultRanker
from backend.utils import json_dumps
from utils.logger import setup_logging, VERBOSE_LEVEL_NUM
from backend.utils import JSONResponse
import time

log_handle = logging.getLogger(__name__)

# --- In-memory metadata cache ---
metadata_cache = {
    "data": None,
    "timestamp": 0,
    "ttl": 1800  # 30 minutes cache TTL
}

# --- FastAPI Application Setup ---
app = FastAPI(
    title="Catalogue Search API",
    description="API for searching through catalogue documents and serving the frontend.",
    version="1.0.0"
)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

def initialize():
    """Initializes the config and other variables, if required"""
    logs_dir = os.environ.get("LOGS_DIR", "logs")
    setup_logging(
        logs_dir=logs_dir, console_level=VERBOSE_LEVEL_NUM,
        file_level=VERBOSE_LEVEL_NUM,
        console_only=False)

    relative_config_path = "configs/config.yaml"
    config = Config(relative_config_path)

    # initialize opensearch client
    get_opensearch_client(config)

@app.get("/api/metadata", response_model=Dict[str, List[str]])
async def get_metadata_api():
    """
    Returns metadata about the indexed documents.
    Uses in-memory cache with 30-minute TTL, computes from OpenSearch if cache is expired.
    """
    try:
        current_time = time.time()
        
        # Check if cache is valid
        if (metadata_cache["data"] is not None and 
            current_time - metadata_cache["timestamp"] < metadata_cache["ttl"]):
            log_handle.info("Retrieving metadata from in-memory cache")
            return JSONResponse(content=metadata_cache["data"], status_code=200)
        
        # Cache is expired or empty, fetch from OpenSearch
        log_handle.info("Cache expired or empty, fetching metadata from OpenSearch")
        config = Config()
        metadata = get_metadata(config)
        
        # Update cache
        metadata_cache["data"] = metadata
        metadata_cache["timestamp"] = current_time
        
        log_handle.info(f"Metadata retrieved and cached: {len(metadata)} keys found")
        return JSONResponse(content=metadata, status_code=200)
    except Exception as e:
        log_handle.exception(f"Error retrieving metadata: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

class SearchRequest(BaseModel):
    """
    Pydantic model for the search request payload.
    """
    query: str = Field(..., example="Bangalore city history")
    proximity_distance: int = Field(30, ge=0, description="Max word distance for proximity search. Use 0 for exact phrase.")
    allow_typos: bool = Field(False, description="Allow typos in search terms.")
    categories: Dict[str, List[str]] = Field({}, example={"author": ["John Doe"], "bookmarks": ["important terms"]})
    page_size: int = Field(20, ge=1, le=100, description="Number of results per page.")
    page_number: int = Field(1, ge=1, description="Page number for pagination.")
    enable_reranking : bool = Field(True, description="Enable re-ranking for better relevance.")

@app.post("/api/search", response_model=Dict[str, Any])
async def search(request_data: SearchRequest = Body(...)):
    """
    Handles search requests to the OpenSearch index.
    Performs lexical and vector searches, collates results, and returns paginated output.
    """
    config = Config()
    index_searcher = IndexSearcher(config)
    keywords = request_data.query
    allow_typos = request_data.allow_typos
    proximity_distance = request_data.proximity_distance
    categories = request_data.categories
    page_size = request_data.page_size
    page_number = request_data.page_number
    enable_reranking = request_data.enable_reranking

    try:

        # If allow_typos is true and proximity_distance is 0 (exact phrase), change to near (10)
        if allow_typos and proximity_distance == 0:
            proximity_distance = 10
            log_handle.info(f"Changed proximity_distance from 0 to 10 because allow_typos=True")

        detected_language = LanguageDetector.detect_language(keywords)
        log_handle.info(f"Received search request: keywords='{keywords}', "
                        f"allow_typos='{allow_typos}', proximity_distance={proximity_distance}, "
                        f"categories={categories}, page={page_number}, size={page_size}, "
                        f"detected_language={detected_language}, enable_reranking={enable_reranking}")

        # Perform Lexical Search
        lexical_results = []
        lexical_total_hits = 0

        lexical_results, lexical_total_hits = index_searcher.perform_lexical_search(
            keywords=keywords,
            proximity_distance=proximity_distance,
            allow_typos=allow_typos,
            categories=categories,
            detected_language=detected_language,
            page_size=page_size,
            page_number=page_number
        )
        log_handle.info(f"Lexical search returned {len(lexical_results)} "
                        f"results (total: {lexical_total_hits}).")

        vector_results = []
        vector_total_hits = 0
        embedding_model = get_embedding_model_factory(config)
        log_handle.info(f"Using embedding model type: {config.EMBEDDING_MODEL_TYPE}")
        query_embedding = embedding_model.get_embedding(keywords)
        if not query_embedding:
            log_handle.warning("Could not generate embedding for query. Vector search skipped.")
            vector_results = []
        else:
            # For vector search, never show all results. Only the top 20 is always ok.
            vector_results, vector_total_hits = index_searcher.perform_vector_search(
                keywords=keywords,
                embedding=query_embedding,
                categories=categories,
                page_size=20,
                page_number=1,
                language=detected_language,
                rerank=enable_reranking
            )
            log_handle.info(
                f"Vector search returned {len(vector_results)} "
                f"results (total: {vector_total_hits}) with reranking={'enabled' if enable_reranking else 'disabled'}.")

        response = {
            "total_results": lexical_total_hits,
            "page_size": page_size,
            "page_number": page_number,
            "results": lexical_results,
            "vector_results": vector_results,
            "total_vector_results": len(vector_results)  # Limit this to 10 always
        }

        log_handle.info(f"Search response: {json_dumps(response)}")
        return JSONResponse(content=response, status_code=200)

    except Exception as e:
        log_handle.exception(f"An error occurred during search request processing: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@app.get("/api/similar-documents/{doc_id}", response_model=Dict[str, Any])
async def get_similar_documents(doc_id: str, language: str = Query("hi", enum=["hi", "gu", "en"])):
    """
    Finds and returns documents that are semantically similar to the given document ID.
    """
    try:
        config = Config()
        index_searcher = IndexSearcher(config)

        log_handle.info(f"Received request for similar documents to doc_id: {doc_id}")

        similar_docs, total_similar = index_searcher.find_similar_by_id(
            doc_id=doc_id,
            language=language,
            size=10  # Fetch top 10 similar documents
        )

        response = {
            "total_results": total_similar,
            "results": similar_docs
        }

        log_handle.info(f"Found {total_similar} similar documents for doc_id: {doc_id}")
        return JSONResponse(content=response, status_code=200)

    except Exception as e:
        log_handle.exception(f"An error occurred while finding similar documents: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@app.get("/context/{chunk_id}", response_model=Dict[str, Any])
async def get_context(chunk_id: str, language: str = Query("hi", enum=["hi", "gu", "en"])):
    """
    Fetches the context (previous, current, next paragraph) for a given chunk_id.
    """
    try:
        config = Config()
        index_searcher = IndexSearcher(config)
        log_handle.info(f"Received request for context for chunk_id: {chunk_id}")
        context_data = index_searcher.get_paragraph_context(chunk_id=chunk_id, language=language)
        if not context_data.get("current"):
            raise HTTPException(status_code=404, detail="Context not found for the given ID.")
        return JSONResponse(content=context_data, status_code=200)
    except Exception as e:
        log_handle.exception(f"An error occurred while fetching context: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


initialize()
