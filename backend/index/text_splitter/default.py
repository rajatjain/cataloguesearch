import hashlib
import logging
import traceback

from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.config import Config
from backend.index.text_splitter.base import BaseChunkSplitter

log_handle = logging.getLogger(__name__)

class DefaultChunksSplitter(BaseChunkSplitter):
    def __init__(self, config: Config):
        super().__init__(config)
        self._chunk_size = \
            config.settings()["index"]["chunking_algos"]["default"]["chunk_size"]
        self._chunk_overlap = \
            config.settings()["index"]["chunking_algos"]["default"]["chunk_overlap"]

        self._char_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self._chunk_size,
            chunk_overlap=self._chunk_overlap,
            length_function=len,
            is_separator_regex=False,
        )

    def get_chunks(self, document_id, pages_text_path : list[str]) -> list[dict]:
        """
        Splits the text from the given pages into chunks based on the configured chunk size and overlap.

        Args:
            pages_text_path (list[str]): List of file paths containing text content.

        Returns:
            list[str]: A list of text chunks.
        """
        all_chunks = list()
        for i, page_path in enumerate(pages_text_path):
            page_num = self._get_page_num(page_path)
            try:
                with open(page_path, 'r', encoding='utf-8') as file:
                    page_content = file.read()
                chunks = self._chunk_text(page_content)
                for chunk_idx, chunk_text in enumerate(chunks):
                    chunk_id = self._get_document_hash(
                        document_id, page_num, chunk_idx, chunk_text
                    )
                    doc = {
                        "document_id": document_id,
                        "page_number": page_num,
                        "chunk_id": chunk_id,
                        "text_content": chunk_text,
                        "embedding_text": chunk_text
                    }
                    all_chunks.append(doc)
            except Exception as e:
                traceback.print_exc()
                log_handle.error(f"Error processing page {page_num} at {page_path}: {e}")
                raise
        
        # Parallelize embedding generation for all chunks
        log_handle.info(f"Generating embeddings for {len(all_chunks)} chunks in parallel...")
        all_chunks = self._add_embeddings_parallel(all_chunks)
        return all_chunks

    def _chunk_text(self, text_content: str) -> list[str]:
        """
        Chunks the given text content using the configured text splitter.

        Args:
            text_content (str): The full text content of a page/document.

        Returns:
            list[str]: A list of text chunks.
        """
        try:
            chunks = self._char_splitter.split_text(text_content)
            log_handle.verbose(f"Chunked text into {len(chunks)} chunks.")
            return chunks
        except Exception as e:
            log_handle.error(f"Error chunking text: {e}")
            return [text_content] # Return original text as single chunk on error