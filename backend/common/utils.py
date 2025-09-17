"""
Common utility functions shared across the backend modules.
"""

import os
import json
import logging

log_handle = logging.getLogger(__name__)


def get_merged_config(file_path: str, base_folder: str) -> dict:
    """
    Loads hierarchical configuration for a file by merging config.json files
    from base folder up to the file's directory, plus file-specific config.
    
    Args:
        file_path: Path to the file to load config for
        base_folder: Base folder to start hierarchy from
        
    Returns:
        Merged configuration dictionary
    """
    file_path = os.path.abspath(file_path)
    base_folder = os.path.abspath(base_folder)
    
    # Collect all folders from base to file's folder
    folders = []
    current = os.path.dirname(file_path)
    
    while True:
        folders = [current] + folders
        log_handle.debug(f"Current folder: {current}, Base folder: {base_folder}")
        
        try:
            if os.path.samefile(current, base_folder):
                break
        except (OSError, FileNotFoundError):
            # If samefile fails, fall back to string comparison
            if os.path.normpath(current) == os.path.normpath(base_folder):
                break
                
        parent = os.path.dirname(current)
        if parent == current:  # Reached filesystem root
            break
        current = parent
    
    # Start with empty config
    config = {}
    
    # Merge config.json from each folder
    for folder in folders:
        config_path = os.path.join(folder, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    folder_config = json.load(f)
                    config.update(folder_config)
                    log_handle.debug(f"Loaded config from {config_path}")
            except (json.JSONDecodeError, IOError) as e:
                log_handle.warning(f"Could not read or parse {config_path}: {e}")
    
    # Merge file-specific config
    file_base, _ = os.path.splitext(file_path)
    file_config_path = f"{file_base}_config.json"
    if os.path.exists(file_config_path):
        try:
            with open(file_config_path, "r", encoding="utf-8") as f:
                file_config = json.load(f)
                config.update(file_config)
                log_handle.debug(f"Loaded file-specific config from {file_config_path}")
        except (json.JSONDecodeError, IOError) as e:
            log_handle.warning(f"Could not read or parse {file_config_path}: {e}")
    
    return config