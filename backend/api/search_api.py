import logging
import os
import time
from typing import Any, Dict, List

from fastapi import Body, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware

from backend.common.embedding_models import get_embedding_model_factory
from backend.common.opensearch import get_opensearch_client, get_metadata
from backend.config import Config
from backend.search.index_searcher import IndexSearcher
from backend.utils import json_dumps, JSONResponse, log_memory_usage
from utils.logger import setup_logging, VERBOSE_LEVEL_NUM, METRICS_LEVEL_NUM
from backend.api.feedback_api import router as feedback_router
from eval.api import router as eval_router

log_handle = logging.getLogger(__name__)

# --- FastAPI Application Setup ---
app = FastAPI(
    title="Catalogue Search API",
    description="API for searching through catalogue documents and serving the frontend.",
    version="1.0.0"
)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include Routers ---
app.include_router(feedback_router, prefix="/api")
app.include_router(eval_router, prefix="/api")

@app.on_event("startup")
async def initialize():
    """
    Initializes the config and other expensive objects once at startup.
    Stores them in the application state.
    """
    # Setup logging
    logs_dir = os.environ.get("LOGS_DIR", "logs")
    setup_logging(
        logs_dir=logs_dir, console_level=VERBOSE_LEVEL_NUM,
        file_level=VERBOSE_LEVEL_NUM,
        console_only=False)
    log_handle.info("Logging setup complete.")

    # Load configuration
    config_path = os.environ.get("CONFIG_PATH", "configs/config.yaml")
    config = Config(config_path)
    app.state.config = config
    log_handle.info("Configuration loaded.")

    # Initialize OpenSearch client (the client itself is managed by opensearch.py module)
    get_opensearch_client(config)
    log_handle.info("OpenSearch client initialized.")

    # Load embedding model
    app.state.embedding_model = get_embedding_model_factory(config)
    log_handle.info(f"Embedding model {config.EMBEDDING_MODEL_NAME} with type {config.EMBEDDING_MODEL_TYPE} loaded.")

    # Initialize IndexSearcher (which may load the reranker)
    app.state.index_searcher = IndexSearcher(config)
    log_handle.info("IndexSearcher initialized.")

    # Initialize and populate metadata cache
    app.state.metadata_cache = {
        "data": None,
        "timestamp": 0,
        "ttl": 1800  # 30 minutes cache TTL
    }
    try:
        log_handle.info("Populating metadata cache at startup...")
        metadata = get_metadata(config)
        # Filter metadata for each language
        filtered_metadata = {}
        for language, lang_metadata in metadata.items():
            filtered_metadata[language] = {
                key: values for key, values in lang_metadata.items()
                if key in config.FILTERED_METADATA_FIELDS
            }
        app.state.metadata_cache["data"] = filtered_metadata
        app.state.metadata_cache["timestamp"] = time.time()
        log_handle.info(f"Metadata cache populated with {json_dumps(metadata)}")
    except Exception as e:
        log_handle.exception(f"Failed to populate metadata cache at startup: {e}")

    # Log memory usage after initialization
    log_memory_usage()

@app.get("/api/metadata", response_model=Dict[str, List[str]])
async def get_metadata_api(request: Request):
    """
    Returns metadata about the indexed documents.
    Uses in-memory cache with 30-minute TTL, computes from OpenSearch if cache is expired.
    """
    try:
        config = Config()
        current_time = time.time()
        cache = request.app.state.metadata_cache

        # Check if cache is valid
        if (cache["data"] is not None and
            current_time - cache["timestamp"] < cache["ttl"]):
            log_handle.info("Retrieving metadata from in-memory cache")
            return JSONResponse(content=cache["data"], status_code=200)

        # Cache is expired or empty, fetch from OpenSearch
        log_handle.info("Cache expired or empty, fetching metadata from OpenSearch")
        metadata = get_metadata(request.app.state.config)

        # Filter to only return Granth, Anuyog, Year fields for each language
        filtered_metadata = {}
        for language, lang_metadata in metadata.items():
            filtered_metadata[language] = {
                key: values for key, values in lang_metadata.items()
                if key in config.FILTERED_METADATA_FIELDS
            }

        # Update cache with filtered data
        cache["data"] = filtered_metadata
        cache["timestamp"] = current_time

        log_handle.info(f"Filtered metadata retrieved and cached: {len(filtered_metadata)} keys found")
        return JSONResponse(content=filtered_metadata, status_code=200)
    except Exception as e:
        log_handle.exception(f"Error retrieving metadata: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@app.post("/api/cache/invalidate")
async def invalidate_cache(request: Request):
    """
    Invalidates the metadata cache by clearing cached data.
    """
    try:
        cache = request.app.state.metadata_cache
        cache["data"] = None
        cache["timestamp"] = 0
        
        log_handle.info("Metadata cache invalidated successfully")
        return {"message": "Cache invalidated successfully", "status": "success"}
    except Exception as e:
        log_handle.exception(f"Error invalidating cache: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

class SearchRequest(BaseModel):
    """
    Pydantic model for the search request payload.
    """
    query: str = Field(..., example="Bangalore city history")
    language: str = Field(..., description="Language of the query.", example="hindi")
    exact_match: bool = Field(False, description="Use exact phrase matching instead of regular match.")
    exclude_words: List[str] = Field([], description="List of words to exclude from search results.")
    categories: Dict[str, List[str]] = Field({}, example={"author": ["John Doe"], "bookmarks": ["important terms"]})
    page_size: int = Field(20, ge=1, le=100, description="Number of results per page.")
    page_number: int = Field(1, ge=1, description="Page number for pagination.")
    enable_reranking: bool = Field(True, description="Enable re-ranking for better relevance.")

@app.post("/api/search", response_model=Dict[str, Any])
async def search(request: Request, request_data: SearchRequest = Body(...)):
    """
    Handles search requests to the OpenSearch index.
    Performs lexical and vector searches, collates results, and returns paginated output.
    """
    index_searcher = request.app.state.index_searcher
    embedding_model = request.app.state.embedding_model

    keywords = request_data.query
    exact_match = request_data.exact_match
    exclude_words = request_data.exclude_words
    categories = request_data.categories
    page_size = request_data.page_size
    page_number = request_data.page_number
    enable_reranking = request_data.enable_reranking
    language = request_data.language

    has_advanced_options = exact_match or (exclude_words and len(exclude_words) > 0)
    is_lexical_query = (index_searcher.is_lexical_query(keywords) or
                        has_advanced_options)

    try:
        # Start timing for metrics
        start_time = time.time()

        # Get client IP - check X-Forwarded-For and X-Real-IP headers first (for nginx proxy)
        client_ip = (
            request.headers.get("x-real-ip") or
            request.headers.get("x-forwarded-for", "").split(",")[0].strip() or
            getattr(request.client, 'host', 'unknown') if request.client else 'unknown'
        )

        log_handle.info(f"Received search request: keywords='{keywords}', "
                        f"exact_match={exact_match}, exclude_words={exclude_words}, "
                        f"categories={categories}, page={page_number}, size={page_size}, "
                        f"language={language}, enable_reranking={enable_reranking}")

        if is_lexical_query:
            # For lexical queries: only perform lexical search
            lexical_results, lexical_total_hits = index_searcher.perform_lexical_search(
                keywords=keywords,
                exact_match=exact_match,
                exclude_words=exclude_words,
                categories=categories,
                detected_language=language,
                page_size=page_size,
                page_number=page_number
            )
            log_handle.info(f"Lexical search returned {len(lexical_results)} results (total: {lexical_total_hits}).")

            # If no lexical results, get spelling suggestions
            if lexical_total_hits == 0:
                suggestions = index_searcher.get_spelling_suggestions(
                    index_name=request.app.state.config.OPENSEARCH_INDEX_NAME,
                    text=keywords,
                    language=language,
                    min_score=0.6,
                    num_suggestions=3
                )

                response = {
                    "total_results": 0,
                    "page_size": page_size,
                    "page_number": page_number,
                    "results": [],
                    "vector_results": [],
                    "total_vector_results": 0,
                    "suggestions": suggestions
                }

                # Log metrics for zero results case
                latency_ms = round((time.time() - start_time) * 1000, 2)
                escaped_query = keywords.replace(',', ';').replace('"', "'").replace('\n', ' ').replace('\r', '')
                escaped_categories = str(categories).replace(',', ';').replace('"', "'")

                log_handle.metrics(
                    f"{client_ip},{escaped_query},lexical,{exact_match},{escaped_categories},{language},"
                    f"{enable_reranking},{page_size},{page_number},{latency_ms},0"
                )

                log_handle.info(f"No lexical results found for lexical query '{keywords}'. Returning {len(suggestions)} suggestions.")
                return JSONResponse(content=response, status_code=200)

            # Skip vector search for lexical queries
            vector_results = []
            vector_total_hits = 0
        else:
            # For non-lexical queries: only perform vector search
            lexical_results = []
            lexical_total_hits = 0

            query_embedding = embedding_model.get_embedding(keywords)
            if not query_embedding:
                log_handle.warning("Could not generate embedding for query. Vector search skipped.")
                vector_results = []
                vector_total_hits = 0
            else:
                vector_results, vector_total_hits = index_searcher.perform_vector_search(
                    keywords=keywords,
                    embedding=query_embedding,
                    categories=categories,
                    page_size=page_size,
                    page_number=page_number,
                    language=language,
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
            "total_vector_results": vector_total_hits
        }

        # Calculate latency and log metrics
        latency_ms = round((time.time() - start_time) * 1000, 2)
        search_type = "lexical" if is_lexical_query else "vector"
        total_results = lexical_total_hits + vector_total_hits

        # Escape query for CSV (replace commas with semicolons, quotes with single quotes)
        escaped_query = keywords.replace(',', ';').replace('"', "'").replace('\n', ' ').replace('\r', '')
        escaped_categories = str(categories).replace(',', ';').replace('"', "'")

        # Log metrics in CSV format: client_ip,query,search_type,exact_match,categories,language,enable_reranking,page_size,page_number,latency_ms,total_results
        log_handle.metrics(
            f"{client_ip},{escaped_query},{search_type},{exact_match},{escaped_categories},{language},"
            f"{enable_reranking},{page_size},{page_number},{latency_ms},{total_results}"
        )

        log_handle.info(f"Search response: {json_dumps(response)}")
        return JSONResponse(content=response, status_code=200)

    except Exception as e:
        log_handle.exception(f"An error occurred during search request processing: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@app.get("/api/similar-documents/{doc_id}", response_model=Dict[str, Any])
async def get_similar_documents(request: Request, doc_id: str, language: str = Query("hi", enum=["hi", "gu", "en"])):
    """
    Finds and returns documents that are semantically similar to the given document ID.
    """
    try:
        index_searcher = request.app.state.index_searcher
        log_handle.info(f"Received request for similar documents to doc_id: {doc_id}")

        similar_docs, total_similar = index_searcher.find_similar_by_id(
            doc_id=doc_id,
            language=language,
            size=10
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

@app.get("/api/context/{chunk_id}", response_model=Dict[str, Any])
async def get_context(request: Request, chunk_id: str, language: str = Query("hi", enum=["hi", "gu", "en"])):
    """
    Fetches the context (previous, current, next paragraph) for a given chunk_id.
    """
    try:
        index_searcher = request.app.state.index_searcher
        log_handle.info(f"Received request for context for chunk_id: {chunk_id}")
        context_data = index_searcher.get_paragraph_context(chunk_id=chunk_id, language=language)
        if not context_data.get("current"):
            raise HTTPException(status_code=404, detail="Context not found for the given ID.")
        return JSONResponse(content=context_data, status_code=200)
    except Exception as e:
        log_handle.exception(f"An error occurred while fetching context: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")
