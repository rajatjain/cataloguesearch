import os
import logging
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
# from requests_aws4auth import AWS4Auth # More robust for signing requests
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
import json
import hashlib
import yaml
from datetime import datetime

from backend.config import Config

# Setup logging for this module
log_handle = logging.getLogger(__name__)

class IndexingEmbeddingModule:
    """
    Handles text chunking, vector embedding generation, and indexing into OpenSearch.
    Supports pluggable chunking and embedding algorithms.
    """

    def __init__(self, config: Config):
        self._config = config
        self._opensearch_config_path = config.OPENSEARCH_CONFIG_PATH
        self._opensearch_host = config.OPENSEARCH_HOST
        self._opensearch_port = config.OPENSEARCH_PORT
        self._opensearch_user = config.OPENSEARCH_USER
        self._opensearch_password = config.OPENSEARCH_PASSWORD
        self._index_name = config.INDEX_NAME
        self._embedding_model_name = config.EMBEDDING_MODEL_NAME
        self._chunk_size = config.CHUNK_SIZE
        self._chunk_overlap = config.CHUNK_OVERLAP
        self._opensearch_settings = {}
        self._embedding_model = None

        # Initialize OpenSearch client
        self._opensearch_client = self._get_opensearch_client(
            self._opensearch_host, self._opensearch_port,
            self._opensearch_user, self._opensearch_password)

        log_handle.info(f"OpenSearch client initialized for {self._opensearch_host}:{self._opensearch_port}.")

        # Initialize embedding model
        try:
            self._embedding_model = SentenceTransformer(self._embedding_model_name)
            log_handle.info(f"Embedding model '{self._embedding_model_name}' loaded successfully.")
        except Exception as e:
            log_handle.error(f"Failed to load embedding model '{self._embedding_model_name}': {e}")
            raise

        # Initialize text splitter
        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self._chunk_size,
            chunk_overlap=self._chunk_overlap,
            length_function=len,
            is_separator_regex=False,
        )
        log_handle.info(
            f"Text splitter initialized with chunk_size={self._chunk_size}, chunk_overlap={self._chunk_overlap}.")

    def _get_opensearch_client(self, host, port, user, password):
        """
        Helper method to get an OpenSearch client instance.
        """
        # Basic authentication for local/test setup. For production, consider IAM roles or more robust methods.
        auth = (user, password)
        client = OpenSearch(
            hosts=[{'host': host, 'port': port}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=False, # Set to True for production with proper CA certs
            ssl_assert_hostname=False,
            ssl_show_warn=False,
            timeout=30 # Increased timeout for potential slow operations
        )
        return client

    def create_index_if_not_exists(self):
        """
        Creates the OpenSearch index with a predefined mapping if it doesn't already exist.
        Includes settings for k-NN and analyzers for Hindi/Gujarati.
        """
        if not self._opensearch_config_path or not os.path.exists(self._opensearch_config_path):
            log_handle.critical(
                f"OpenSearch config file not found at {self._opensearch_config_path}. Exiting.")
            raise FileNotFoundError(
                f"OpenSearch config file not found: {self._opensearch_config_path}")

        log_handle.info(f"Loading OpenSearch config from {self._opensearch_config_path}")
        with open(self._opensearch_config_path, 'r', encoding='utf-8') as f:
            self._opensearch_settings = yaml.safe_load(f)

        self._opensearch_settings['settings']['vector_embedding']['dimension'] = \
            self._embedding_model.get_sentence_embedding_dimension()

        try:
            if not self._opensearch_client.indices.exists(self._index_name):
                response = self._opensearch_client.indices.create(
                    self._index_name, body=self._opensearch_settings)
                log_handle.info(f"Index '{self.index_name}' created: {response}")
            else:
                log_handle.info(f"Index '{self.index_name}' already exists.")
        except Exception as e:
            log_handle.critical(f"Error creating index '{self.index_name}': {e}")
            raise

    def _generate_embedding(self, text: str) -> list[float]:
        """
        Generates a vector embedding for the given text using the loaded model.

        Args:
            text (str): The text to embed.

        Returns:
            list[float]: The dense vector embedding.
        """
        try:
            embedding = self._embedding_model.encode(text)
            return embedding.tolist()
        except Exception as e:
            log_handle.error(
                f"Error generating embedding for text (first 50 chars: '{text[:50]}...'): {e}")
            return []

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
            page_text_paths: list[str], metadata: dict, bookmarks: list[dict],
            reindex_metadata_only: bool = False):
        """
        Indexes a document (its pages/chunks) and associated metadata into OpenSearch.

        Args:
            document_id (str): A unique identifier for the PDF document.
            original_filename (str): The original filename of the PDF.
            page_text_paths (list[str]): List of file paths to the page-wise text files.
            metadata (dict): Merged configuration metadata for the document.
            bookmarks (list[dict]): List of extracted bookmarks.
            reindex_metadata_only (bool): If True, only updates metadata for existing chunks,
                                          skipping text re-chunking and embedding.
        """
        log_handle.info(
            f"Indexing document: {document_id}, reindex_metadata_only: {reindex_metadata_only}")
        timestamp = datetime.now(datetime.UTC).isoformat() + "Z" # ISO 8601 format with Z for UTC

        if reindex_metadata_only:
            # For metadata-only re-indexing, we need to find existing chunks for this document
            # and update their metadata. This assumes chunk_id remains stable.
            try:
                query = {
                    "query": {
                        "term": {
                            "document_id.keyword": document_id
                        }
                    },
                    "size": 10000 # Max results to retrieve
                }
                response = self._opensearch_client.search(index=self._index_name, body=query)
                hits = response['hits']['hits']
                log_handle.info(f"Found {len(hits)} existing chunks for document {document_id} for metadata update.")

                for hit in hits:
                    doc_id = hit['_id']
                    # get the page number of the 'hit' document
                    page_number = hit['_source']['page_number']
                    update_body = {
                        "doc": {
                            "metadata": metadata,
                            "bookmarks": bookmarks[page_number + 1] if page_number + 1 < len(bookmarks) else None,
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
            page_number = page_num_idx + 1 # 1-indexed page number
            page_bookmark = bookmarks[page_number] if page_number < len(bookmarks) else None
            try:
                with open(page_path, 'r', encoding='utf-8') as f:
                    page_content = f.read()

                chunks = self._chunk_text(page_content)

                for chunk_idx, chunk_text in enumerate(chunks):
                    # Generate a stable chunk_id
                    chunk_id = self._get_document_hash(document_id, page_number, chunk_idx, chunk_text)

                    embedding = self._generate_embedding(chunk_text)
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
                        "text_content_hindi": chunk_text, # For Hindi analyzer
                        "text_content_gujarati": chunk_text, # For Gujarati analyzer
                        "metadata": metadata,
                        "bookmarks": page_bookmark,
                        "timestamp_indexed": timestamp,
                        "vector_embedding": embedding
                    }

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
                log_handle.error(f"Error processing page {page_path} for indexing: {e}")
        log_handle.info(f"Finished full indexing for document {document_id}.")