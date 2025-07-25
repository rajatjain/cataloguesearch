import hashlib

from backend.config import Config


class BaseChunkSplitter:
    def __init__(self, config: Config):
        self._config = config

    def get_chunks(self, document_id: str, pages_text_path: list[str]) -> list[dict]:
        """
        Splits the text from the given pages into chunks based on the configured chunk size and overlap.

        Args:
            pages_text_path (list[str]): List of file paths containing text content.

        Returns:
            list[str]: A list of text chunks.
        """
        raise NotImplementedError("Subclasses must implement _get_chunks method")

    def _get_document_hash(
            self, document_id: str, page_number: int,
            chunk_index: int, text_content: str) -> str:
        """
        Generates a unique hash for a document chunk.
        """
        unique_string = f"{document_id}-{page_number}-{chunk_index}-{text_content}"
        return hashlib.sha256(unique_string.encode('utf-8')).hexdigest()

