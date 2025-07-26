import logging
import os
from typing import Any, Dict, List

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from langdetect import detect
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.common.embedding_models import get_embedding_model, get_embedding
from backend.common.opensearch import get_opensearch_client, get_metadata
from backend.config import Config
from backend.crawler.index_state import IndexState
from backend.search.highlight_extractor import HighlightExtractor
from backend.common.language_detector import LanguageDetector
from backend.search.index_searcher import IndexSearcher
from backend.search.result_ranker import ResultRanker
from backend.utils import json_dumps
from utils.logger import setup_logging, VERBOSE_LEVEL_NUM

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
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# --- Static File Serving ---
frontend_build_path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "build")

app.mount(
    "/static",
    StaticFiles(directory=os.path.join(frontend_build_path, "static")),
    name="static"
)

def initialize():
    """Initializes the config and other variables, if required"""
    logs_dir = os.environ.get("LOGS_DIR", "logs")
    setup_logging(
        logs_dir=logs_dir, console_level=VERBOSE_LEVEL_NUM,
        file_level=VERBOSE_LEVEL_NUM,
        console_only=True)

    relative_config_path = "configs/config.yaml"
    config = Config(relative_config_path)

@app.get("/metadata", response_model=Dict[str, List[str]])
async def get_metadata_api():
    """
    Returns metadata about the indexed documents.
    First checks index_state cache, falls back to OpenSearch if not present.
    """
    try:
        config = Config()
        index_state = IndexState(config.SQLITE_DB_PATH)

        if index_state.has_metadata_cache():
            log_handle.info("Retrieving metadata from cache")
            metadata = index_state.get_metadata_cache()
        else:
            log_handle.info("No metadata cache found, fetching from OpenSearch")
            metadata = get_metadata(config)
            index_state.update_metadata_cache(metadata)

        log_handle.info(f"Metadata retrieved: {len(metadata)} keys found")
        return JSONResponse(content=metadata, status_code=200)
    except Exception as e:
        log_handle.exception(f"Error retrieving metadata: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

class SearchRequest(BaseModel):
    """
    Pydantic model for the search request payload.
    """
    query: str = Field(..., example="Bangalore city history")
    search_type: str = Field("strict", description="Type of search: 'strict' or 'fuzzy'.")
    proximity_distance: int = Field(30, ge=1, description="Max word distance for proximity search.")
    categories: Dict[str, List[str]] = Field({}, example={"author": ["John Doe"], "bookmarks": ["important terms"]})
    page_size: int = Field(20, ge=1, le=100, description="Number of results per page.")
    page_number: int = Field(1, ge=1, description="Page number for pagination.")


@app.post("/search", response_model=Dict[str, Any])
async def search(request_data: SearchRequest = Body(...)):
    """
    Handles search requests to the OpenSearch index.
    Performs lexical and vector searches, collates results, and returns paginated output.
    """
    config = Config()
    index_searcher = IndexSearcher(config)
    keywords = request_data.query
    search_type = request_data.search_type
    proximity_distance = request_data.proximity_distance
    categories = request_data.categories
    page_size = request_data.page_size
    page_number = request_data.page_number


    try:
        detected_language = LanguageDetector.detect_language(keywords)
        log_handle.info(f"Received search request: keywords='{keywords}', "
                        f"search_type='{search_type}', categories={categories}, page={page_number}, size={page_size}")
        log_handle.info(f"Detected language for keywords '{keywords}': {detected_language}")

        disable_lexical_search = False
        
        # TODO(rajatjain): Enable vector search when embedding model is ready.
        disable_vector_search = True

        # Perform Lexical Search
        lexical_results = []

        if not disable_lexical_search:
            lexical_results, lexical_total_hits = index_searcher.perform_lexical_search(
                keywords=keywords,
                proximity_distance=proximity_distance,
                categories=categories,
                detected_language=detected_language,
                page_size=page_size,
                page_number=page_number,
                search_type=search_type
            )
            log_handle.info(f"Lexical search returned {len(lexical_results)} "
                            f"results (total: {lexical_total_hits}).")

        vector_results = []
        if not disable_vector_search:
            model_name = config.EMBEDDING_MODEL_NAME
            log_handle.info(f"Using embedding model: {model_name}")
            query_embedding = get_embedding(model_name, keywords)
            if not query_embedding:
                log_handle.warning("Could not generate embedding for query. Vector search skipped.")
                vector_results = []
            else:
                vector_results, vector_total_hits = index_searcher.perform_vector_search(
                    embedding=query_embedding,
                    categories=categories,
                    page_size=page_size,
                    page_number=page_number,
                    language=detected_language
                )
                log_handle.info(
                    f"Vector search returned {len(vector_results)} "
                    f"results (total: {vector_total_hits}).")

        final_results, total_results = ResultRanker.collate_and_rank(
            lexical_results, vector_results, page_size, page_number
        )
        log_handle.info(f"Collation and ranking produced {len(final_results)} final results (total: {total_results}).")

        response = {
            "total_results": total_results,
            "page_size": page_size,
            "page_number": page_number,
            "results": final_results,
        }
        log_handle.info(f"Search response: {json_dumps(response, truncate_fields=['content_snippet'])}")
        return JSONResponse(content=response, status_code=200)

    except Exception as e:
        log_handle.exception(f"An error occurred during search request processing: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

initialize()

@app.get("/{full_path:path}")
async def serve_react_app(request: Request, full_path: str):
    index_path = os.path.join(frontend_build_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "Frontend not built. Run 'npm run build' in the frontend directory."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
