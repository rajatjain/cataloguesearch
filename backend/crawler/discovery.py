import os
import json
import hashlib
import sys
import traceback
from datetime import datetime

from backend.crawler.pdf_processor import PDFProcessor
from backend.utils import json_dumps
import uuid # For generating unique document IDs
import logging

from backend.config import Config
from backend.index.embedding_module import IndexingEmbeddingModule
from backend.crawler.index_state import IndexState

# Setup logging for this module
log_handle = logging.getLogger(__name__)

class SingleFileProcessor:
    def __init__(self, config: Config,
                 file_path: str,
                 indexing_mod: IndexingEmbeddingModule,
                 index_state: IndexState,
                 pdf_processor: PDFProcessor,
                 scan_time: str):
        self._file_path = os.path.abspath(file_path)
        self._base_pdf_folder = config.BASE_PDF_PATH
        self._indexing_module = indexing_mod
        self._index_state = index_state
        self._output_text_base_dir = config.BASE_TEXT_PATH
        self._pdf_processor = pdf_processor
        self._images_folder = config.TMP_IMAGES_PATH
        self._scan_time = scan_time

    def _get_metadata(self) -> dict:
        # Collect all folders from base to PDF's folder
        folders = []
        current = os.path.dirname(self._file_path)
        config = {}
        while True:
            folders = [current] + folders
            log_handle.debug(f"Current folder: {current}, Base folder: {self._base_pdf_folder}")
            if os.path.samefile(current, self._base_pdf_folder):
                break
            parent = os.path.dirname(current)
            current = parent

        # Merge config.json from each folder
        for folder in folders:
            config_path = os.path.join(folder, "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config.update(json.load(f))

        # Merge file-specific config
        file_base, _ = os.path.splitext(self._file_path)
        file_config_path = f"{file_base}_config.json"
        if os.path.exists(file_config_path):
            with open(file_config_path, "r", encoding="utf-8") as f:
                config.update(json.load(f))

        return config

    def _get_file_checksum(self) -> str:
        """Generates a SHA256 checksum for a file's content."""
        hasher = hashlib.sha256()
        try:
            with open(self._file_path, 'rb') as f:
                while chunk := f.read(8192): # Read in 8KB chunks
                    hasher.update(chunk)
            return hasher.hexdigest()
        except FileNotFoundError:
            log_handle.warning(f"File not found for checksum calculation: {self._file_path}")
            return ""
        except Exception as e:
            log_handle.error(f"Error calculating checksum for {self._file_path}: {e}")
            return ""

    def _get_config_hash(self, config_data: dict) -> str:
        """Generates a SHA256 hash for a config dictionary."""
        # Ensure consistent order for hashing by sorting keys
        sorted_config_str = json_dumps(
            config_data, sort_keys=True)
        return hashlib.sha256(sorted_config_str.encode('utf-8')).hexdigest()

    def _save_state(self, document_id: str, state: dict):
        """Saves the current indexed state to a JSON file."""
        self._index_state.update_state(document_id, state)

    def _get_output_text_dir(self):
        relative_path = os.path.relpath(self._file_path, self._base_pdf_folder)
        return relative_path

    def process(self):
        relative_pdf_path = os.path.relpath(self._file_path, self._base_pdf_folder)
        document_id = str(uuid.uuid5(uuid.NAMESPACE_URL, relative_pdf_path))
        log_handle.info(f"Processing PDF: {self._file_path} (ID: {document_id})")

        last_state = self._index_state.get_state(document_id)

        current_file_checksum = self._get_file_checksum()
        file_metadata = self._get_metadata()
        file_metadata_hash = self._get_config_hash(file_metadata)

        should_full_reindex = False
        should_metadata_reindex = False

        if not last_state:
            should_full_reindex = True
        elif current_file_checksum != last_state["file_checksum"]:
            should_full_reindex = True
        elif file_metadata_hash != last_state["config_hash"]:
            should_metadata_reindex = True
        else:
            log_handle.info(f"No changes detected for {self._file_path}. Skipping.")
            return

        if should_full_reindex:
            try:
                output_text_dir = "%s/%s" % (
                    self._output_text_base_dir,
                    os.path.splitext(relative_pdf_path)[0])
                os.makedirs(output_text_dir, exist_ok=True)
                # Process PDF (OCR, page-wise text, bookmarks)
                log_handle.info(
                    f"file_path: {self._file_path}, output_text_dir: {output_text_dir}, images_folder: {self._images_folder}"
                )
                page_text_paths, bookmarks = self._pdf_processor.process_pdf(
                    self._file_path, output_text_dir, self._images_folder, file_metadata
                )
                log_handle.info(f"Processed PDF: {self._file_path}")
                log_handle.verbose(f"page_text_paths: {page_text_paths}, bookmarks: {bookmarks}")
                # Index into OpenSearch
                relative_path = os.path.relpath(self._file_path, self._base_pdf_folder)
                self._indexing_module.index_document(
                    document_id, relative_path,
                    page_text_paths, file_metadata, bookmarks,
                    reindex_metadata_only=False
                )
                log_handle.info(f"Full re-index of {self._file_path} completed successfully.")
            except Exception as e:
                traceback.print_exc()
                log_handle.error(f"Failed to full index document {self._file_path}: {e}")
        elif should_metadata_reindex:
            try:
                # For metadata-only, we don't need to re-process PDF pages, just update metadata
                # We still need bookmarks, so re-extract them.
                bookmarks = self._pdf_processor.fetch_bookmarks(self._file_path)
                self._indexing_module.index_document(
                    document_id, self._file_path, [], file_metadata, bookmarks,
                    reindex_metadata_only=True
                )
                log_handle.info(f"Metadata re-index of {self._file_path} completed successfully.")
            except Exception as e:
                traceback.print_exc()
                log_handle.error(f"Failed to metadata re-index document {self._file_path}: {e}")

        self._save_state(
            document_id,
            {
                "file_path": self._file_path,
                "last_indexed_timestamp": self._scan_time,
                "file_checksum": current_file_checksum,
                "config_hash": file_metadata_hash
            }
        )

class Discovery:
    """
    The Discovery Module is responsible for scanning, preprocessing, and preparing PDF data
    and its associated metadata for ingestion into OpenSearch. It manages the lifecycle
    of documents from raw PDF to processed text and metadata, ensuring only new or
    changed content is re-indexed.
    """
    def __init__(self, config: Config,
                 indexing_mod: IndexingEmbeddingModule,
                 pdf_processor: PDFProcessor,
                 index_state : IndexState):
        """
        Initializes the Discovery module with configuration, indexing module, and PDF processor.

        Args:
            config (Config): Configuration instance containing settings for discovery.
            indexing_mod (IndexingEmbeddingModule): Instance responsible for indexing documents.
            pdf_processor (PDFProcessor): Instance responsible for processing PDF files.
        """
        self._config = config
        self._indexing_module = indexing_mod
        self._pdf_processor = pdf_processor
        self._index_state = index_state

        # Ensure required components are initialized
        if not self._indexing_module:
            log_handle.critical("IndexingEmbeddingModule not provided. Exiting.")
            sys.exit(1)
        if not self._pdf_processor:
            log_handle.critical("PDFProcessor not provided. Exiting.")
            sys.exit(1)

        self.base_pdf_folder = self._config.BASE_PDF_PATH
        self.output_text_base_dir = self._config.BASE_TEXT_PATH

        # Ensure output directories exist
        os.makedirs(self.base_pdf_folder, exist_ok=True)
        os.makedirs(self.output_text_base_dir, exist_ok=True)

        log_handle.info(f"DiscoveryModule initialized for base folder: {self.base_pdf_folder}")


    def crawl(self):
        """
        Scans the base PDF folder, identifies new or changed files/configs,
        and triggers indexing or re-indexing.
        """
        current_scan_time = datetime.now().isoformat()
        log_handle.info(f"Starting scan and index process... at {current_scan_time}")

        files_found_in_scan = set()

        for root, _, files in os.walk(self.base_pdf_folder):
            for file_name in files:
                if not file_name.lower().endswith(".pdf"):
                    log_handle.verbose(f"Skipping file {file_name} (not a PDF)")
                    continue
                pdf_file_path = os.path.abspath(os.path.join(root, file_name))

                single_file_processor = SingleFileProcessor(
                    config=self._config,
                    file_path=pdf_file_path,
                    indexing_mod=self._indexing_module,
                    index_state=self._index_state,
                    pdf_processor=self._pdf_processor,
                    scan_time=current_scan_time
                )
                single_file_processor.process()

        self._index_state.garbage_collect()

        # TODO(rajatjain): Delete files from OpenSearch index if they no longer exist in the filesystem.

        log_handle.info(f"Scan and index process completed. Start: {current_scan_time}, End: {datetime.now().isoformat()}")
