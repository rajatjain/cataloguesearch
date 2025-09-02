import logging
import os.path
import traceback
from datetime import datetime, timezone

from opensearchpy import OpenSearch, helpers

from backend.common.embedding_models import get_embedding_model_factory
from backend.common.opensearch import delete_documents_by_filename
from backend.config import Config
from backend.crawler.paragraph_generator.gujarati import GujaratiParagraphGenerator
from backend.crawler.paragraph_generator.hindi import HindiParagraphGenerator

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
        self._metadata_index_name = config.OPENSEARCH_METADATA_INDEX_NAME
        self._opensearch_settings = {}
        self._embedding_model_name = config.EMBEDDING_MODEL_NAME
        self._opensearch_client = opensearch_client

        self._index_keys_per_lang = {
            "hi": "text_content_hindi",
            "gu": "text_content_gujarati"
        }

        self._paragraph_generators = {
            "hi": HindiParagraphGenerator(self._config),
            "gu": GujaratiParagraphGenerator(self._config)
        }


    def index_document(
        self, document_id: str, original_filename: str,
        ocr_dir: str, output_text_dir: str, pages_list: list[int], metadata: dict,
        scan_config: dict, bookmarks: dict[int, str],
        reindex_metadata_only: bool = False, dry_run: bool = True):
        log_handle.info(
            f"Indexing document: {document_id}, reindex_metadata_only: {reindex_metadata_only}"
            f"Dry Run: {dry_run}")
        paragraphs = []
        for page_num in pages_list:
            ocr_file = f"{ocr_dir}/page_{page_num:04d}.txt"
            with open(ocr_file, 'r', encoding='utf-8') as f:
                content = f.read()
                page_paragraphs = content.split("\n----\n") if content.strip() else []
                paragraphs.append((page_num, page_paragraphs))

        language = metadata.get("language", "hi")
        paragraph_gen = self._paragraph_generators[language]
        processed_paras = paragraph_gen.generate_paragraphs(
            paragraphs, scan_config
        )

        # Write paragraphs to the text directory
        self._write_paragraphs(output_text_dir, processed_paras)

        if dry_run:
            log_handle.info(
                f"[DRY RUN] Would index document to OpenSearch and save state for "
                f"{original_filename}"
            )
            return

        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        if reindex_metadata_only:
            self._reindex_metadata_only(document_id, metadata, bookmarks, timestamp)
            return

        # --- Full Re-indexing Logic ---
        # Delete all existing documents for this original_filename before reindexing
        log_handle.info(f"Deleting existing documents for {original_filename} before reindexing")
        try:
            delete_documents_by_filename(self._config, original_filename)
        except Exception as e:
            log_handle.error(f"Failed to delete existing documents for {original_filename}: {e}")
            # Continue with indexing even if deletion fails, as it's a safety measure

        page_text_paths = []
        for root, _, files in os.walk(output_text_dir):
            for file_name in files:
                if not file_name.lower().endswith(".txt"):
                    continue
                page_text_paths.append(os.path.join(root, file_name))
        page_text_paths = sorted(page_text_paths)
        paras = self._get_paras(page_text_paths)

        chunks = self._create_chunks_from_paras(
            paras, document_id, original_filename, metadata, bookmarks, timestamp
        )
        log_handle.info(f"Created {len(chunks)} initial chunks for document {document_id}.")

        # 3. Add embeddings in parallel
        chunks_with_embeddings = self._add_embeddings_parallel(chunks)

        # 4. Index chunks into OpenSearch using the bulk helper for efficiency
        self._bulk_index_chunks(chunks_with_embeddings)

        # 5. Update the metadata index with the new metadata
        self._update_metadata_index(metadata)

        log_handle.info(
            f"Finished full indexing for document {document_id}: total_chunks: {len(chunks)}.")


    def _write_paragraphs(self, output_dir, paragraphs):
        page_paras = {}
        for page_num, para in paragraphs:
            if page_num not in page_paras:
                page_paras[page_num] = []
            page_paras[page_num].append(para)

        page_nums = sorted(page_paras.keys())
        for page_num in page_nums:
            para_list = page_paras[page_num]
            fname = f"{output_dir}/page_{page_num:04d}.txt"
            content = "\n----\n".join(para_list)
            try:
                with open(fname, 'w', encoding='utf-8') as fh:
                    fh.write(content)
            except IOError:
                traceback.print_exc()
                log_handle.error(f"Failed to write {fname}")

    def _reindex_metadata_only(self, document_id, metadata, bookmarks, timestamp):
        """Handles the logic for updating metadata of existing documents."""
        try:
            query = {"query": {"term": {"document_id": document_id}}, "size": 10000}
            response = self._opensearch_client.search(index=self._index_name, body=query)
            hits = response['hits']['hits']
            log_handle.info(
                f"Found {len(hits)} existing chunks for document {document_id} "
                f"for metadata update."
            )

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

            # Also update the dedicated metadata index
            self._update_metadata_index(metadata)

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
                "embedding_text": para_text,
                "metadata": metadata,
                "bookmarks": bookmarks.get(page_num),
                "timestamp_indexed": timestamp,
            }

            language = metadata.get("language", "hi")
            chunk["language"] = language

            # Default to Hindi for unsupported languages or English text
            lang_key = self._index_keys_per_lang.get(language, self._index_keys_per_lang["hi"])
            chunk[lang_key] = para_text

            chunks.append(chunk)
        return chunks

    def _add_embeddings_parallel(self, all_chunks: list[dict]) -> list[dict]:
        """Adds vector embeddings to chunks using efficient batch processing."""
        if not all_chunks:
            return []

        embedding_model = get_embedding_model_factory(self._config)

        # Extract the text to be embedded from all chunks
        texts_to_embed = [chunk["embedding_text"] for chunk in all_chunks]

        log_handle.info(f"Generating embeddings for {len(texts_to_embed)} chunks in batches...")

        # Generate all embeddings in a single, optimized batch call
        embeddings = embedding_model.get_embeddings_batch(texts_to_embed, batch_size=8)

        # Assign the generated embeddings back to their corresponding chunks
        for i, chunk in enumerate(all_chunks):
            chunk["vector_embedding"] = embeddings[i]
            del chunk["embedding_text"]  # Save space

        log_handle.info(
            f"Generated embeddings for {len(all_chunks)} chunks using "
            f"{self._config.EMBEDDING_MODEL_TYPE} model."
        )
        return all_chunks

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
            success, failed = helpers.bulk(
                self._opensearch_client, actions, stats_only=True, raise_on_error=False
            )
            log_handle.info(
                f"Successfully indexed {success} chunks, failed to index {failed} chunks."
            )
            if failed > 0:
                log_handle.error(
                    f"Failed to index {failed} chunks. Check OpenSearch logs for details."
                )
        except Exception as e:
            log_handle.error(f"An exception occurred during bulk indexing: {e}")

    def _update_metadata_index(self, metadata: dict):
        """
        Updates the dedicated metadata index with new values from a document.
        Uses a scripted upsert for efficiency and atomicity.
        """
        if not metadata:
            return

        log_handle.info(f"Updating metadata index for keys: {list(metadata.keys())}")

        actions = []
        for key, value in metadata.items():
            if not value:
                continue

            # Ensure new_values is a list of strings
            new_values = [str(v) for v in value] if isinstance(value, list) else [str(value)]

            action = {
                "_op_type": "update",
                "_index": self._metadata_index_name,
                "_id": key,
                "script": {
                    "source": """
                        boolean changed = false;
                        for (item in params.newValues) {
                            if (!ctx._source.values.contains(item)) {
                                ctx._source.values.add(item);
                                changed = true;
                            }
                        }
                        if (changed) {
                            Collections.sort(ctx._source.values);
                        }
                    """,
                    "lang": "painless",
                    "params": {"newValues": new_values}
                },
                "upsert": {"values": sorted(new_values)}
            }
            actions.append(action)

        if actions:
            helpers.bulk(self._opensearch_client, actions, stats_only=True, raise_on_error=False)
            log_handle.info(f"Successfully sent {len(actions)} updates to the metadata index.")

    def _get_paras(self, page_text_paths: list[str]) -> list[tuple[int, str]]:
        """
        Reads all paragraph files and returns a flattened list of (page_number, paragraph_text).
        """
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
