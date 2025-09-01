import os
import logging
from pathlib import Path
import fitz  # PyMuPDF

# Set environment variable to use fork instead of spawn for multiprocessing
os.environ["TOKENIZERS_PARALLELISM"] = "false"

ROOT_DIR = Path(__file__).parent.parent

from scratch.prod_setup import prod_setup
from backend.config import Config
from backend.crawler.pdf_processor import PDFProcessor

log_handle = logging.getLogger(__name__)

def main():
    # Setup logging first
    prod_setup(console_only=True)
    
    log_handle.info("Starting OCR processing...")
    # Initialize PDF Processor with config
    config = Config()
    processor = PDFProcessor(config)
    
    # Base directory for PDF files
    base_dir = ROOT_DIR / "tests" / "data" / "pdfs"
    base_output_dir = ROOT_DIR / "tests" / "data" / "text"
    
    # Create output directory if it doesn't exist
    base_output_dir.mkdir(parents=True, exist_ok=True)

    log_handle.info(f"base_dir: {base_dir}")
    
    # Process all PDF files in the base directory
    for pdf_file in base_dir.glob("*.pdf"):
        # Determine language based on filename
        if "_hindi.pdf" in pdf_file.name:
            language = "hi"  # Use language code as expected by PDFProcessor
        elif "_gujarati.pdf" in pdf_file.name:
            language = "gu"  # Use language code as expected by PDFProcessor
        else:
            continue  # Skip files that don't match the pattern
        
        # Define output directory (ignore extension)
        output_dir = base_output_dir / pdf_file.stem
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get total number of pages from PDF
        with fitz.open(str(pdf_file)) as doc:
            total_pages = len(doc)
        
        # Define scan_config with start_page=1, end_page=total_num_pages and language
        scan_config = {
            "start_page": 1,
            "end_page": total_pages,
            "language": language
        }
        
        log_handle.info(f"Processing {pdf_file.name} as {language} language...")
        
        # Call process_pdf function
        processor.process_pdf(
            pdf_path=str(pdf_file),
            output_dir=str(output_dir),
            scan_config=scan_config
        )

if __name__ == "__main__":
    main()