from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict
import os
import sys

# Add the backend directory to the Python path to import config
backend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from config import Config

router = APIRouter(prefix="/eval", tags=["evaluation"])

class PathsResponse(BaseModel):
    base_pdf_path: str
    base_text_path: str
    base_ocr_path: str

@router.get("/paths", response_model=PathsResponse)
async def get_evaluation_paths():
    """
    Get the base paths for evaluation from the configuration.
    """
    try:
        # Initialize config (assuming it's already loaded)
        config = Config("configs/config.yaml")
        
        return PathsResponse(
            base_pdf_path=config.BASE_PDF_PATH,
            base_text_path=config.BASE_TEXT_PATH,
            base_ocr_path=config.BASE_OCR_PATH
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading configuration: {str(e)}")