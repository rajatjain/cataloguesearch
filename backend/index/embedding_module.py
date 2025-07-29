import logging

from opensearchpy import OpenSearch
from datetime import datetime, timezone
from backend.common import language_detector

from backend.config import Config
from backend.crawler.text_splitter.default import DefaultChunksSplitter
from backend.crawler.text_splitter.dynamic_chunks import DynamicChunksSplitter
from backend.crawler.text_splitter.paragraph_splitter import ParagraphChunksSplitter

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
        self._opensearch_settings = {}
        self._embedding_model_name = config.EMBEDDING_MODEL_NAME
        self._opensearch_client = opensearch_client

        self._chunk_strategy = config.CHUNK_STRATEGY
        if self._chunk_strategy is None or self._chunk_strategy == "default":
            self._text_splitter = DefaultChunksSplitter(config)
        elif self._chunk_strategy == "dynamic":
            self._text_splitter = DynamicChunksSplitter(config)
        elif self._chunk_strategy == "paragraph":
            self._text_splitter = ParagraphChunksSplitter(config)

        self._index_keys_per_lang = {
            "hi": "text_content_hindi",
            "en": "text_content",
            "gu": "text_content_gujarati"
        }

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

        chunks = self._text_splitter.get_chunks(
            document_id=document_id, pages_text_path=page_text_paths)

        language = metadata.get("language", None)
        for chunk in chunks:
            # add common fields
            chunk["original_filename"] = original_filename
            chunk["metadata"] = metadata
            chunk["timestamp_indexed"] = timestamp
            chunk["bookmarks"] = bookmarks.get(chunk["page_number"], None)
            if language is None:
                language = language_detector.LanguageDetector.detect_language(chunk["text_content"])
            chunk["language"] = language
            if language == "hi+gu":
                chunk[self._index_keys_per_lang["hi"]] = chunk["text_content"]
                chunk[self._index_keys_per_lang["gu"]] = chunk["text_content"]
                log_handle.verbose(
                    f"Hindi and Gujarati text for chunk {chunk['chunk_id']}: {chunk['text_content'][:50]}...")
            else:
                chunk[self._index_keys_per_lang[language]] = chunk["text_content"]
                log_handle.verbose(
                    f"{language.upper()} text for chunk {chunk['chunk_id']}: {chunk['text_content'][:50]}...")
            # Index the document
            try:
                response = self._opensearch_client.index(
                    index=self._index_name,
                    body=chunk,
                    id=chunk["chunk_id"], # Use chunk_id as OpenSearch document ID
                    refresh=True # Make the document immediately searchable
                )
                log_handle.debug(
                    f"Indexed chunk {chunk['chunk_id']} for document {document_id}, "
                    f"page {chunk['page_number']}. Response: {response['result']}")
            except Exception as e:
                log_handle.error(
                    f"Error indexing chunk {chunk['chunk_id']} "
                    f"for document {document_id}: {e}")

        log_handle.info(f"Finished full indexing for document {document_id}: total_chunks: {len(chunks)}")