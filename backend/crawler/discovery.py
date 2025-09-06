import os
import json
import hashlib
import sys
import traceback
import uuid
import logging
from datetime import datetime

import fitz

from backend.crawler.pdf_processor import PDFProcessor
from backend.utils import json_dumps
from backend.config import Config
from backend.crawler.index_generator import IndexGenerator
from backend.crawler.index_state import IndexState

# Setup logging for this module
log_handle = logging.getLogger(__name__)

class SingleFileProcessor:
    def __init__(self, config: Config,
                 file_path: str,
                 indexing_mod: IndexGenerator,
                 index_state: IndexState,
                 pdf_processor: PDFProcessor,
                 scan_time: str):
        self._file_path = os.path.abspath(file_path)
        self._base_pdf_folder = config.BASE_PDF_PATH
        self._indexing_module = indexing_mod
        self._index_state = index_state
        self._output_text_base_dir = config.BASE_TEXT_PATH
        self._output_ocr_base_dir = config.BASE_OCR_PATH
        self._pdf_processor = pdf_processor
        self._scan_time = scan_time

    def _get_metadata(self, scan_config: dict = None) -> dict:
        """
        Loads all the metadata for the file. This metadata will be indexed in OpenSearch
        """
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

        # Add file_url from scan_config if provided
        if scan_config:
            config["file_url"] = scan_config.get("file_url", "")

        return config

    def _get_scan_config(self) -> dict:
        """
        Loads all the scan_config for this file. This config will be passed on to
        PDFProcessor to extract relevant text, ignore headers/footers etc.
        """
        try:
            with fitz.open(self._file_path) as doc:
                num_pages = doc.page_count
        except Exception as e:
            log_handle.error(f"Could not open PDF {self._file_path} to get page count: {e}")
            num_pages = 0

        # Collect all folders from base to PDF's folder
        folders = []
        current = os.path.dirname(self._file_path)
        while True:
            folders = [current] + folders
            log_handle.debug(f"Current folder: {current}, Base folder: {self._base_pdf_folder}")
            if os.path.samefile(current, self._base_pdf_folder):
                break
            parent = os.path.dirname(current)
            current = parent

        # Start with baseline configuration.
        scan_meta = {
            "header_prefix": [],
            "header_regex": [],
            "page_list": [],
            "typo_list": [],
            "crop": {}
        }

        # Merge scan_config.json from each folder, starting from base directory
        scan_config_data = {}
        for folder in folders:
            scan_config_path = os.path.join(folder, "scan_config.json")
            if os.path.exists(scan_config_path):
                log_handle.info(f"found scan_config_path: {scan_config_path}")
                try:
                    with open(scan_config_path, "r", encoding="utf-8") as f:
                        scan_config_data = json.load(f)

                    # Apply default settings from this config file
                    default_config = scan_config_data.get("default", {})
                    scan_meta["header_prefix"].extend(default_config.get("header_prefix", []))
                    scan_meta["header_regex"].extend(default_config.get("header_regex", []))
                    scan_meta["page_list"].extend(default_config.get("page_list", []))
                    scan_meta["typo_list"].extend(default_config.get("typo_list", []))

                    # Update crop settings from default config
                    if "crop" in default_config:
                        scan_meta["crop"].update(default_config["crop"])

                except (json.JSONDecodeError, IOError) as e:
                    log_handle.warning(f"Could not read or parse {scan_config_path}: {e}")

        # Layer 2: Apply file-specific settings, which override defaults.
        filename = os.path.splitext(os.path.basename(self._file_path))[0]
        file_config = scan_config_data.get(filename, {})
        if file_config:
            scan_meta["header_prefix"].extend(file_config.get("header_prefix", []))
            scan_meta["header_regex"].extend(file_config.get("header_regex", []))
            scan_meta["file_url"] = file_config.get("file_url", "")
            if file_config.get("start_page") and file_config.get("end_page"):
                # Page numbers are typically file-specific.
                scan_meta["start_page"] = file_config.get("start_page", 1)
                scan_meta["end_page"] = file_config.get("end_page", num_pages)
            if file_config.get("page_list"):
                scan_meta["page_list"].extend(file_config.get("page_list"))

            # Update crop settings from file-specific config (overrides defaults)
            if "crop" in file_config:
                scan_meta["crop"].update(file_config["crop"])

        return scan_meta

    def _get_config_hash(self, config_data: dict) -> str:
        """Generates a SHA256 hash for a config dictionary."""
        # Ensure consistent order for hashing by sorting keys
        sorted_config_str = json_dumps(
            config_data, sort_keys=True)
        return hashlib.sha256(sorted_config_str.encode('utf-8')).hexdigest()

    def _save_state(self, document_id: str, state: dict):
        """Saves the current indexed state to a JSON file."""
        self._index_state.update_state(document_id, state)

    def _get_page_list(self, scan_config):
        all_pages = set()

        # Add pages from the list of ranges
        pages_list = scan_config.get("page_list", [])
        for page in pages_list:
            start = page.get("start")
            end = page.get("end")

            # Add pages if both start and end exist
            if start is not None and end is not None:
                all_pages.update(range(start, end + 1))

        # Add pages from the top-level range
        start_page = scan_config.get("start_page")
        end_page = scan_config.get("end_page")

        if start_page is not None and end_page is not None:
            all_pages.update(range(start_page, end_page + 1))

        # 3. Return the final sorted list of unique pages
        return sorted(list(all_pages))

    def process(self):
        relative_pdf_path = os.path.relpath(self._file_path, self._base_pdf_folder)
        document_id = str(uuid.uuid5(uuid.NAMESPACE_URL, relative_pdf_path))

        scan_config = self._get_scan_config()
        pages_list = self._get_page_list(scan_config)
        current_ocr_checksum = self._index_state.calculate_ocr_checksum(
            relative_pdf_path, pages_list)

        last_state = self._index_state.get_state(document_id)

        # Check if OCR text files already exist for this OCR configuration
        if last_state and last_state.get("ocr_checksum") == current_ocr_checksum:
            log_handle.info(f"OCR text files already exist for {self._file_path}. Skipping.")
            return

        try:
            file_metadata = self._get_metadata(scan_config)
            scan_config["language"] = file_metadata.get("language", "hi")

            language = scan_config.get("language", "hi")
            ret = self._pdf_processor.process_pdf(
                self._file_path, scan_config, pages_list)

            if ret:
                self._save_state(
                    document_id,
                    {
                        "file_path": relative_pdf_path,
                        "last_indexed_timestamp": self._scan_time,
                        "file_checksum": "",
                        "config_hash": "",
                        "ocr_checksum": current_ocr_checksum
                    }
                )

            log_handle.info(f"Generated OCR text files for {self._file_path}")

        except Exception as e:
            traceback.print_exc()
            log_handle.error(f"Failed to generate OCR text for {self._file_path}: {e}")
            return


    def index(self, dry_run=False):
        relative_path = os.path.relpath(self._file_path, self._base_pdf_folder)
        document_id = str(uuid.uuid5(uuid.NAMESPACE_URL, relative_path))
        log_handle.info(f"Indexing PDF: {self._file_path} ID: {document_id}")

        output_ocr_dir = f"{self._output_ocr_base_dir}/{os.path.splitext(relative_path)[0]}"
        output_text_dir = f"{self._output_text_base_dir}/{os.path.splitext(relative_path)[0]}"

        # Check if OCR directory exists
        if not os.path.exists(output_ocr_dir):
            log_handle.error(
                f"OCR directory does not exist for {self._file_path}. Run process() first.")
            return

        scan_config = self._get_scan_config()
        pages_list = self._get_page_list(scan_config)

        # Check if all required OCR pages exist
        missing_pages = []
        for page_num in pages_list:
            ocr_file = f"{output_ocr_dir}/page_{page_num:04d}.txt"
            if not os.path.exists(ocr_file):
                missing_pages.append(page_num)

        if missing_pages:
            log_handle.error(
                f"Missing OCR files for pages {missing_pages} in {self._file_path}. "
                f"Run process() first.")
            return

        # Calculate current checksums for comparison
        file_metadata = self._get_metadata(scan_config)
        current_config_hash = self._get_config_hash(file_metadata)
        current_ocr_checksum = self._index_state.calculate_ocr_checksum(relative_path, pages_list)

        index_state = self._index_state.get_state(document_id)

        # Check if indexing is needed based on config changes or OCR changes
        if (index_state and
            index_state.get("config_hash") == current_config_hash and
            index_state.get("ocr_checksum") == current_ocr_checksum):
            log_handle.info(f"No changes detected for {self._file_path}. Not indexing.")
            return

        bookmarks = self._pdf_processor.fetch_bookmarks(self._file_path)
        self._indexing_module.index_document(
            document_id, relative_path, output_ocr_dir, output_text_dir,
            pages_list, file_metadata, scan_config, bookmarks, False,
            dry_run
        )

        if not dry_run:
            self._save_state(document_id, {
                "file_path": relative_path,
                "last_indexed_timestamp": self._scan_time,
                "file_checksum": "",
                "config_hash": current_config_hash,
                "index_checksum": "",
                "ocr_checksum": current_ocr_checksum
            })
            log_handle.info(f"Completed indexing of {self._file_path}")


class Discovery:
    """
    The Discovery Module is responsible for scanning, preprocessing, and preparing PDF data
    and its associated metadata for ingestion into OpenSearch. It manages the lifecycle
    of documents from raw PDF to processed text and metadata, ensuring only new or
    changed content is re-indexed.
    """
    def __init__(self, config: Config,
                 indexing_mod: IndexGenerator,
                 pdf_processor: PDFProcessor,
                 index_state : IndexState):
        """
        Initializes the Discovery module with configuration, indexing module, and PDF processor.

        Args:
            config (Config): Configuration instance containing settings for discovery.
            indexing_mod (IndexGenerator): Instance responsible for indexing documents.
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
        self.base_text_folder = self._config.BASE_TEXT_PATH
        self.base_ocr_folder = self._config.BASE_OCR_PATH

        # Ensure output directories exist
        os.makedirs(self.base_pdf_folder, exist_ok=True)
        os.makedirs(self.base_text_folder, exist_ok=True)
        os.makedirs(self.base_ocr_folder, exist_ok=True)

        log_handle.info(f"DiscoveryModule initialized for base folder: {self.base_pdf_folder}")


    def _get_directories_to_crawl(self):
        """
        Recursively builds a list of directories to crawl.
        Skips directories containing a '_ignore' file and their subdirectories.

        Returns:
            list: List of directory paths to crawl
        """
        directories_to_crawl = []

        def _recurse_directory(directory_path):
            """Recursively traverse directory and collect paths to crawl"""
            # Check if this directory should be ignored
            ignore_file_path = os.path.join(directory_path, "_ignore")
            if os.path.exists(ignore_file_path):
                log_handle.info(f"Ignoring directory {directory_path} due to _ignore file")
                return  # Skip this directory and all its subdirectories

            # Add current directory to crawl list
            directories_to_crawl.append(directory_path)

            # Recursively process subdirectories
            try:
                for item in os.listdir(directory_path):
                    # Skip directories that start with a dot (like .git, .vscode, etc.)
                    if item.startswith('.'):
                        continue
                    item_path = os.path.join(directory_path, item)
                    if os.path.isdir(item_path):
                        _recurse_directory(item_path)
            except (OSError, PermissionError) as e:
                log_handle.warning(f"Cannot access directory {directory_path}: {e}")

        # Start recursion from base folder
        _recurse_directory(self.base_pdf_folder)

        return directories_to_crawl

    def crawl(self, process=False, index=False, dry_run=False):
        """
        Scans the base PDF folder, identifies new or changed files/configs,
        and triggers indexing or re-indexing.

        Uses recursive directory traversal with _ignore file support.
        """
        current_scan_time = datetime.now().isoformat()
        log_handle.info(f"Starting scan process... at {current_scan_time}")
        log_handle.info(f"Base PDF path: {self.base_pdf_folder}")
        log_handle.info(f"process: {process}, index: {index}")

        if not process and not index:
            return

        # First, recursively create list of directories to crawl
        directories_to_crawl = self._get_directories_to_crawl()
        log_handle.info(f"Found {len(directories_to_crawl)} directories to crawl")

        # Second, crawl each directory for PDF files
        for directory in directories_to_crawl:
            try:
                files = os.listdir(directory)
            except (OSError, PermissionError) as e:
                log_handle.warning(f"Cannot access directory {directory}: {e}")
                continue

            for file_name in files:
                if not file_name.lower().endswith(".pdf"):
                    continue
                pdf_file_path = os.path.abspath(os.path.join(directory, file_name))

                single_file_processor = SingleFileProcessor(
                    config=self._config,
                    file_path=pdf_file_path,
                    indexing_mod=self._indexing_module,
                    index_state=self._index_state,
                    pdf_processor=self._pdf_processor,
                    scan_time=current_scan_time
                )
                if process:
                    log_handle.info(f"Processing PDF file {file_name}")
                    single_file_processor.process()

                if index:
                    if dry_run:
                        log_handle.info(f"[DRY RUN] Would index file {file_name}")
                    else:
                        log_handle.info(f"Indexing file {file_name}")
                    single_file_processor.index(dry_run)

        self._index_state.garbage_collect(self.base_pdf_folder)

        # TODO(rajatjain): Delete files from OpenSearch index if they no longer exist in the
        # filesystem.

        log_handle.info(
            f"Scan and index process completed. Start: {current_scan_time}, "
            f"End: {datetime.now().isoformat()}")