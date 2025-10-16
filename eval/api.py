from fastapi import APIRouter, HTTPException, File, UploadFile, Form, BackgroundTasks
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
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
import requests
from enum import Enum

# OCR-specific imports
from PIL import Image

# Add the backend directory to the Python path to import config
backend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Add the scratch directory to import para_gen
scratch_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scratch', 'para_gen')
if scratch_path not in sys.path:
    sys.path.insert(0, scratch_path)

from config import Config
from backend.crawler.pdf_processor import PDFProcessor
from backend.crawler.markdown_parser import MarkdownParser
from backend.common.scan_config import get_scan_config
from .ocr import get_ocr_service
from para_gen import process_image_to_paragraphs

log_handle = logging.getLogger(__name__)

# --- Language mapping for PDFProcessor compatibility ---
def get_pdf_processor_language(api_language: str) -> str:
    """Convert API language codes to PDFProcessor language codes"""
    language_map = {"hin": "hi", "guj": "gu", "eng": "en"}
    return language_map.get(api_language, "hi")

class OCRMode(str, Enum):
    """Defines the available OCR processing modes."""
    PSM6 = "psm6"
    PSM3 = "psm3"
    ADVANCED = "advanced"

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

# --- Scripture Eval Request Model ---
class ScriptureEvalRequest(BaseModel):
    relative_path: str

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

@router.get("/ocr/scan-config")
async def get_file_scan_config(relative_path: str):
    """
    Get the scan_config for a PDF file from the base PDF folder.
    This returns merged configuration from scan_config.json files in the directory hierarchy.

    Args:
        relative_path: Relative path to the PDF file from the base PDF folder

    Returns:
        dict: Scan configuration with header_prefix, header_regex, page_list, crop, psm, etc.
    """
    try:
        config = Config("configs/config.yaml")
        base_pdf_folder = config.BASE_PDF_PATH
        file_path = os.path.join(base_pdf_folder, relative_path)

        # Validate file exists
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"File not found: {relative_path}")

        # Get scan config using the utility function
        scan_config = get_scan_config(file_path, base_pdf_folder)

        return scan_config

    except HTTPException:
        raise
    except Exception as e:
        log_handle.error(f"Error getting scan config: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting scan config: {str(e)}")

@router.post("/ocr", response_model=OCRResponse)
async def process_ocr(
    image: UploadFile = File(None, description="Image file to process (not needed if relative_path and page_number are provided)"),
    language: str = Form("hin", description="Language code for OCR (hin, guj, eng)"),
    crop_top: int = Form(0, description="Percentage to crop from top (0-50)"),
    crop_bottom: int = Form(0, description="Percentage to crop from bottom (0-50)"),
    mode: OCRMode = Form(
        OCRMode.PSM6,
        description='OCR processing mode. "psm6" and "psm3" use the legacy processor. '
                    '"advanced" uses the new para_gen logic (beta).'
    ),
    relative_path: Optional[str] = Form(None, description="Relative path to PDF file from base folder"),
    page_number: Optional[int] = Form(None, description="Page number to extract from PDF (1-indexed, requires relative_path)")
):
    """
    Process OCR on an image.

    Two modes of operation:
    1. Upload mode: Provide 'image' file
    2. PDF extraction mode: Provide 'relative_path' and 'page_number' to extract page from PDF directly

    If relative_path is provided, the scan_config will be loaded from scan_config.json files
    in the directory hierarchy, providing header_prefix, header_regex, and other settings.
    """
    # Validate input: either image OR (relative_path + page_number)
    if not image and not (relative_path and page_number):
        raise HTTPException(status_code=400, detail="Either provide 'image' file OR both 'relative_path' and 'page_number'")

    if image and (relative_path and page_number):
        raise HTTPException(status_code=400, detail="Provide either 'image' file OR 'relative_path'+'page_number', not both")
    if not (0 <= crop_top <= 50 and 0 <= crop_bottom <= 50):
        raise HTTPException(status_code=400, detail="Crop percentages must be between 0 and 50")

    # Determine settings based on the selected mode
    use_para_gen = (mode == OCRMode.ADVANCED)
    psm = 3 if mode == OCRMode.PSM3 else 6

    # For now, Google OCR is not supported with this endpoint.
    use_google_ocr = False

    # TODO: Google OCR not yet supported in PDFProcessor integration
    if use_google_ocr:
        raise HTTPException(status_code=400, detail="Google OCR is not supported for single-page evaluation.")

    # Build scan_config
    scan_config = {}

    # If relative_path is provided, load scan_config from hierarchy
    if relative_path:
        try:
            config = Config("configs/config.yaml")
            base_pdf_folder = config.BASE_PDF_PATH
            file_path = os.path.join(base_pdf_folder, relative_path)
            if not file_path.endswith(".pdf"):
                file_path = f"{file_path}.pdf"

            if os.path.exists(file_path):
                log_handle.info(f"getting scan_config for {file_path} and base_folder {base_pdf_folder}")
                scan_config = get_scan_config(file_path, base_pdf_folder)
                log_handle.info(f"Loaded scan_config for {relative_path}: {scan_config.keys()}")
        except Exception as e:
            log_handle.warning(f"Failed to load scan_config for {relative_path}: {e}")

    # Merge crop settings (these override scan_config crop if both present)
    if crop_top > 0 or crop_bottom > 0:
        if "crop" not in scan_config:
            scan_config["crop"] = {}
        scan_config["crop"]["top"] = crop_top
        scan_config["crop"]["bottom"] = crop_bottom

    # Map language to PDFProcessor format
    processor_language = get_pdf_processor_language(language)

    # Initialize PDF processor
    config = Config("configs/config.yaml")
    pdf_processor = PDFProcessor(config)

    # --- Determine Image Source ---
    temp_path = None
    pil_image = None
    page_num = 1
    source_description = ""

    try:
        if relative_path and page_number:
            # Mode 1: Extract page directly from PDF in base folder
            base_pdf_folder = config.BASE_PDF_PATH
            pdf_file_path = os.path.join(base_pdf_folder, relative_path)
            if not pdf_file_path.endswith(".pdf"):
                pdf_file_path = f"{pdf_file_path}.pdf"

            if not os.path.exists(pdf_file_path):
                raise HTTPException(status_code=404, detail=f"PDF file not found: {relative_path}")

            log_handle.info(f"Extracting page {page_number} from {pdf_file_path}")

            # Use PDFProcessor._get_image to extract the specified page with cropping
            images, page_numbers = pdf_processor._get_image(pdf_file_path, [page_number], scan_config)
            if not images:
                raise HTTPException(status_code=400, detail=f"Failed to extract page {page_number} from PDF")

            pil_image = images[0]
            page_num = page_numbers[0]
            source_description = f"page {page_num} from {relative_path}"

        else:
            # Mode 2: Use uploaded image file
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

            source_description = f"uploaded file {image.filename}"

        # --- OCR and Paragraph Logic ---
        if use_para_gen:
            log_handle.info(f"Processing OCR for {source_description} using para_gen logic...")
            # Map language to pytesseract format ('hin+guj')
            tesseract_lang = language.replace(' ', '+')

            # Call the new refactored function with scan_config
            generated_paragraphs, _ = process_image_to_paragraphs(
                pil_image, lang=tesseract_lang, page_num=page_num, scan_config=scan_config
            )

            # Adapt the output to the API's Paragraph model
            api_paragraphs = [Paragraph(text=p.text, boxes=[]) for p in generated_paragraphs]
            extracted_text = '\n\n----\n\n'.join([p.text for p in api_paragraphs])
            log_handle.info(f"OCR processing completed using para_gen: {len(api_paragraphs)} paragraphs")

            return OCRResponse(text=extracted_text, boxes=[], paragraphs=api_paragraphs, language=language)

        else: # Keep the original logic
            log_handle.info(f"Processing OCR for {source_description} using legacy PDFProcessor logic...")
            config = Config("configs/config.yaml")
            pdf_processor = PDFProcessor(config)
            processor_language = get_pdf_processor_language(language)

            # Use PDFProcessor._process_single_page for OCR
            processor_lang_code = pdf_processor._pytesseract_language_map[processor_language]
            _, text_paragraphs = PDFProcessor._process_single_page(
                (page_num, pil_image, processor_lang_code, psm))

            # Create paragraphs without text boxes (simplified approach)
            paragraphs = [Paragraph(text=p_text, boxes=[]) for p_text in text_paragraphs]
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
    use_google_ocr: bool = Form(False, description="Use Google Vision OCR instead of Tesseract"),
    psm: int = Form(6, description="PSM mode (3 or 6)")
):
    """
    Start batch OCR processing of a PDF file.
    Returns a job ID for tracking progress.
    """
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Please upload a PDF file")

    # Validate PSM value
    if psm not in [3, 6]:
        raise HTTPException(status_code=400, detail="PSM must be 3 or 6")

    log_handle.info(f"Starting batch OCR for {file.filename} with language={language}")

    try:
        # Read file content upfront to avoid "read of closed file" error
        file_content = await file.read()

        ocr_service = get_ocr_service()
        job_id = ocr_service.start_batch_processing(file_content, language, use_google_ocr, psm)

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

@router.post("/scripture")
async def process_scripture(request: ScriptureEvalRequest):
    """
    Process a markdown scripture file and return the parsed Granth object.
    """
    try:
        # Initialize config to get base paths
        config = Config("configs/config.yaml")

        # Construct the full path to the markdown file
        # Assuming the relative path is relative to the base markdown directory
        base_path = getattr(config, 'BASE_MARKDOWN_PATH', config.BASE_PDF_PATH)  # fallback to PDF path if markdown path not defined
        full_file_path = os.path.join(base_path, request.relative_path)

        # Validate file exists and is a markdown file
        if not os.path.exists(full_file_path):
            raise HTTPException(status_code=404, detail=f"Markdown file not found: {request.relative_path}")

        if not full_file_path.lower().endswith('.md'):
            raise HTTPException(status_code=400, detail="File must be a markdown (.md) file")

        log_handle.info(f"Processing scripture file: {full_file_path}")

        # Parse the markdown file using MarkdownParser
        # Pass the base directory so it can find config files
        parser = MarkdownParser(base_folder=base_path)
        granth = parser.parse_file(full_file_path)

        log_handle.info(f"Successfully parsed Granth: {granth._name} with {len(granth._verses)} verses")

        # Return the Granth object as HTTP response
        return granth.get_http_response()

    except HTTPException:
        raise
    except Exception as e:
        log_handle.error(f"Error processing scripture file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing scripture file: {str(e)}")

@router.get("/pdf/proxy")
async def proxy_pdf(url: str):
    """
    Proxy PDF requests to avoid CORS issues with external PDF URLs.
    """
    try:
        # Validate that this is a PDF URL
        if not url or not (url.startswith('http://') or url.startswith('https://')):
            raise HTTPException(status_code=400, detail="Invalid URL provided")

        # Add some basic security - only allow certain domains if needed
        # For now, we'll be permissive but you can add domain whitelist here

        log_handle.info(f"Proxying PDF request for: {url}")

        # Make request to external PDF
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=30, stream=True)
        response.raise_for_status()

        # Check if it's actually a PDF
        content_type = response.headers.get('content-type', '').lower()
        if 'pdf' not in content_type and not url.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="URL does not appear to be a PDF file")

        # Return the PDF content with proper headers
        return Response(
            content=response.content,
            media_type="application/pdf",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET",
                "Access-Control-Allow-Headers": "*",
                "Cache-Control": "public, max-age=3600"  # Cache for 1 hour
            }
        )

    except requests.RequestException as e:
        log_handle.error(f"Error fetching PDF from {url}: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch PDF: {str(e)}")
    except Exception as e:
        log_handle.error(f"Error proxying PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error proxying PDF: {str(e)}")