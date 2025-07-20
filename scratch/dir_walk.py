import os
import json

class Config:
    def get_merged_config(self, pdf_file_path: str, base_pdf_folder: str) -> dict:
        """
        Merges config from base folder, all subfolders up to the PDF, and file-specific config.
        Precedence: file-specific > deepest folder > ... > base folder.
        """
        config = {}

        # Normalize paths
        base_pdf_folder = os.path.abspath(base_pdf_folder)
        pdf_file_path = os.path.abspath(pdf_file_path)
        pdf_folder = os.path.dirname(pdf_file_path)

        # Collect all folders from base to PDF's folder
        folders = []
        current = pdf_folder
        while True:
            folders = [current] + folders
            folders.append(current)
            if os.path.samefile(current, base_pdf_folder):
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
        file_base, _ = os.path.splitext(pdf_file_path)
        file_config_path = f"{file_base}_config.json"
        if os.path.exists(file_config_path):
            with open(file_config_path, "r", encoding="utf-8") as f:
                config.update(json.load(f))

        return config