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
        
        # Function 1: Store Granth object in granth_index
        self._store_granth_in_granth_index(granth, granth_id, timestamp)
        
        # Function 2: Store teeka & bhavarth paragraphs in search_index
        self._store_paragraphs_in_search_index(granth, granth_id, timestamp)
        
        log_handle.info(f"Completed indexing Granth: {granth._name}")
    
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
                    "type_num": verse._type_num,
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
        Function 2: Store all verse fields in search_index
        """
        log_handle.info(f"Storing all verse fields for Granth: {granth._name}")

        # Define fields to index with/without embeddings
        fields_config = {
            "no_embeddings": ["verse", "translation", "meaning"],
            "with_embeddings": ["teeka", "bhavarth"]
        }

        all_docs = []

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

        if not all_docs:
            log_handle.info("No verse fields found to index")
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
                "verse_type_num": verse._type_num,
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
                self._opensearch_client, actions, stats_only=True, raise_on_error=False
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