# -*- coding: utf-8 -*-
"""
This script processes a specified range of pages from a local PDF file using
Google Cloud Document AI. It uploads the PDF to a GCS bucket, extracts text
from the main paragraphs (ignoring headers and footers), saves the content
to local text files, and then cleans up by deleting the file from GCS.
"""

# ==============================================================================
# SETUP INSTRUCTIONS
# ==============================================================================
#
# 1.  **Install required libraries:**
#     Open your terminal or command prompt and run the following command:
#     pip install google-cloud-documentai google-cloud-storage
#
# 2.  **Authenticate with Google Cloud:**
#     This script uses Application Default Credentials (ADC). It will automatically
#     work if you have already logged in via the gcloud CLI using either:
#     `gcloud auth login` or `gcloud auth application-default login`
#
# 3.  **Enable APIs:**
#     Make sure you have enabled the "Document AI API" and "Cloud Storage"
#     in your Google Cloud project.
#
# 4.  **Create a Document AI Processor:**
#     - Go to the Document AI section in the Google Cloud Console.
#     - Create a processor. For this task, the "Document OCR" processor is
#       a great choice.
#     - Note down its "Processor ID".
#
# 5.  **Create a GCS Bucket:**
#     - Go to the Cloud Storage section in the Google Cloud Console.
#     - Create a new bucket. It must have a globally unique name.
#     - Note down the "Bucket Name".
#
# 6.  **Fill in the configuration below.**
#
# ==============================================================================

import os
import uuid
from typing import List, Dict

from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1 as documentai
from google.cloud import storage

# --- CONFIGURATION - PLEASE FILL THESE IN ---
PROJECT_ID = "jaincatalogue"  # Your Google Cloud project ID
# The region for your Document AI processor. "asia-south1" (Mumbai) is a good choice for India.
# Pricing may vary slightly by region, but the model is generally consistent.
LOCATION = "us"
PROCESSOR_ID = "eafa6f76ad214fd9"  # Your Document AI processor ID
GCS_BUCKET_NAME = "jaincatalogue-text"  # The GCS bucket for temporary PDF storage
# --- END OF CONFIGURATION ---


def upload_to_gcs(local_file_path: str, bucket_name: str, destination_blob_name: str) -> str:
    """
    Uploads a local file to a GCS bucket.

    Args:
        local_file_path: Path to the local file to upload.
        bucket_name: The name of the GCS bucket.
        destination_blob_name: The name of the object in the GCS bucket.

    Returns:
        The GCS URI of the uploaded file (e.g., "gs://bucket/blob").
    """
    print(f"Uploading '{local_file_path}' to GCS bucket '{bucket_name}'...")
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_filename(local_file_path)
    print("File uploaded successfully.")
    return f"gs://{bucket_name}/{destination_blob_name}"


def delete_from_gcs(bucket_name: str, blob_name: str):
    """
    Deletes a blob from a GCS bucket.

    Args:
        bucket_name: The name of the GCS bucket.
        blob_name: The name of the object to delete.
    """
    try:
        print(f"Attempting to delete '{blob_name}' from GCS bucket '{bucket_name}'...")
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.delete()
        print("Temporary GCS file deleted successfully.")
    except Exception as e:
        print(f"Error deleting GCS file: {e}. Manual cleanup may be required.")


def process_document_ai(
        project_id: str,
        location: str,
        processor_id: str,
        gcs_uri: str,
        pages_to_process: List[int],
) -> Dict[int, List[str]]:
    """
    Calls the Document AI API to process a document and extracts text from
    paragraphs, ignoring headers and footers.

    Args:
        project_id: Your Google Cloud project ID.
        location: The region of your Document AI processor.
        processor_id: The ID of your Document AI processor.
        gcs_uri: The GCS URI of the PDF file to process.
        pages_to_process: A list of page numbers to process from the PDF.

    Returns:
        A dictionary where keys are page numbers and values are lists of
        paragraph texts for that page.
    """
    print("Processing document with Document AI...")
    # You must set the api_endpoint if you use a location other than "us".
    opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
    client = documentai.DocumentProcessorServiceClient(client_options=opts)

    # The full resource name of the processor
    name = client.processor_path(project_id, location, processor_id)

    # Configure the process request
    gcs_document = documentai.GcsDocument(gcs_uri=gcs_uri, mime_type="application/pdf")
    process_options = documentai.ProcessOptions(
        individual_page_selector=documentai.ProcessOptions.IndividualPageSelector(
            pages=pages_to_process
        )
    )
    request = documentai.ProcessRequest(
        name=name,
        gcs_document=gcs_document,
        process_options=process_options,
        skip_human_review=True, # Set to False for human-in-the-loop review
    )

    # Send the request and get the result
    result = client.process_document(request=request)
    print("API call successful for this batch.")
    return result.document

def extract_paragraphs_from_document(document: documentai.Document) -> Dict[int, List[str]]:
    """
    Extracts text from paragraphs in a processed Document object.

    Args:
        document: The processed Document object from the API.

    Returns:
        A dictionary where keys are page numbers and values are lists of
        paragraph texts for that page.
    """
    processed_pages = {}
    full_text = document.text

    for page in document.pages:
        page_number = page.page_number
        paragraphs_text = []

        for paragraph in page.paragraphs:
            paragraph_text = get_text_from_layout(paragraph.layout, full_text)
            paragraphs_text.append(paragraph_text)

        processed_pages[page_number] = paragraphs_text

    return processed_pages


def get_text_from_layout(layout: documentai.Document.Page.Layout, text: str) -> str:
    """
    Extracts text from the document's full text based on the provided layout
    segments.

    Args:
        layout: A layout object from a Document AI response.
        text: The full text of the document from the response.

    Returns:
        The text segment corresponding to the layout.
    """
    text_segment = ""
    for segment in layout.text_anchor.text_segments:
        start_index = int(segment.start_index)
        end_index = int(segment.end_index)
        text_segment += text[start_index:end_index]
    return text_segment.strip()


def save_to_files(
        processed_pages: Dict[int, List[str]], scripture_name: str, output_dir: str = "output"
):
    """
    Saves the processed text into separate files for each page.

    Args:
        processed_pages: A dictionary of page numbers to paragraph texts.
        scripture_name: The name of the scripture, used for the sub-directory.
        output_dir: The root directory to save files in.
    """
    output_dir = "/Users/r0j08wt/cataloguesearch/documentai_output"
    scripture_output_dir = os.path.join(output_dir, scripture_name)
    os.makedirs(scripture_output_dir, exist_ok=True)
    print(f"Saving extracted text to '{scripture_output_dir}'...")

    for page_number, paragraphs in processed_pages.items():
        file_name = f"{scripture_name}_page_{page_number}.txt"
        file_path = os.path.join(scripture_output_dir, file_name)

        with open(file_path, "w", encoding="utf-8") as f:
            # Join paragraphs with a clear separator for easy parsing later
            f.write("\n\n---\n\n".join(paragraphs))

    print(f"Successfully saved {len(processed_pages)} files.")


def main_process(
        local_pdf_path: str, scripture_name: str, pages_to_process: List[int]
):
    """
    Main function to orchestrate the entire PDF processing workflow.

    Args:
        local_pdf_path: The path to the local PDF file.
        scripture_name: The name of the scripture (e.g., "Kalash_Tika_02").
        pages_to_process: A list of page numbers to process.
    """
    if not os.path.exists(local_pdf_path):
        print(f"ERROR: Local file not found at '{local_pdf_path}'")
        return

    # Generate a unique name for the GCS blob to avoid conflicts
    unique_id = uuid.uuid4()
    destination_blob_name = f"temp/{scripture_name}_{unique_id}.pdf"
    gcs_uri = ""

    # Define the batch size limit for the API
    BATCH_SIZE = 15
    all_processed_pages = {}

    try:
        # Step 1: Upload the local file to GCS (only once)
        gcs_uri = upload_to_gcs(local_pdf_path, GCS_BUCKET_NAME, destination_blob_name)

        # Step 2: Process the document in batches
        for i in range(0, len(pages_to_process), BATCH_SIZE):
            page_batch = pages_to_process[i:i + BATCH_SIZE]

            # Call the Document AI API for the current batch
            document = process_document_ai(
                PROJECT_ID, LOCATION, PROCESSOR_ID, gcs_uri, page_batch
            )

            # Extract paragraphs and add them to our collection
            extracted_data = extract_paragraphs_from_document(document)
            all_processed_pages.update(extracted_data)

        # Step 3: Save all collected results to local files
        if all_processed_pages:
            save_to_files(all_processed_pages, scripture_name)
        else:
            print("No pages were processed or no text was found.")

        print("\nWorkflow completed successfully!")
    except Exception as e:
        print(f"\nAn error occurred during the process: {e}")
        print("Aborting operation.")

    finally:
        # Step 4: Always attempt to delete the temporary file from GCS
        if gcs_uri:
            delete_from_gcs(GCS_BUCKET_NAME, destination_blob_name)


if __name__ == "__main__":
    # --- Example Usage ---

    # 1. Define the path to your local PDF file
    # On Windows, it might look like: "C:\\Users\\YourUser\\Documents\\Kalash Tika 02.pdf"
    # On macOS/Linux, it might look like: "/Users/youruser/Documents/Kalash Tika 02.pdf"
    LOCAL_PDF_FILE = "/Users/r0j08wt/cataloguesearch/SS01.pdf"

    # 2. Define a clean name for the scripture for file naming
    SCRIPTURE_NAME = "SS01"  # This should be a clean name without spaces or special characters

    # 3. Define the list of pages you want to process
    # Example: Process pages 26 through 590
    PAGES_TO_PROCESS = list(range(164, 189))

    # Run the main processing workflow
    main_process(LOCAL_PDF_FILE, SCRIPTURE_NAME, PAGES_TO_PROCESS)
