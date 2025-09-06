#!/usr/bin/env python3

import os
import tempfile
import logging
import time
from typing import List, Dict, Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from starlette.background import BackgroundTask
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pytesseract
from PIL import Image
import cv2
import numpy as np
import uuid
import zipfile
from pdf2image import convert_from_path
import shutil
import concurrent.futures
import threading

from .extract_text import extract_and_split_paragraphs

# Setup logging
logging.basicConfig(level=logging.INFO)
log_handle = logging.getLogger(__name__)

# --- FastAPI Application Setup ---
app = FastAPI(
    title="OCR Utils API",
    description="API for OCR processing of images and PDFs with text extraction and bounding box detection.",
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

# --- In-memory job tracking & Concurrency Control ---
jobs: Dict[str, Dict] = {}
progress_lock = threading.Lock()
job_semaphore = threading.Semaphore(2)  # Allow 2 concurrent jobs

# --- Response Models ---
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

# --- Helper function for parallel processing ---
def process_single_page(page_image, language: str, page_num: int, page_filename: str, output_dir: str, job_id: str):
    job_info = jobs.get(job_id)
    if not job_info or job_info.get("cancel_requested"):
        return

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_image_file:
            page_image.save(temp_image_file.name, "PNG")
            paragraphs = extract_and_split_paragraphs(temp_image_file.name, lang=language)
            page_text = "\n\n----\n\n".join(paragraphs)
            with open(os.path.join(output_dir, page_filename), "w") as text_file:
                text_file.write(page_text)
        
        with progress_lock:
            if jobs.get(job_id):
                jobs[job_id]["progress"] += 1
    except Exception as e:
        log_handle.error(f"Error processing page {page_num} for job {job_id}: {e}")

# --- Background Task ---
def process_pdf_in_background(file_path: str, language: str, job_id: str, original_filename: str):
    job_info = jobs[job_id]
    output_dir = None
    
    with job_semaphore:
        try:
            job_info["status"] = "preparing"
            output_dir = tempfile.mkdtemp()
            job_info["output_dir"] = output_dir

            images = convert_from_path(file_path)
            job_info["status"] = "processing"
            
            total_pages = len(images)
            job_info["total_pages"] = total_pages

            page_format_string = "page_%04d.txt" if total_pages >= 1000 else "page_%03d.txt"

            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = [
                    executor.submit(
                        process_single_page,
                        img,
                        language,
                        i + 1,
                        page_format_string % (i + 1),
                        output_dir,
                        job_id
                    ) for i, img in enumerate(images)
                ]

                for future in concurrent.futures.as_completed(futures):
                    if job_info.get("cancel_requested"):
                        executor.shutdown(wait=False, cancel_futures=True)
                        job_info["status"] = "canceled"
                        log_handle.info(f"Job {job_id} was canceled.")
                        return

            if job_info.get("cancel_requested"):
                job_info["status"] = "canceled"
                return

            base_filename = os.path.splitext(original_filename)[0]
            zip_filename = f"{base_filename}_extracted.zip"
            job_info["zip_filename"] = zip_filename
            
            zip_path = os.path.join(output_dir, zip_filename)
            with zipfile.ZipFile(zip_path, "w") as zipf:
                for i in range(total_pages):
                    page_filename = page_format_string % (i + 1)
                    page_path = os.path.join(output_dir, page_filename)
                    if os.path.exists(page_path):
                        zipf.write(page_path, page_filename)
            
            job_info["zip_path"] = zip_path
            job_info["status"] = "completed"
            job_info["completion_time"] = time.time()

        except Exception as e:
            log_handle.error(f"Job {job_id} failed: {e}")
            job_info["status"] = "failed"
            job_info["error"] = str(e)
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
            if job_info["status"] != "completed" and output_dir and os.path.exists(output_dir):
                shutil.rmtree(output_dir)

@app.on_event("startup")
async def initialize():
    """Initialize the OCR API server."""
    log_handle.info("OCR Utils API server starting up...")
    try:
        version = pytesseract.get_tesseract_version()
        log_handle.info(f"Tesseract version {version} detected and ready")
    except Exception as e:
        log_handle.warning(f"Tesseract check failed: {e}")

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

@app.post("/api/ocr/batch", response_model=BatchJobResponse)
async def process_ocr_batch(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF file to process"),
    language: str = Form("hin", description="Language code for OCR (hin, guj, eng)")
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported for batch processing")

    background_tasks.add_task(cleanup_old_jobs)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_path = temp_file.name

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "total_pages": 0,
        "zip_path": None,
        "zip_filename": None,
        "output_dir": None,
        "error": None,
        "cancel_requested": False,
        "completion_time": None
    }

    background_tasks.add_task(process_pdf_in_background, temp_path, language, job_id, file.filename)
    return BatchJobResponse(job_id=job_id)

@app.post("/api/ocr/batch/cancel/{job_id}")
async def cancel_batch_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] in ["completed", "failed", "canceled"]:
        raise HTTPException(status_code=400, detail=f"Job is already in a final state ({job['status']}).")
    job["cancel_requested"] = True
    job["status"] = "canceling"
    return {"message": "Job cancellation requested."}

@app.get("/api/ocr/batch/status/{job_id}", response_model=BatchStatusResponse)
async def get_batch_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return BatchStatusResponse(
        status=job["status"], 
        progress=job["progress"], 
        total_pages=job["total_pages"], 
        zip_filename=job.get("zip_filename"),
        error=job["error"]
    )

@app.get("/api/ocr/batch/download/{job_id}")
async def download_batch_result(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Job is not yet complete. Current status: {job['status']}")
    zip_path = job.get("zip_path")
    zip_filename = job.get("zip_filename", "extracted_text.zip")
    if not zip_path or not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="Result file not found. It may have been cleaned up.")
    from fastapi.responses import FileResponse
    background_task = BackgroundTask(cleanup_job_files, job_id=job_id)
    return FileResponse(zip_path, media_type="application/zip", filename=zip_filename, background=background_task)

@app.post("/api/ocr", response_model=OCRResponse)
async def process_ocr(
    image: UploadFile = File(..., description="Image file to process"),
    language: str = Form("hin", description="Language code for OCR (hin, guj, eng)"),
    crop_top: int = Form(0, description="Percentage to crop from top (0-50)"),
    crop_bottom: int = Form(0, description="Percentage to crop from bottom (0-50)")
):
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
        if crop_top > 0 or crop_bottom > 0:
            width, height = pil_image.size
            top_crop_pixels = int(height * crop_top / 100)
            bottom_crop_pixels = int(height * crop_bottom / 100)
            crop_box = (0, top_crop_pixels, width, height - bottom_crop_pixels)
            pil_image = pil_image.crop(crop_box)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as cropped_temp:
                pil_image.save(cropped_temp.name)
                cropped_temp_path = cropped_temp.name
        text_paragraphs = extract_and_split_paragraphs(cropped_temp_path, lang=language)
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
        text_boxes.sort(key=lambda box: (box.y, box.x))
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
        extracted_text = '\n\n----\n\n'.join([p.text for p in paragraphs])
        log_handle.info(f"OCR processing completed: {len(paragraphs)} paragraphs, {len(text_boxes)} text boxes")
        return OCRResponse(text=extracted_text, boxes=text_boxes, paragraphs=paragraphs, language=language)
    finally:
        try:
            os.unlink(temp_path)
            if cropped_temp_path != temp_path:
                os.unlink(cropped_temp_path)
        except Exception as cleanup_error:
            log_handle.warning(f"Failed to cleanup temporary files: {cleanup_error}")

@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint to verify Tesseract installation."""
    try:
        version = pytesseract.get_tesseract_version()
        return HealthResponse(status="healthy", tesseract_version=str(version))
    except Exception as e:
        log_handle.error(f"Health check failed: {e}")
        return HealthResponse(status="unhealthy", error=str(e))

if __name__ == '__main__':
    import uvicorn
    print("Starting OCR Utils API Server...")
    print("API available at: http://localhost:8500")
    print("Health check at: http://localhost:8500/api/health")
    print("API docs at: http://localhost:8500/docs")
    uvicorn.run(app, host="0.0.0.0", port=8500, log_level="info")
