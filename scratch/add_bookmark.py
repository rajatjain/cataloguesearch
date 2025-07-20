import tempfile

import fitz
import logging
import hashlib
import os
import tempfile

log_handle = logging.getLogger(__name__)

def get_file_checksum(file_path: str) -> str:
    """Generates a SHA256 checksum for a file's content."""
    hasher = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192): # Read in 8KB chunks
                hasher.update(chunk)
        return hasher.hexdigest()
    except FileNotFoundError:
        log_handle.warning(f"File not found for checksum calculation: {file_path}")
        return ""
    except Exception as e:
        log_handle.error(f"Error calculating checksum for {file_path}: {e}")
        return ""


def add_bookmark_to_pdf(pdf_path, bookmark_name, page_number):
    doc = None
    # Define a temporary path for the new file
    temp_pdf_path = tempfile.mkstemp(suffix=".temp.pdf")[1]

    try:
        doc = fitz.open(pdf_path)
        toc = doc.get_toc()

        # Add the new bookmark
        toc.append([1, bookmark_name, page_number])

        # Update the document's table of contents
        doc.set_toc(toc)

        # Save the changes to the temporary file (this is a full rewrite)
        doc.save(temp_pdf_path, garbage=4, deflate=True, clean=True)

    except Exception as e:
        print(f"An error occurred during PDF modification: {e}")
        # If the temp file was created, clean it up
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
        return  # Exit the function on error
    finally:
        if doc:
            doc.close()

    try:
        # If saving was successful, replace the original file with the new one
        os.replace(temp_pdf_path, pdf_path)
        print(f"Successfully added bookmark '{bookmark_name}' to page {page_number}.")
        print(f"The file '{pdf_path}' has been updated.")
    except Exception as e:
        print(f"An error occurred during file replacement: {e}")


file = "/Users/r0j08wt/Downloads/bangalore_hindi.pdf"
print(f"file: {file}, checksum: {get_file_checksum(file)}")

add_bookmark_to_pdf(file, "new_bookmark", 1)
print(f"file: {file}, checksum: {get_file_checksum(file)}")