from fastapi import APIRouter, HTTPException, File, UploadFile, Form, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, List, Optional
import os
import sys
import tempfile
import logging
import time
import psutil
import uuid
import zipfile
import shutil
import concurrent.futures
import threading
from starlette.background import BackgroundTask

# OCR-specific imports
from PIL import Image

# Add the backend directory to the Python path to import config
backend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from config import Config
from backend.crawler.pdf_processor import PDFProcessor
from .ocr import get_ocr_service

log_handle = logging.getLogger(__name__)

# --- Language mapping for PDFProcessor compatibility ---
def get_pdf_processor_language(api_language: str) -> str:
    """Convert API language codes to PDFProcessor language codes"""
    language_map = {"hin": "hi", "guj": "gu", "eng": "en"}
    return language_map.get(api_language, "hi")

# --- Removed old job tracking - now handled by EvalOCRService ---

router = APIRouter(prefix="/eval", tags=["evaluation"])

# --- Response Models ---
class PathsResponse(BaseModel):
    base_pdf_path: str
    base_text_path: str
    base_ocr_path: str

class TextBox(BaseModel):
    x: int
    y: int
    width: int
    height: int
    text: str
    confidence: int

class Paragraph(BaseModel):
    text: str
    boxes: List[TextBox]

class OCRResponse(BaseModel):
    text: str
    boxes: List[TextBox]
    paragraphs: List[Paragraph]
    language: str

class HealthResponse(BaseModel):
    status: str
    tesseract_version: Optional[str] = None
    error: Optional[str] = None

class BatchJobResponse(BaseModel):
    job_id: str

class BatchStatusResponse(BaseModel):
    status: str
    progress: int
    total_pages: int
    zip_filename: Optional[str] = None
    error: Optional[str] = None
    elapsed_time: Optional[float] = None
    elapsed_time_formatted: Optional[str] = None

class CostCalculationRequest(BaseModel):
    total_pages: int
    use_google_ocr: bool = False

class CostCalculationResponse(BaseModel):
    cost: str
    pages: int
    currency: str = "₹"

# --- Helper Functions ---
def get_memory_usage():
    """Get current memory usage in MB"""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024

# --- API Endpoints ---

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

@router.post("/ocr", response_model=OCRResponse)
async def process_ocr(
    image: UploadFile = File(..., description="Image file to process"),
    language: str = Form("hin", description="Language code for OCR (hin, guj, eng)"),
    crop_top: int = Form(0, description="Percentage to crop from top (0-50)"),
    crop_bottom: int = Form(0, description="Percentage to crop from bottom (0-50)"),
    use_google_ocr: bool = Form(False, description="Use Google Vision OCR instead of Tesseract")
):
    """
    Process OCR on an uploaded image file using PDFProcessor.
    """
    if not image.filename:
        raise HTTPException(status_code=400, detail="No image file selected")
    if not (0 <= crop_top <= 50 and 0 <= crop_bottom <= 50):
        raise HTTPException(status_code=400, detail="Crop percentages must be between 0 and 50")
    
    # TODO: Google OCR not yet supported in PDFProcessor integration
    if use_google_ocr:
        raise HTTPException(status_code=400, detail="Google OCR not yet implemented in PDFProcessor integration")
    
    log_handle.info(f"Processing OCR for {image.filename} with language={language}, crop_top={crop_top}, crop_bottom={crop_bottom}")
    
    # Initialize PDFProcessor
    try:
        config = Config("configs/config.yaml")
        pdf_processor = PDFProcessor(config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize PDFProcessor: {str(e)}")
    
    # Build scan_config for cropping
    scan_config = {}
    if crop_top > 0 or crop_bottom > 0:
        scan_config["crop"] = {"top": crop_top, "bottom": crop_bottom}
    
    # Map language to PDFProcessor format
    processor_language = get_pdf_processor_language(language)
    
    # Save uploaded file temporarily
    temp_path = None
    try:
        # Determine file suffix based on content type
        suffix = '.pdf' if image.content_type == 'application/pdf' else '.png'
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            content = await image.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        if image.content_type == 'application/pdf':
            # Use PDFProcessor._get_image to extract first page with cropping
            images, page_numbers = pdf_processor._get_image(temp_path, [1], scan_config)
            if not images:
                raise HTTPException(status_code=400, detail="Failed to extract page from PDF")
            
            pil_image = images[0]
            page_num = page_numbers[0]
        else:
            # Load image directly and apply cropping manually
            pil_image = Image.open(temp_path)
            
            # Apply cropping if needed (for non-PDF images)
            if crop_top > 0 or crop_bottom > 0:
                width, height = pil_image.size
                top_crop_pixels = int(height * crop_top / 100)
                bottom_crop_pixels = int(height * crop_bottom / 100)
                pil_image = pil_image.crop((0, top_crop_pixels, width, height - bottom_crop_pixels))
            
            page_num = 1
        
        # Use PDFProcessor._process_single_page for OCR
        processor_lang_code = pdf_processor._pytesseract_language_map[processor_language]
        page_num_result, text_paragraphs = PDFProcessor._process_single_page((page_num, pil_image, processor_lang_code))
        
        # Create paragraphs without text boxes (simplified approach)
        paragraphs = []
        for paragraph_text in text_paragraphs:
            paragraphs.append(Paragraph(text=paragraph_text, boxes=[]))
        
        # Create final response
        extracted_text = '\n\n----\n\n'.join([p.text for p in paragraphs])
        log_handle.info(f"OCR processing completed using PDFProcessor: {len(paragraphs)} paragraphs")
        
        return OCRResponse(text=extracted_text, boxes=[], paragraphs=paragraphs, language=language)
    
    except HTTPException:
        raise
    except Exception as e:
        log_handle.error(f"OCR processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")
    finally:
        # Clean up temporary files
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception as cleanup_error:
                log_handle.warning(f"Failed to cleanup temporary file: {cleanup_error}")

@router.post("/ocr/batch", response_model=BatchJobResponse)
async def start_batch_ocr(
    file: UploadFile = File(..., description="PDF file to process"),
    language: str = Form("hin", description="Language code for OCR (hin, guj, eng)"),
    use_google_ocr: bool = Form(False, description="Use Google Vision OCR instead of Tesseract")
):
    """
    Start batch OCR processing of a PDF file.
    Returns a job ID for tracking progress.
    """
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Please upload a PDF file")
    
    log_handle.info(f"Starting batch OCR for {file.filename} with language={language}")
    
    try:
        # Read file content upfront to avoid "read of closed file" error
        file_content = await file.read()
        
        ocr_service = get_ocr_service()
        job_id = ocr_service.start_batch_processing(file_content, language, use_google_ocr)
        
        return BatchJobResponse(job_id=job_id)
        
    except Exception as e:
        log_handle.error(f"Failed to start batch OCR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start batch processing: {str(e)}")

@router.get("/ocr/batch/status/{job_id}", response_model=BatchStatusResponse)
async def get_batch_status(job_id: str):
    """
    Get the status of a batch OCR job.
    """
    try:
        ocr_service = get_ocr_service()
        job_status = ocr_service.get_job_status(job_id)
        
        if not job_status:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return BatchStatusResponse(
            status=job_status["status"],
            progress=job_status["progress"],
            total_pages=job_status["total_pages"],
            zip_filename=job_status.get("zip_filename"),
            error=job_status.get("error"),
            elapsed_time=job_status.get("elapsed_time"),
            elapsed_time_formatted=job_status.get("elapsed_time_formatted")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log_handle.error(f"Error getting job status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting job status: {str(e)}")

@router.post("/ocr/batch/cancel/{job_id}")
async def cancel_batch_job(job_id: str):
    """
    Cancel a batch OCR job.
    """
    try:
        ocr_service = get_ocr_service()
        success = ocr_service.cancel_job(job_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Job not found or cannot be cancelled")
        
        return {"message": "Job cancellation requested"}
        
    except HTTPException:
        raise
    except Exception as e:
        log_handle.error(f"Error cancelling job: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error cancelling job: {str(e)}")

@router.get("/ocr/batch/download/{job_id}")
async def download_batch_results(job_id: str):
    """
    Download the results of a completed batch OCR job as a ZIP file.
    """
    try:
        ocr_service = get_ocr_service()
        zip_path = ocr_service.get_download_path(job_id)
        
        if not zip_path:
            raise HTTPException(status_code=404, detail="Download not available. Job may not be completed or file may have been cleaned up.")
        
        job_status = ocr_service.get_job_status(job_id)
        filename = job_status.get("zip_filename", f"extracted_text_{job_id}.zip")
        
        return FileResponse(
            path=zip_path,
            filename=filename,
            media_type="application/zip"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log_handle.error(f"Error downloading results: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error downloading results: {str(e)}")

@router.post("/ocr/calculate-cost", response_model=CostCalculationResponse)
async def calculate_ocr_cost(request: CostCalculationRequest):
    """
    Calculate the cost of OCR processing.
    """
    try:
        ocr_service = get_ocr_service()
        cost_info = ocr_service.calculate_cost(request.total_pages, request.use_google_ocr)
        
        return CostCalculationResponse(**cost_info)
        
    except Exception as e:
        log_handle.error(f"Error calculating cost: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error calculating cost: {str(e)}")

# Background task to clean up old jobs
async def cleanup_old_jobs_task():
    """Background task to periodically clean up old jobs"""
    try:
        ocr_service = get_ocr_service()
        ocr_service.cleanup_old_jobs()
    except Exception as e:
        log_handle.error(f"Error during job cleanup: {str(e)}")

# Clean up old jobs when the module loads
import asyncio
try:
    asyncio.create_task(cleanup_old_jobs_task())
except Exception:
    pass  # Ignore if no event loop is running