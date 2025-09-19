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
import pytesseract
from PIL import Image
import cv2
import numpy as np
from pdf2image import convert_from_path

# Add the backend directory to the Python path to import config
backend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from config import Config

log_handle = logging.getLogger(__name__)

# --- OCR Classes (copied from ocr_utils) ---
class OCR:
    """Base class for OCR engines."""
    def extract_text(self, image_path: str, lang: str = "hin") -> List[str]:
        raise NotImplementedError

class TesseractOCR(OCR):
    """Tesseract OCR implementation."""
    def extract_text(self, image_path: str, lang: str = "hin") -> List[str]:
        try:
            config = f'--oem 3 --psm 3 -l {lang}'
            text = pytesseract.image_to_string(Image.open(image_path), config=config)
            paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
            return paragraphs if paragraphs else [""]
        except Exception as e:
            log_handle.error(f"Tesseract OCR failed: {e}")
            return [""]

class GoogleOCR(OCR):
    """Google Vision OCR implementation."""
    def extract_text(self, image_path: str, lang: str = "hin") -> List[str]:
        try:
            from google.cloud import vision
            client = vision.ImageAnnotatorClient()
            
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
            
            image = vision.Image(content=content)
            response = client.text_detection(image=image)
            texts = response.text_annotations
            
            if texts:
                full_text = texts[0].description
                paragraphs = [p.strip() for p in full_text.split('\n\n') if p.strip()]
                return paragraphs if paragraphs else [""]
            return [""]
        except Exception as e:
            log_handle.error(f"Google OCR failed: {e}")
            return [""]

# --- In-memory job tracking & Concurrency Control ---
jobs: Dict[str, Dict] = {}
progress_lock = threading.Lock()
job_semaphore = threading.Semaphore(2)  # Allow 2 concurrent jobs

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

def process_single_page(page_image, language: str, page_num: int, page_filename: str, output_dir: str, job_id: str,
                        use_google_ocr: bool = False):
    job_info = jobs.get(job_id)
    if not job_info or job_info.get("cancel_requested"):
        return

    temp_image_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_image_file:
            temp_image_path = temp_image_file.name
            page_image.save(temp_image_path, "PNG")
            
            if use_google_ocr:
                ocr_engine = GoogleOCR()
            else:
                ocr_engine = TesseractOCR()
            
            paragraphs = ocr_engine.extract_text(temp_image_path, lang=language)
            page_text = "\n\n----\n\n".join(paragraphs)
            with open(os.path.join(output_dir, page_filename), "w") as text_file:
                text_file.write(page_text)
        
        with progress_lock:
            if jobs.get(job_id):
                jobs[job_id]["progress"] += 1
    except Exception as e:
        log_handle.error(f"Error processing page {page_num} for job {job_id}: {e}")
    finally:
        # Clean up temporary image file
        if temp_image_path and os.path.exists(temp_image_path):
            try:
                os.unlink(temp_image_path)
            except Exception:
                pass

def cleanup_job_files(job_id: str):
    job = jobs.get(job_id)
    if job:
        output_dir = job.get("output_dir")
        if output_dir and os.path.exists(output_dir):
            try:
                shutil.rmtree(output_dir)
                log_handle.info(f"Cleaned up output directory for job {job_id}")
            except Exception as e:
                log_handle.error(f"Error cleaning up directory for job {job_id}: {e}")
        jobs.pop(job_id, None)
        log_handle.info(f"Removed job {job_id} from memory.")

def cleanup_old_jobs():
    now = time.time()
    TTL = 3600  # 1 hour
    jobs_to_delete = [job_id for job_id, info in jobs.items() if info["status"] == "completed" and now - info.get("completion_time", now) > TTL]
    for job_id in jobs_to_delete:
        log_handle.info(f"Cleaning up old job {job_id}")
        cleanup_job_files(job_id)

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
    Process OCR on an uploaded image file.
    """
    if not image.filename:
        raise HTTPException(status_code=400, detail="No image file selected")
    if not (0 <= crop_top <= 50 and 0 <= crop_bottom <= 50):
        raise HTTPException(status_code=400, detail="Crop percentages must be between 0 and 50")
    
    log_handle.info(f"Processing OCR for {image.filename} with language={language}, crop_top={crop_top}, crop_bottom={crop_bottom}")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
        content = await image.read()
        temp_file.write(content)
        temp_path = temp_file.name
    
    try:
        pil_image = Image.open(temp_path)
        cropped_temp_path = temp_path
        
        # Apply cropping if specified
        if crop_top > 0 or crop_bottom > 0:
            width, height = pil_image.size
            top_crop_pixels = int(height * crop_top / 100)
            bottom_crop_pixels = int(height * crop_bottom / 100)
            crop_box = (0, top_crop_pixels, width, height - bottom_crop_pixels)
            pil_image = pil_image.crop(crop_box)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as cropped_temp:
                pil_image.save(cropped_temp.name)
                cropped_temp_path = cropped_temp.name
        
        # Choose OCR engine
        if use_google_ocr:
            ocr_engine = GoogleOCR()
        else:
            ocr_engine = TesseractOCR()
        
        # Extract text paragraphs
        text_paragraphs = ocr_engine.extract_text(cropped_temp_path, lang=language)
        
        # Get text boxes using Tesseract
        opencv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        config_boxes = f'--oem 3 --psm 3 -l {language}'
        ocr_data = pytesseract.image_to_data(opencv_image, config=config_boxes, output_type=pytesseract.Output.DICT)
        
        text_boxes = []
        n_boxes = len(ocr_data['level'])
        for i in range(n_boxes):
            confidence = int(ocr_data['conf'][i])
            text_content = ocr_data['text'][i].strip()
            if confidence > 30 and text_content:
                x, y, w, h = ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i]
                text_boxes.append(TextBox(x=x, y=y, width=w, height=h, text=text_content, confidence=confidence))
        
        # Sort text boxes by position
        text_boxes.sort(key=lambda box: (box.y, box.x))
        
        # Create paragraphs with associated boxes
        paragraphs = []
        if text_paragraphs and text_boxes:
            boxes_per_paragraph = len(text_boxes) / len(text_paragraphs)
            box_index = 0
            for i, paragraph_text in enumerate(text_paragraphs):
                if i == len(text_paragraphs) - 1:
                    paragraph_boxes = text_boxes[box_index:]
                else:
                    next_box_index = int((i + 1) * boxes_per_paragraph)
                    paragraph_boxes = text_boxes[box_index:next_box_index]
                    box_index = next_box_index
                
                if paragraph_boxes:
                    paragraphs.append(Paragraph(text=paragraph_text, boxes=paragraph_boxes))
        
        # Create final response
        extracted_text = '\n\n----\n\n'.join([p.text for p in paragraphs])
        log_handle.info(f"OCR processing completed: {len(paragraphs)} paragraphs, {len(text_boxes)} text boxes")
        
        return OCRResponse(text=extracted_text, boxes=text_boxes, paragraphs=paragraphs, language=language)
    
    finally:
        # Clean up temporary files
        try:
            os.unlink(temp_path)
            if cropped_temp_path != temp_path:
                os.unlink(cropped_temp_path)
        except Exception as cleanup_error:
            log_handle.warning(f"Failed to cleanup temporary files: {cleanup_error}")