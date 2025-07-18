import os
import json
import hashlib
import sys
from datetime import datetime

from backend.processor.pdf_processor import PDFProcessor
from backend.utils import json_dump, json_dumps
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
                 index_state: IndexState,
                 pdf_processor: PDFProcessor,
                 scan_time: str):
        self._file_path = os.path.abspath(file_path)
        self._base_pdf_folder = config.BASE_PDF_PATH
        self._index_state = index_state
        self._output_text_base_dir = config.BASE_TEXT_PATH
        self._pdf_processor = pdf_processor
        self._images_folder = config.TMP_IMAGES_PATH
        self._scan_time = scan_time

    def get_metadata(self) -> dict:
        # Collect all folders from base to PDF's folder
        folders = []
        current = os.path.dirname(self._file_path)
        config = {}
        while True:
            folders = [current] + folders
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
            config_data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(sorted_config_str.encode('utf-8')).hexdigest()

    def _save_state(self, document_id: str, state: dict):
        # TODO(rajatjain): Reimplement this.
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
        current_config = self.get_metadata()
        current_config_hash = self._get_config_hash(current_config)

        should_full_reindex = False
        should_metadata_reindex = False

        if not last_state:
            should_full_reindex = True
        elif current_file_checksum != last_state["file_checksum"]:
            should_full_reindex = True
        elif current_config_hash != last_state["config_hash"]:
            should_metadata_reindex = True
        else:
            log_handle.info(f"No changes detected for {self._file_path}. Skipping.")
            return

        if should_full_reindex:
            try:
                output_text_dir = self._get_output_text_dir()
                # Process PDF (OCR, page-wise text, bookmarks)
                page_text_paths, bookmarks = self.pdf_processor.process_pdf(
                    self._file_path, output_text_dir
                )
                # Index into OpenSearch
                self.indexing_module.index_document(
                    document_id, self._file_name,
                    page_text_paths, current_config, bookmarks,
                    reindex_metadata_only=False
                )
            except Exception as e:
                log_handle.error(f"Failed to full index document {pdf_file_path}: {e}")
        elif should_metadata_reindex:
            try:
                # For metadata-only, we don't need to re-process PDF pages, just update metadata
                # We still need bookmarks, so re-extract them.
                bookmarks = self._pdf_processor.fetch_bookmarks(self._file_path)
                self.indexing_module.index_document(
                    document_id, self._file_name, [], current_config, bookmarks,
                    reindex_metadata_only=True
                )
            except Exception as e:
                log_handle.error(f"Failed to metadata re-index document {pdf_file_path}: {e}")

        self._save_state(
            document_id,
            {
                "file_path": self._file_path,
                "last_indexed_timestamp": self._scan_time,
                "file_checksum": current_file_checksum,
                "config_hash": current_config_hash
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
                 indexing_module: IndexingEmbeddingModule,
                 pdf_processor: PDFProcessor,
                 index_state : IndexState):
        """
        Initializes the Discovery module with configuration, indexing module, and PDF processor.

        Args:
            config (Config): Configuration instance containing settings for discovery.
            indexing_module (IndexingEmbeddingModule): Instance responsible for indexing documents.
            pdf_processor (PDFProcessor): Instance responsible for processing PDF files.
        """
        self._config = config
        self.indexing_module = indexing_module
        self.pdf_processor = pdf_processor
        self._index_state = index_state

        # Ensure required components are initialized
        if not self.indexing_module:
            log_handle.critical("IndexingEmbeddingModule not provided. Exiting.")
            sys.exit(1)
        if not self.pdf_processor:
            log_handle.critical("PDFProcessor not provided. Exiting.")
            sys.exit(1)

        self.base_pdf_folder = self._config.BASE_PDF_PATH
        self.output_text_base_dir = self._config.BASE_TEXT_PATH

        # Ensure output directories exist
        os.makedirs(self.base_pdf_folder, exist_ok=True)
        os.makedirs(self.output_text_base_dir, exist_ok=True)

        self.indexing_module.create_index_if_not_exists() # Ensure index is ready
        log_handle.info(f"DiscoveryModule initialized for base folder: {self.base_pdf_folder}")


    def scan_and_index(self):
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
                    logging.verbose(f"Skipping file {file_name} (not a PDF)")
                    continue
                pdf_file_path = os.path.abspath(os.path.join(root, file_name))

                single_file_processor = SingleFileProcessor(
                    config=self._config,
                    file_path=pdf_file_path,
                    index_state=self._index_state,
                    pdf_processor=self.pdf_processor,
                    scan_time=current_scan_time
                )
                single_file_processor.process()


        # Remove state for files that no longer exist in the base folder
        documents_to_remove = []

        for doc_id in self.indexed_files_state.keys():
            if doc_id not in files_found_in_scan:
                documents_to_remove.append(doc_id)
                log_handle.info(f"Document {self.indexed_files_state[doc_id].get('file_path', doc_id)} no longer exists. Consider removing from index.")
                # TODO: Implement logic to remove documents from OpenSearch if they are deleted from file system
                # This would involve querying OpenSearch for chunks with this document_id and deleting them.
                # self.indexing_module.delete_document_from_index(document_id) # Needs to be implemented in IndexingEmbeddingModule

        self._index_state.garbage_collect()

        log_handle.info(f"Scan and index process completed. Start: {current_scan_time}, End: {datetime.now().isoformat()}")