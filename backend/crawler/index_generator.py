import logging
import os.path
from concurrent.futures import ThreadPoolExecutor, as_completed

from opensearchpy import OpenSearch, helpers
from datetime import datetime, timezone

from tqdm import tqdm

from backend.common import language_detector, embedding_models

from backend.config import Config

# Setup logging for this module
log_handle = logging.getLogger(__name__)

class IndexGenerator:
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

        self._index_keys_per_lang = {
            "hi": "text_content_hindi",
            "en": "text_content",
            "gu": "text_content_gujarati"
        }

    def index_document(
            self, document_id: str, original_filename: str,
            page_text_paths: list[str], metadata: dict, bookmarks: dict[int, str],
            reindex_metadata_only: bool = False):
        """
        Indexes a document (its pages/chunks) and associated metadata into OpenSearch.
        """
        log_handle.info(
            f"Indexing document: {document_id}, reindex_metadata_only: {reindex_metadata_only}")
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

        if reindex_metadata_only:
            self._reindex_metadata_only(document_id, metadata, bookmarks, timestamp)
            return

        # --- Full Re-indexing Logic ---
        # 1. Get paragraphs from text files
        paras = self._get_paras(page_text_paths)

        # 2. Create chunk dictionaries from paragraphs
        chunks = self._create_chunks_from_paras(
            paras, document_id, original_filename, metadata, bookmarks, timestamp
        )
        log_handle.info(f"Created {len(chunks)} initial chunks for document {document_id}.")

        # 3. Add embeddings in parallel
        chunks_with_embeddings = self._add_embeddings_parallel(chunks)

        # 4. Index chunks into OpenSearch using the bulk helper for efficiency
        self._bulk_index_chunks(chunks_with_embeddings)

        log_handle.info(f"Finished full indexing for document {document_id}: total_chunks: {len(chunks)}.")

    def _reindex_metadata_only(self, document_id, metadata, bookmarks, timestamp):
        """Handles the logic for updating metadata of existing documents."""
        try:
            query = {"query": {"term": {"document_id": document_id}}, "size": 10000}
            response = self._opensearch_client.search(index=self._index_name, body=query)
            hits = response['hits']['hits']
            log_handle.info(
                f"Found {len(hits)} existing chunks for document {document_id} for metadata update.")

            update_actions = []
            for hit in hits:
                doc_id = hit['_id']
                page_number = hit['_source'].get('page_number')
                action = {
                    "_op_type": "update",
                    "_index": self._index_name,
                    "_id": doc_id,
                    "doc": {
                        "metadata": metadata,
                        "bookmarks": bookmarks.get(page_number),
                        "timestamp_indexed": timestamp
                    }
                }
                update_actions.append(action)

            if update_actions:
                helpers.bulk(self._opensearch_client, update_actions)
            log_handle.info(f"Metadata re-indexed for document {document_id}.")
        except Exception as e:
            log_handle.error(f"Error during metadata-only re-indexing for {document_id}: {e}")

    def _create_chunks_from_paras(self, paras, document_id,
                                  original_filename, metadata, bookmarks, timestamp):
        """Converts a list of paragraphs into a list of chunk dictionaries."""
        chunks = []
        for i, (page_num, para_text) in enumerate(paras):
            chunk_id = f"{document_id}_p{page_num}_para{i}"
            chunk = {
                "chunk_id": chunk_id,
                "document_id": document_id,
                "original_filename": original_filename,
                "page_number": page_num,
                "paragraph_id": i,
                "text_content": para_text,
                "embedding_text": para_text,
                "metadata": metadata,
                "bookmarks": bookmarks.get(page_num),
                "timestamp_indexed": timestamp,
            }

            language = metadata.get("language") or language_detector.LanguageDetector.detect_language(para_text)
            chunk["language"] = language

            lang_key = self._index_keys_per_lang.get(language, "text_content")
            chunk[lang_key] = para_text
            if language == "hi+gu":
                chunk[self._index_keys_per_lang["gu"]] = para_text

            chunks.append(chunk)
        return chunks

    def _add_embeddings_parallel(self, all_chunks: list[dict]) -> list[dict]:
        """Adds vector embeddings to chunks using parallel processing."""
        def process_chunk(chunk):
            try:
                embedding = embedding_models.get_embedding(
                    self._embedding_model_name, chunk["embedding_text"]
                )
                chunk["vector_embedding"] = embedding
                del chunk["embedding_text"]  # Save space
                return chunk
            except Exception as e:
                log_handle.error(f"Error generating embedding for chunk {chunk.get('chunk_id')}: {e}")
                return chunk

        with ThreadPoolExecutor(max_workers=8) as executor:
            processed_chunks = list(tqdm(executor.map(process_chunk, all_chunks),
                                         total=len(all_chunks),
                                         desc="Creating embeddings"))
        log_handle.info(f"Generated embeddings for {len(processed_chunks)} chunks")
        return processed_chunks

    def _bulk_index_chunks(self, chunks: list[dict]):
        """Indexes a list of chunks into OpenSearch using the bulk API."""
        actions = [
            {
                "_index": self._index_name,
                "_id": chunk["chunk_id"],
                "_source": chunk
            }
            for chunk in chunks
        ]
        try:
            success, failed = helpers.bulk(self._opensearch_client, actions, stats_only=True, raise_on_error=False)
            log_handle.info(f"Successfully indexed {success} chunks, failed to index {failed} chunks.")
            if failed > 0:
                log_handle.error(f"Failed to index {failed} chunks. Check OpenSearch logs for details.")
        except Exception as e:
            log_handle.error(f"An exception occurred during bulk indexing: {e}")

    def _get_paras(self, page_text_paths: list[str]) -> list[tuple[int, str]]:
        """Reads all paragraph files and returns a flattened list of (page_number, paragraph_text)."""
        final_paras = []
        for page_text_path in page_text_paths:
            page_num = self._get_page_num(page_text_path)
            if page_num is None:
                continue

            try:
                with open(page_text_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # FIX: Use the correct separator used in pdf_processor.py
                    paras = content.split("\n----\n")
                    for para in paras:
                        if para.strip():
                            final_paras.append((page_num, para.strip()))
            except IOError as e:
                log_handle.error(f"Could not read file {page_text_path}: {e}")
        return final_paras

    def _get_page_num(self, file_path: str) -> int | None:
        """Extracts the page number from a filename like 'page_0123.txt'."""
        try:
            filename = os.path.basename(file_path)
            page_str = filename.removesuffix('.txt').removeprefix('page_')
            return int(page_str)
        except (ValueError, AttributeError):
            log_handle.warning(f"Could not parse page number from filename: {file_path}")
            return None