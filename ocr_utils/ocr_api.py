#!/usr/bin/env python3

import os
import tempfile
import logging
from typing import List
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pytesseract
from PIL import Image
import cv2
import numpy as np

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
    tesseract_version: str = None
    error: str = None

@app.on_event("startup")
async def initialize():
    """Initialize the OCR API server."""
    log_handle.info("OCR Utils API server starting up...")
    
    # Test Tesseract installation
    try:
        version = pytesseract.get_tesseract_version()
        log_handle.info(f"Tesseract version {version} detected and ready")
    except Exception as e:
        log_handle.warning(f"Tesseract check failed: {e}")

@app.post("/api/ocr", response_model=OCRResponse)
async def process_ocr(
    image: UploadFile = File(..., description="Image file to process"),
    language: str = Form("hin", description="Language code for OCR (hin, guj, eng)"),
    crop_top: int = Form(0, description="Percentage to crop from top (0-50)"),
    crop_bottom: int = Form(0, description="Percentage to crop from bottom (0-50)")
):
    """Process OCR on uploaded image with optional cropping."""
    try:
        if not image.filename:
            raise HTTPException(status_code=400, detail="No image file selected")
        
        # Validate crop parameters
        if crop_top < 0 or crop_top > 50:
            raise HTTPException(status_code=400, detail="crop_top must be between 0 and 50")
        if crop_bottom < 0 or crop_bottom > 50:
            raise HTTPException(status_code=400, detail="crop_bottom must be between 0 and 50")
        
        log_handle.info(f"Processing OCR for {image.filename} with language={language}, crop_top={crop_top}, crop_bottom={crop_bottom}")
        
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
            content = await image.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        try:
            # Load image using PIL
            pil_image = Image.open(temp_path)
            cropped_temp_path = temp_path  # Initialize to avoid scope issues
            
            # Apply cropping if specified
            if crop_top > 0 or crop_bottom > 0:
                width, height = pil_image.size
                
                # Calculate crop dimensions
                top_crop_pixels = int(height * crop_top / 100)
                bottom_crop_pixels = int(height * crop_bottom / 100)
                
                # Ensure we don't crop too much
                top_crop_pixels = min(top_crop_pixels, height // 3)
                bottom_crop_pixels = min(bottom_crop_pixels, height // 3)
                
                # Crop the image (left, top, right, bottom)
                crop_box = (0, top_crop_pixels, width, height - bottom_crop_pixels)
                pil_image = pil_image.crop(crop_box)
                
                # Save cropped image to temporary file for extract_and_split_paragraphs
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as cropped_temp:
                    pil_image.save(cropped_temp.name)
                    cropped_temp_path = cropped_temp.name
            else:
                cropped_temp_path = temp_path
            
            # Use the improved extract_and_split_paragraphs function
            text_paragraphs = extract_and_split_paragraphs(cropped_temp_path, lang=language)
            
            # Convert PIL image to OpenCV format for bounding box extraction
            opencv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            
            # Get OCR data with bounding boxes
            config_boxes = f'--oem 3 --psm 3 -l {language}'
            ocr_data = pytesseract.image_to_data(
                opencv_image, 
                config=config_boxes, 
                output_type=pytesseract.Output.DICT
            )
            
            # Extract text boxes with their positions
            text_boxes = []
            n_boxes = len(ocr_data['level'])
            for i in range(n_boxes):
                confidence = int(ocr_data['conf'][i])
                text_content = ocr_data['text'][i].strip()
                
                # Only include text with reasonable confidence
                if confidence > 30 and text_content:
                    x = ocr_data['left'][i]
                    y = ocr_data['top'][i]
                    width = ocr_data['width'][i]
                    height = ocr_data['height'][i]
                    
                    text_boxes.append(TextBox(
                        x=x,
                        y=y,
                        width=width,
                        height=height,
                        text=text_content,
                        confidence=confidence
                    ))
            
            # Sort text boxes by vertical position (top to bottom), then horizontal (left to right)
            text_boxes.sort(key=lambda box: (box.y, box.x))
            
            # Now create paragraphs by distributing text boxes across text_paragraphs
            paragraphs = []
            if text_paragraphs and text_boxes:
                # Calculate roughly how many boxes per paragraph
                boxes_per_paragraph = len(text_boxes) / len(text_paragraphs)
                
                box_index = 0
                for i, paragraph_text in enumerate(text_paragraphs):
                    # Calculate how many boxes this paragraph should get
                    if i == len(text_paragraphs) - 1:
                        # Last paragraph gets all remaining boxes
                        paragraph_boxes = text_boxes[box_index:]
                    else:
                        # Regular distribution
                        next_box_index = int((i + 1) * boxes_per_paragraph)
                        paragraph_boxes = text_boxes[box_index:next_box_index]
                        box_index = next_box_index
                    
                    if paragraph_boxes:
                        paragraphs.append(Paragraph(
                            text=paragraph_text,
                            boxes=paragraph_boxes
                        ))
            
            # Create combined text for backward compatibility
            extracted_text = '\n\n----\n\n'.join([p.text for p in paragraphs])
            
            log_handle.info(f"OCR processing completed: {len(paragraphs)} paragraphs, {len(text_boxes)} text boxes")
            
            return OCRResponse(
                text=extracted_text,
                boxes=text_boxes,
                paragraphs=paragraphs,
                language=language
            )
            
        finally:
            # Clean up temporary files
            try:
                os.unlink(temp_path)
                if cropped_temp_path != temp_path:
                    os.unlink(cropped_temp_path)
            except Exception as cleanup_error:
                log_handle.warning(f"Failed to cleanup temporary files: {cleanup_error}")
            
    except Exception as e:
        log_handle.error(f"OCR processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")

@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint to verify Tesseract installation."""
    try:
        # Test Tesseract installation
        version = pytesseract.get_tesseract_version()
        return HealthResponse(
            status="healthy",
            tesseract_version=str(version)
        )
    except Exception as e:
        log_handle.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            error=str(e)
        )

if __name__ == '__main__':
    import uvicorn
    print("Starting OCR Utils API Server...")
    print("API available at: http://localhost:8500")
    print("Health check at: http://localhost:8500/api/health")
    print("API docs at: http://localhost:8500/docs")
    uvicorn.run(app, host="0.0.0.0", port=8500, log_level="info")