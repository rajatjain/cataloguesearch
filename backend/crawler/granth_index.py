import logging
import os
import uuid
from datetime import datetime, timezone

from opensearchpy import OpenSearch, helpers

from backend.config import Config
from backend.common.embedding_models import get_embedding_model_factory
from backend.crawler.granth import Granth

log_handle = logging.getLogger(__name__)


class GranthIndexer:
    """
    Handles indexing of Granth objects into OpenSearch.

    Two main functions:
    1. Store the complete Granth object in granth_index
    2. Extract teeka & bhavarth paragraphs, generate embeddings, and store in search_index
    """

    def __init__(self, config: Config, opensearch_client: OpenSearch):
        self._config = config
        self._opensearch_client = opensearch_client
        self._granth_index_name = config.OPENSEARCH_GRANTH_INDEX_NAME
        self._search_index_name = config.OPENSEARCH_INDEX_NAME
        self._base_dir = config.BASE_PDF_PATH

        self._index_keys_per_lang = {
            "hi": "text_content_hindi",
            "gu": "text_content_gujarati"
        }
    
    def delete_current_index(self, relative_filename: str):
        """
        Delete all entries from both granth_index and search_index with the given original_filename.

        Args:
            relative_filename: The relative filename to match for deletion
        """
        log_handle.info(f"Deleting all entries for original_filename: {relative_filename}")

        indices = [self._granth_index_name, self._search_index_name]
        total_deleted = {}

        for index_name in indices:
            delete_query = {
                "query": {
                    "term": {
                        "original_filename": relative_filename
                    }
                }
            }

            try:
                response = self._opensearch_client.delete_by_query(
                    index=index_name,
                    body=delete_query
                )
                deleted_count = response.get('deleted', 0)
                total_deleted[index_name] = deleted_count
                log_handle.info(f"Deleted {deleted_count} documents from {index_name}")
            except Exception as e:
                log_handle.error(f"Error deleting from {index_name}: {e}")
                total_deleted[index_name] = 0

        log_handle.info(
            f"Total deleted: {total_deleted.get(self._granth_index_name, 0)} from granth_index, "
            f"{total_deleted.get(self._search_index_name, 0)} from search_index"
        )

    def index_granth(self, granth: Granth, dry_run: bool = True):
        """
        Main function to index a Granth object.

        Args:
            granth: The Granth object to index
            dry_run: If True, performs a dry run without actually indexing
        """
        log_handle.info(f"Starting to index Granth: {granth._name}")

        # Generate granth_id from relative path of original filename
        granth_id = str(uuid.uuid5(uuid.NAMESPACE_URL, granth._original_filename))
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

        if dry_run:
            log_handle.info(f"[DRY RUN] Would index Granth {granth._name} with ID {granth_id}")
            return

        # Delete existing entries for this filename
        self.delete_current_index(granth._original_filename)

        # Function 1: Store Granth object in granth_index
        self._store_granth_in_granth_index(granth, granth_id, timestamp)

        # Function 2: Store teeka & bhavarth paragraphs in search_index
        self._store_paragraphs_in_search_index(granth, granth_id, timestamp)

        log_handle.info(f"Completed indexing Granth: {granth._name}")
    
    def _prose_section_to_dict(self, prose_section) -> dict:
        """
        Convert a ProseSection object to dictionary, including nested subsections.
        """
        subsections_list = []
        if prose_section._subsections:
            for subsection in prose_section._subsections:
                subsections_list.append({
                    "seq_num": subsection._seq_num,
                    "heading": subsection._heading,
                    "content": subsection._content,
                    "page_num": subsection._page_num,
                    "adhikar": subsection._adhikar
                })

        return {
            "seq_num": prose_section._seq_num,
            "heading": prose_section._heading,
            "content": prose_section._content,
            "subsections": subsections_list,
            "page_num": prose_section._page_num,
            "adhikar": prose_section._adhikar
        }

    def _store_granth_in_granth_index(self, granth: Granth, granth_id: str, timestamp: str):
        """
        Function 1: Store the complete Granth object in granth_index
        """
        log_handle.info(f"Storing Granth object in granth_index with ID: {granth_id}")

        # Convert language to code format (hindi -> hi, gujarati -> gu)
        language_to_code = {
            "hindi": "hi",
            "gujarati": "gu",
            "hi": "hi",
            "gu": "gu"
        }
        language_code = language_to_code.get(
            granth._metadata._language.lower() if granth._metadata._language else "",
            "hi"
        )

        # Convert Granth to the expected document format for granth_index
        granth_doc = {
            "granth_id": granth_id,
            "original_filename": granth._original_filename,
            "name": granth._name,
            "metadata": {
                "anuyog": granth._metadata._anuyog,
                "language": language_code,
                "author": granth._metadata._author,
                "teekakar": granth._metadata._teekakar,
                "file_url": granth._metadata._file_url
            },
            "verses": [
                {
                    "seq_num": verse._seq_num,
                    "verse": verse._verse,
                    "type": verse._type,
                    "type_start_num": verse._type_start_num,
                    "type_end_num": verse._type_end_num,
                    "translation": verse._translation,
                    "language": verse._language,
                    "meaning": verse._meaning,
                    "teeka": verse._teeka,
                    "bhavarth": verse._bhavarth,
                    "page_num": verse._page_num,
                    "adhikar": verse._adhikar
                }
                for verse in granth._verses
            ],
            "prose_sections": [
                self._prose_section_to_dict(prose_section)
                for prose_section in (granth._prose_sections or [])
            ],
            "timestamp_indexed": timestamp
        }
        
        try:
            response = self._opensearch_client.index(
                index=self._granth_index_name,
                id=granth_id,
                body=granth_doc
            )
            log_handle.info(f"Successfully stored Granth in granth_index: {response['result']}")
        except Exception as e:
            log_handle.error(f"Failed to store Granth in granth_index: {e}")
            raise
    
    def _store_paragraphs_in_search_index(self, granth: Granth, granth_id: str, timestamp: str):
        """
        Function 2: Store all verse fields and prose content paragraphs in search_index
        """
        log_handle.info(f"Storing all verse fields and prose paragraphs for Granth: {granth._name}")

        # Define fields to index with/without embeddings
        fields_config = {
            "no_embeddings": ["verse", "translation", "meaning"],
            "with_embeddings": ["teeka", "bhavarth"]
        }

        all_docs = []

        # Index verse fields
        for verse in granth._verses:
            verse_seq = verse._seq_num or 0
            language = granth._metadata._language or "hi"
            page_num = verse._page_num or 1
            lang_key = self._index_keys_per_lang.get(language, self._index_keys_per_lang["hi"])

            # Index fields WITHOUT embeddings
            for field_name in fields_config["no_embeddings"]:
                field_value = getattr(verse, f"_{field_name}", None)
                if field_value and str(field_value).strip():
                    doc = self._create_verse_document(
                        granth, granth_id, verse, verse_seq, language, lang_key,
                        page_num, field_name, str(field_value).strip(), timestamp,
                        include_embedding=False
                    )
                    all_docs.append(doc)

            # Index fields WITH embeddings (arrays)
            for field_name in fields_config["with_embeddings"]:
                field_value = getattr(verse, f"_{field_name}", None)
                if field_value:
                    # Handle both list and string values
                    field_list = field_value if isinstance(field_value, list) else [field_value]
                    for i, content in enumerate(field_list):
                        if content and content.strip():
                            doc = self._create_verse_document(
                                granth, granth_id, verse, verse_seq, language, lang_key,
                                page_num, field_name, content.strip(), timestamp,
                                include_embedding=True, array_index=i
                            )
                            all_docs.append(doc)

        # Index prose content paragraphs
        for prose_section in (granth._prose_sections or []):
            prose_seq = prose_section._seq_num
            language = granth._metadata._language or "hi"
            page_num = prose_section._page_num or 1
            lang_key = self._index_keys_per_lang.get(language, self._index_keys_per_lang["hi"])

            # Index main prose content paragraphs
            if prose_section._content:
                for i, paragraph in enumerate(prose_section._content):
                    if paragraph and paragraph.strip():
                        doc = self._create_prose_document(
                            granth, granth_id, prose_section, prose_seq, language, lang_key,
                            page_num, paragraph.strip(), timestamp, i
                        )
                        all_docs.append(doc)

            # Index subsection content paragraphs
            if prose_section._subsections:
                for subsection in prose_section._subsections:
                    subsection_seq = subsection._seq_num
                    subsection_page_num = subsection._page_num or page_num

                    if subsection._content:
                        for i, paragraph in enumerate(subsection._content):
                            if paragraph and paragraph.strip():
                                doc = self._create_prose_document(
                                    granth, granth_id, subsection, subsection_seq, language, lang_key,
                                    subsection_page_num, paragraph.strip(), timestamp, i,
                                    parent_seq=prose_seq
                                )
                                all_docs.append(doc)

        if not all_docs:
            log_handle.info("No verse fields or prose paragraphs found to index")
            return

        # Separate docs by whether they need embeddings
        docs_needing_embeddings = [doc for doc in all_docs if doc.get("needs_embedding")]
        docs_without_embeddings = [doc for doc in all_docs if not doc.get("needs_embedding")]

        # Generate embeddings in parallel batch for all docs that need them
        if docs_needing_embeddings:
            texts_to_embed = [doc["text_content"] for doc in docs_needing_embeddings]

            embedding_model = get_embedding_model_factory(self._config)
            log_handle.info(f"Generating embeddings for {len(texts_to_embed)} fields...")

            # Generate embeddings in batches (parallel processing)
            embeddings = embedding_model.get_embeddings_batch(texts_to_embed, batch_size=8)

            # Add embeddings to documents
            for doc, embedding in zip(docs_needing_embeddings, embeddings):
                doc["vector_embedding"] = embedding
                # Clean up temporary fields
                del doc["needs_embedding"]
                del doc["text_content"]

        # Clean up temporary fields for docs without embeddings
        for doc in docs_without_embeddings:
            del doc["needs_embedding"]
            del doc["text_content"]

        # Bulk index all documents
        final_docs = docs_needing_embeddings + docs_without_embeddings
        self._bulk_index_search_documents(final_docs)

        log_handle.info(
            f"Successfully indexed {len(final_docs)} verse fields "
            f"({len(docs_without_embeddings)} without embeddings, {len(docs_needing_embeddings)} with embeddings)"
        )

    def _create_verse_document(
        self, granth: Granth, granth_id: str, verse, verse_seq: int,
        language: str, lang_key: str, page_num: int, field_name: str,
        content: str, timestamp: str, include_embedding: bool = False, array_index: int = None
    ) -> dict:
        """
        Create a document for a verse field to be indexed in search_index
        """
        # Create chunk_id
        if array_index is not None:
            chunk_id = f"{granth_id}_v{verse_seq}_{field_name}_{array_index}"
        else:
            chunk_id = f"{granth_id}_v{verse_seq}_{field_name}"

        doc = {
            "chunk_id": chunk_id,
            "document_id": granth_id,
            "original_filename": granth._original_filename,
            "page_number": page_num,
            "paragraph_id": f"{field_name}_{verse_seq}",
            "metadata": {
                "title": granth._name,
                "language": language,
                "author": granth._metadata._author,
                "teekakar": granth._metadata._teekakar,
                "anuyog": granth._metadata._anuyog,
                "category": "Granth",
                "verse_content_type": field_name,
                "verse_seq_num": verse_seq,
                "verse_type": verse._type,
                "verse_type_start_num": verse._type_start_num,
                "verse_type_end_num": verse._type_end_num,
                "adhikar": verse._adhikar,
                "file_url": granth._metadata._file_url
            },
            "timestamp_indexed": timestamp,
            "language": language,
            "needs_embedding": include_embedding,
            "text_content": content  # Temporary field for embedding generation
        }

        # Add text content to appropriate language field
        doc[lang_key] = content

        return doc

    def _create_prose_document(
        self, granth: Granth, granth_id: str, prose_section, prose_seq: int,
        language: str, lang_key: str, page_num: int, content: str,
        timestamp: str, array_index: int, parent_seq: int = None
    ) -> dict:
        """
        Create a document for a prose paragraph to be indexed in search_index

        Args:
            parent_seq: If this is a subsection, the parent prose section's seq_num
        """
        # Create chunk_id
        if parent_seq is not None:
            # Subsection: granth_id_p{parent_seq}_sub{prose_seq}_content_{array_index}
            chunk_id = f"{granth_id}_p{parent_seq}_sub{prose_seq}_content_{array_index}"
        else:
            # Main prose: granth_id_p{prose_seq}_content_{array_index}
            chunk_id = f"{granth_id}_p{prose_seq}_content_{array_index}"

        doc = {
            "chunk_id": chunk_id,
            "document_id": granth_id,
            "original_filename": granth._original_filename,
            "page_number": page_num,
            "paragraph_id": f"prose_{prose_seq}_content_{array_index}",
            "metadata": {
                "title": granth._name,
                "language": language,
                "author": granth._metadata._author,
                "teekakar": granth._metadata._teekakar,
                "anuyog": granth._metadata._anuyog,
                "category": "Granth",
                "prose_content_type": "subsection" if parent_seq is not None else "main",
                "prose_seq_num": prose_seq,
                "prose_heading": prose_section._heading,
                "adhikar": prose_section._adhikar,
                "file_url": granth._metadata._file_url
            },
            "timestamp_indexed": timestamp,
            "language": language,
            "needs_embedding": True,  # All prose paragraphs get embeddings
            "text_content": content  # Temporary field for embedding generation
        }

        # Add text content to appropriate language field
        doc[lang_key] = content

        return doc

    def _bulk_index_search_documents(self, search_docs: list[dict]):
        """
        Bulk index documents into search_index
        """
        actions = [
            {
                "_index": self._search_index_name,
                "_id": doc["chunk_id"],
                "_source": doc
            }
            for doc in search_docs
        ]
        
        try:
            success, failed = helpers.bulk(
                self._opensearch_client, actions, stats_only=True, raise_on_error=True
            )
            log_handle.info(
                f"Successfully indexed {success} chunks, failed to index {failed} chunks in search_index."
            )
            if failed > 0:
                log_handle.error(
                    f"Failed to index {failed} chunks in search_index. Check OpenSearch logs for details."
                )
        except Exception as e:
            log_handle.error(f"An exception occurred during bulk indexing to search_index: {e}")
            raise