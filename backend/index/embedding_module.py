import logging
import traceback

import langdetect
from opensearchpy import OpenSearch
from langchain_text_splitters import RecursiveCharacterTextSplitter
from backend.common.embedding_models import get_embedding
import hashlib
from datetime import datetime, timezone
from backend.common import language_detector

from backend.config import Config

# Setup logging for this module
log_handle = logging.getLogger(__name__)

class IndexingEmbeddingModule:
    """
    Handles text chunking, vector embedding generation, and indexing into OpenSearch.
    Supports pluggable chunking and embedding algorithms.
    """

    def __init__(self, config: Config, opensearch_client: OpenSearch):
        self._config = config
        self._opensearch_config_path = config.OPENSEARCH_CONFIG_PATH
        self._index_name = config.OPENSEARCH_INDEX_NAME
        self._chunk_size = config.CHUNK_SIZE
        self._chunk_overlap = config.CHUNK_OVERLAP
        self._opensearch_settings = {}
        self._embedding_model_name = config.EMBEDDING_MODEL_NAME
        self._opensearch_client = opensearch_client

        # Initialize text splitter
        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self._chunk_size,
            chunk_overlap=self._chunk_overlap,
            length_function=len,
            is_separator_regex=False,
        )

        self._index_keys_per_lang = {
            "hi": "text_content_hindi",
            "en": "text_content",
            "gu": "text_content_gujarati"
        }
        log_handle.info(
            f"Text splitter initialized with chunk_size={self._chunk_size}, chunk_overlap={self._chunk_overlap}.")

    def _chunk_text(self, text_content: str) -> list[str]:
        """
        Chunks the given text content using the configured text splitter.

        Args:
            text_content (str): The full text content of a page/document.

        Returns:
            list[str]: A list of text chunks.
        """
        try:
            chunks = self._text_splitter.split_text(text_content)
            log_handle.verbose(f"Chunked text into {len(chunks)} chunks.")
            return chunks
        except Exception as e:
            log_handle.error(f"Error chunking text: {e}")
            return [text_content] # Return original text as single chunk on error

    def _get_document_hash(
            self, document_id: str, page_number: int,
            chunk_index: int, text_content: str) -> str:
        """
        Generates a unique hash for a document chunk.
        """
        unique_string = f"{document_id}-{page_number}-{chunk_index}-{text_content}"
        return hashlib.sha256(unique_string.encode('utf-8')).hexdigest()

    def index_document(
            self, document_id: str, original_filename: str,
            page_text_paths: list[str], metadata: dict, bookmarks: dict[int: str],
            reindex_metadata_only: bool = False):
        """
        Indexes a document (its pages/chunks) and associated metadata into OpenSearch.

        Args:
            document_id (str): A unique identifier for the PDF document.
            original_filename (str): The original filename of the PDF.
            page_text_paths (list[str]): List of file paths to the page-wise text files.
            metadata (dict): Merged configuration metadata for the document.
            bookmarks (dict): Dict of extracted bookmarks.
            reindex_metadata_only (bool): If True, only updates metadata for existing chunks,
                                          skipping text re-chunking and embedding.
        """
        log_handle.info(
            f"Indexing document: {document_id}, reindex_metadata_only: {reindex_metadata_only}")
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

        if reindex_metadata_only:
            # For metadata-only re-indexing, we need to find existing chunks for this document
            # and update their metadata. This assumes chunk_id remains stable.
            try:
                query = {
                    "query": {
                        "term": {
                            "document_id": document_id
                        }
                    },
                    "size": 10000 # Max results to retrieve
                }
                response = self._opensearch_client.search(index=self._index_name, body=query)
                hits = response['hits']['hits']
                log_handle.info(
                    f"Found {len(hits)} existing chunks for document {document_id} for metadata update.")

                for hit in hits:
                    doc_id = hit['_id']
                    # get the page number of the 'hit' document
                    page_number = hit['_source']['page_number']
                    update_body = {
                        "doc": {
                            "metadata": metadata,
                            "bookmarks": bookmarks[page_number] if page_number <= len(bookmarks) else None,
                            "timestamp_indexed": timestamp
                        }
                    }
                    self._opensearch_client.update(index=self._index_name, id=doc_id, body=update_body)
                    log_handle.debug(f"Updated metadata for chunk {doc_id} of document {document_id}.")
                log_handle.info(f"Metadata re-indexed for document {document_id}.")
            except Exception as e:
                log_handle.error(f"Error during metadata-only re-indexing for {document_id}: {e}")
            return

        # Full indexing path (new file or content changed)
        for page_num_idx, page_path in enumerate(page_text_paths):
            log_handle.verbose(f"bookmarks: {bookmarks}")
            page_number = page_num_idx + 1 # 1-indexed page number
            page_bookmark = bookmarks[page_number] if page_number <= len(bookmarks) else None
            log_handle.verbose(
                f"page_number: {page_number}, page_bookmark: {page_bookmark}, page_path: {page_path}")
            try:
                with open(page_path, 'r', encoding='utf-8') as f:
                    page_content = f.read()

                chunks = self._chunk_text(page_content)

                for chunk_idx, chunk_text in enumerate(chunks):
                    # Generate a stable chunk_id
                    chunk_id = self._get_document_hash(document_id, page_number, chunk_idx, chunk_text)

                    embedding = get_embedding(self._embedding_model_name, chunk_text)
                    if not embedding:
                        log_handle.warning(f"Skipping indexing for chunk {chunk_id} due to embedding failure.")
                        continue

                    # Prepare document for OpenSearch
                    doc = {
                        "document_id": document_id,
                        "original_filename": original_filename,
                        "page_number": page_number,
                        "chunk_id": chunk_id,
                        "text_content": chunk_text,
                        "metadata": metadata,
                        "bookmarks": page_bookmark,
                        "timestamp_indexed": timestamp,
                        "vector_embedding": embedding
                    }

                    language = metadata.get("language", None)
                    if language is None:
                        language = language_detector.LanguageDetector.detect_language(chunk_text)
                        log_handle.debug(f"Detected language {language} for chunk {chunk_id}: {chunk_text[:50]}...")
                    doc["language"] = language
                    if "language" == "hi+gu":
                        doc[self._index_keys_per_lang["hi"]] = chunk_text
                        doc[self._index_keys_per_lang["gu"]] = chunk_text
                    else:
                        doc[self._index_keys_per_lang[language]] = chunk_text

                    # Index the document
                    try:
                        response = self._opensearch_client.index(
                            index=self._index_name,
                            body=doc,
                            id=chunk_id, # Use chunk_id as OpenSearch document ID
                            refresh=True # Make the document immediately searchable
                        )
                        log_handle.debug(f"Indexed chunk {chunk_id} for document {document_id}, page {page_number}. Response: {response['result']}")
                    except Exception as e:
                        log_handle.error(f"Error indexing chunk {chunk_id} for document {document_id}: {e}")

            except FileNotFoundError:
                log_handle.error(f"Page text file not found: {page_path}. Skipping.")
            except Exception as e:
                traceback.print_exc()
                log_handle.error(f"Error processing page {page_path} for indexing: {e}")
            log_handle.info(f"Finished full indexing for document {document_id}.")