import hashlib
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.common.embedding_models import get_embedding
from backend.config import Config

log_handle = logging.getLogger(__name__)

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

    def _get_page_num(self, file_path):
        """Extract page number from filename pattern 'page_X.txt',
        where X can be any number of digits.
        """
        fname = os.path.basename(file_path)
        
        if not (fname.startswith("page_") and fname.endswith(".txt")):
            return None
            
        # Extract the numeric part between 'page_' and '.txt'
        page_part = fname[5:-4]  # Remove 'page_' prefix and '.txt' suffix
        
        if not page_part:  # Handle empty string case
            return None
            
        try:
            return int(page_part)
        except ValueError:
            return None

    def _add_embeddings_parallel(self, all_chunks: list[dict]) -> list[dict]:
        """
        Add vector embeddings to chunks using parallel processing.

        Args:
            all_chunks (list[dict]): List of chunk dictionaries

        Returns:
            list[dict]: Chunks with vector_embedding field added
        """
        def process_chunk(chunk):
            try:
                text_content = chunk["text_content"]
                embedding_text = chunk["embedding_text"]
                embedding = get_embedding(self._config.EMBEDDING_MODEL_NAME, embedding_text)
                chunk["vector_embedding"] = embedding
                # remove chunk['embedding_text'] to save space
                del chunk["embedding_text"]
                return chunk
            except Exception as e:
                log_handle.error(f"Error generating embedding for chunk {chunk.get('chunk_id', 'unknown')}: {e}")
                # Return chunk without embedding on error
                return chunk

        # Use ThreadPoolExecutor for parallel processing
        max_workers = min(len(all_chunks), 8)  # Limit to 8 threads
        processed_chunks = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_chunk = {executor.submit(process_chunk, chunk): chunk for chunk in all_chunks}

            # Collect results as they complete
            for future in as_completed(future_to_chunk):
                try:
                    result = future.result()
                    processed_chunks.append(result)
                except Exception as e:
                    chunk = future_to_chunk[future]
                    log_handle.error(f"Error processing chunk {chunk.get('chunk_id', 'unknown')}: {e}")
                    # Add chunk without embedding on error
                    processed_chunks.append(chunk)

        log_handle.info(f"Generated embeddings for {len(processed_chunks)} chunks")
        # Sort chunks by page_number
        processed_chunks.sort(key=lambda chunk: chunk["page_number"])
        return processed_chunks