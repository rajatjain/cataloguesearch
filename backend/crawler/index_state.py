import sqlite3
import logging
import os
import json
from datetime import datetime

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
                config_hash TEXT
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
        c.execute("SELECT document_id, file_path, last_indexed_timestamp, file_checksum, config_hash FROM indexed_files_state")
        rows = c.fetchall()
        conn.close()
        state = {}
        for row in rows:
            state[row[0]] = {
                "file_path": row[1],
                "last_indexed_timestamp": row[2],
                "file_checksum": row[3],
                "config_hash": row[4]
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
            SELECT document_id, file_path, last_indexed_timestamp, file_checksum, config_hash
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
                "config_hash": row[4]
            }
        return {}

    def update_state(self, document_id: str, state: dict):
        """Inserts or updates a document's state in the DB."""
        conn = sqlite3.connect(self.state_db_path)
        c = conn.cursor()
        c.execute("""
            INSERT INTO indexed_files_state (document_id, file_path, last_indexed_timestamp, file_checksum, config_hash)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(document_id) DO UPDATE SET
                file_path=excluded.file_path,
                last_indexed_timestamp=excluded.last_indexed_timestamp,
                file_checksum=excluded.file_checksum,
                config_hash=excluded.config_hash
        """, (
            document_id,
            state.get("file_path"),
            state.get("last_indexed_timestamp"),
            state.get("file_checksum"),
            state.get("config_hash")
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

    def get_metadata_cache(self) -> dict[str, list[str]]:
        """
        Retrieves cached metadata from the database.
        Returns dict[str, list[str]] with metadata keys and their values.
        """
        conn = sqlite3.connect(self.state_db_path)
        c = conn.cursor()
        c.execute("SELECT metadata_key, metadata_values FROM metadata_cache")
        rows = c.fetchall()
        conn.close()

        metadata = {}
        for row in rows:
            key = row[0]
            values = json.loads(row[1])
            metadata[key] = values

        return metadata

    def update_metadata_cache(self, metadata: dict[str, list[str]]):
        """
        Updates the metadata cache with new metadata.

        Args:
            metadata: Dictionary with metadata keys and their values
        """
        conn = sqlite3.connect(self.state_db_path)
        c = conn.cursor()

        # Clear existing metadata
        c.execute("DELETE FROM metadata_cache")

        # Insert new metadata
        timestamp = datetime.now().isoformat()
        for key, values in metadata.items():
            c.execute("""
                INSERT INTO metadata_cache (metadata_key, metadata_values, last_updated_timestamp)
                VALUES (?, ?, ?)
            """, (key, json.dumps(values), timestamp))

        conn.commit()
        conn.close()
        log_handle.info(f"Updated metadata cache with {len(metadata)} keys")

    def has_metadata_cache(self) -> bool:
        """
        Checks if metadata cache exists and is not empty.

        Returns:
            bool: True if metadata cache has data, False otherwise
        """
        conn = sqlite3.connect(self.state_db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM metadata_cache")
        count = c.fetchone()[0]
        conn.close()

        return count > 0

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
