"""
Utility functions for loading and merging scan_config.json files.

This module provides shared functionality for loading scan configuration
from hierarchical scan_config.json files in the PDF directory structure.
"""

import os
import json
import logging

import fitz

log_handle = logging.getLogger(__name__)


def get_scan_config(file_path: str, base_pdf_folder: str) -> dict:
    """
    Loads scan_config for a given PDF file by merging scan_config.json files
    from the directory hierarchy.

    The function walks up from the PDF file's directory to the base_pdf_folder,
    collecting and merging scan_config.json files along the way. File-specific
    settings override default settings.

    Args:
        file_path: Absolute path to the PDF file
        base_pdf_folder: Absolute path to the base PDF folder

    Returns:
        dict: Merged scan configuration with keys:
            - header_prefix: List of header prefixes to identify headers/footers
            - header_regex: List of regex patterns to identify headers/footers
            - question_prefix: List of prefixes that mark question lines
            - answer_prefix: List of prefixes that mark answer lines
            - page_list: List of page ranges to process
            - typo_list: List of typos to correct
            - crop: Dictionary of cropping settings
            - psm: Page segmentation mode (optional)
            - start_page: Starting page number (optional)
            - end_page: Ending page number (optional)
            - file_url: URL for the file (optional)
    """
    try:
        with fitz.open(file_path) as doc:
            num_pages = doc.page_count
    except Exception as e:
        log_handle.error(f"Could not open PDF {file_path} to get page count: {e}")
        num_pages = 0

    # Collect all folders from base to PDF's folder
    folders = []
    current = os.path.dirname(file_path)
    while True:
        folders = [current] + folders
        log_handle.debug(f"Current folder: {current}, Base folder: {base_pdf_folder}")
        if os.path.samefile(current, base_pdf_folder):
            break
        parent = os.path.dirname(current)
        current = parent

    # Start with baseline configuration.
    scan_meta = {
        "header_prefix": [],
        "header_regex": [],
        "page_list": [],
        "typo_list": [],
        "crop": {},
        "question_prefix": [],
        "answer_prefix": []
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
                scan_meta["question_prefix"].extend(default_config.get("question_prefix", []))
                scan_meta["answer_prefix"].extend(default_config.get("answer_prefix", []))

                # Update crop settings from default config
                if "crop" in default_config:
                    scan_meta["crop"].update(default_config["crop"])

                # Update PSM setting from default config (if present)
                if "psm" in default_config:
                    scan_meta["psm"] = default_config["psm"]

            except (json.JSONDecodeError, IOError) as e:
                log_handle.warning(f"Could not read or parse {scan_config_path}: {e}")

    # Layer 2: Apply file-specific settings, which override defaults.
    filename = os.path.splitext(os.path.basename(file_path))[0]
    file_config = scan_config_data.get(filename, {})
    if file_config:
        scan_meta["header_prefix"].extend(file_config.get("header_prefix", []))
        scan_meta["header_regex"].extend(file_config.get("header_regex", []))
        scan_meta["question_prefix"].extend(file_config.get("question_prefix", []))
        scan_meta["answer_prefix"].extend(file_config.get("answer_prefix", []))
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

        # Update PSM setting from file-specific config (overrides default)
        if "psm" in file_config:
            scan_meta["psm"] = file_config["psm"]

    return scan_meta