import sqlite3
import logging
import os
import json
import hashlib
from datetime import datetime

from backend.utils import json_dumps

log_handle = logging.getLogger(__name__)

class IndexState:
    def __init__(self, state_db_path: str):
        self.state_db_path = state_db_path
        self._init()

    def _init(self):
        """Initializes the SQLite DB and creates the state table if needed."""
        conn = sqlite3.connect(self.state_db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS indexed_files_state (
                document_id TEXT PRIMARY KEY,
                file_path TEXT,
                last_indexed_timestamp TEXT,
                file_checksum TEXT,
                config_hash TEXT,
                index_checksum TEXT,
                ocr_checksum TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS metadata_cache (
                metadata_key TEXT PRIMARY KEY,
                metadata_values TEXT,
                last_updated_timestamp TEXT
            )
        """)
        conn.commit()
        conn.close()

    def load_state(self) -> dict:
        """Loads the indexed state from the SQLite DB."""
        conn = sqlite3.connect(self.state_db_path)
        c = conn.cursor()
        c.execute(
            "SELECT document_id, file_path, last_indexed_timestamp, file_checksum, "
            "config_hash, index_checksum, ocr_checksum FROM indexed_files_state"
        )
        rows = c.fetchall()
        conn.close()
        state = {}
        for row in rows:
            state[row[0]] = {
                "file_path": row[1],
                "last_indexed_timestamp": row[2],
                "file_checksum": row[3],
                "config_hash": row[4],
                "index_checksum": row[5],
                "ocr_checksum": row[6] if len(row) > 6 else None
            }
        return state

    def get_state(self, document_id: str) -> dict:
        """
        Retrieves the state of a document by its ID.
        Returns a dictionary with file_path, last_indexed_timestamp, file_checksum, and config_hash.
        If the document is not found, returns an empty dictionary.
        """
        conn = sqlite3.connect(self.state_db_path)
        c = conn.cursor()
        sql_query = """
            SELECT document_id, file_path, last_indexed_timestamp, file_checksum, config_hash, index_checksum, ocr_checksum
            FROM indexed_files_state WHERE document_id = ?
        """
        c.execute(sql_query, (document_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return {
                "file_path": row[1],
                "last_indexed_timestamp": row[2],
                "file_checksum": row[3],
                "config_hash": row[4],
                "index_checksum": row[5],
                "ocr_checksum": row[6] if len(row) > 6 else None
            }
        return {}

    def update_state(self, document_id: str, state: dict):
        """Inserts or updates a document's state in the DB."""
        conn = sqlite3.connect(self.state_db_path)
        c = conn.cursor()
        log_handle.info(f"Storing state: {json_dumps(state)}")
        c.execute("""
            INSERT INTO indexed_files_state (document_id, file_path, last_indexed_timestamp, file_checksum, config_hash, index_checksum, ocr_checksum)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(document_id) DO UPDATE SET
                file_path=excluded.file_path,
                last_indexed_timestamp=excluded.last_indexed_timestamp,
                file_checksum=excluded.file_checksum,
                config_hash=excluded.config_hash,
                index_checksum=excluded.index_checksum,
                ocr_checksum=excluded.ocr_checksum
        """, (
            document_id,
            state.get("file_path"),
            state.get("last_indexed_timestamp"),
            state.get("file_checksum"),
            state.get("config_hash"),
            state.get("index_checksum", ""),
            state.get("ocr_checksum", "")
        ))
        conn.commit()
        conn.close()

    def delete_state(self, document_id: str):
        """Deletes a document's state from the DB."""
        conn = sqlite3.connect(self.state_db_path)
        c = conn.cursor()
        c.execute("DELETE FROM indexed_files_state WHERE document_id = ?", (document_id,))
        conn.commit()
        conn.close()

    def garbage_collect(self):
        """
        Deletes all the document_ids which no longer have files
        that exist in the filesystem.
        :return: [str] List of file paths that were deleted from the state.
        """

        conn = sqlite3.connect(self.state_db_path)
        c = conn.cursor()
        c.execute("SELECT document_id, file_path FROM indexed_files_state")
        rows = c.fetchall()
        deleted_files = []

        for row in rows:
            document_id, file_path = row
            if not os.path.exists(file_path):
                c.execute("DELETE FROM indexed_files_state WHERE document_id = ?", (document_id,))
                deleted_files.append(file_path)

        conn.commit()
        conn.close()
        log_handle.info(f"Garbage Collect: Deleted {deleted_files} files from state.")
        return deleted_files

    def calculate_ocr_checksum(self, relative_file_path: str, ocr_pages: list[int]) -> str:
        """
        Calculates OCR checksum based on relative file path and list of pages OCRed.

        Args:
            relative_file_path: Relative path of the PDF file
            ocr_pages: List of page numbers that were OCRed

        Returns:
            String representing OCR checksum based on file path and pages
        """

        # Validate inputs
        if not relative_file_path:
            return ""

        if not isinstance(ocr_pages, list):
            return ""

        # Validate that all pages are positive integers
        valid_pages = []
        for page in ocr_pages:
            if isinstance(page, int) and page > 0:
                valid_pages.append(page)
            else:
                log_handle.warning(f"Invalid page number {page} in OCR pages list")

        if not valid_pages:
            return ""

        # Create checksum from relative path and sorted pages
        pages_str = ",".join(map(str, sorted(valid_pages)))
        checksum_input = f"{relative_file_path}:{pages_str}"

        return hashlib.sha256(checksum_input.encode('utf-8')).hexdigest()

    def delete_index_state(self):
        """
        Deletes the entire index state from the SQLite DB.
        This is a destructive operation and should be used with caution.
        """
        conn = sqlite3.connect(self.state_db_path)
        c = conn.cursor()
        c.execute("DELETE FROM indexed_files_state")
        c.execute("DELETE FROM metadata_cache")
        conn.commit()
        conn.close()
        log_handle.info("Deleted all index state and metadata cache.")
