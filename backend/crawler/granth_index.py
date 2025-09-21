import logging
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
        
        # Convert Granth to the expected document format for granth_index
        granth_doc = {
            "granth_id": granth_id,
            "original_filename": granth._original_filename,
            "name": granth._name,
            "metadata": {
                "anuyog": granth._metadata._anuyog,
                "language": granth._metadata._language,
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
        Function 2: Extract teeka & bhavarth paragraphs and store in search_index
        """
        log_handle.info(f"Extracting and storing teeka & bhavarth paragraphs for Granth: {granth._name}")
        
        # Extract all paragraphs from teeka and bhavarth
        paragraphs = self._extract_paragraphs_from_verses(granth, granth_id)
        
        if not paragraphs:
            log_handle.info("No paragraphs found to index")
            return
        
        # Generate embeddings for all paragraphs
        paragraphs_with_embeddings = self._add_embeddings_to_paragraphs(paragraphs)
        
        # Create documents for search_index
        search_docs = self._create_search_documents(
            paragraphs_with_embeddings, granth, granth_id, timestamp
        )
        
        # Bulk index into search_index
        self._bulk_index_search_documents(search_docs)
        
        log_handle.info(
            f"Successfully indexed {len(search_docs)} paragraph chunks for Granth: {granth._name}"
        )
    
    def _extract_paragraphs_from_verses(self, granth: Granth, granth_id: str) -> list[dict]:
        """
        Extract teeka and bhavarth paragraphs from all verses
        """
        paragraphs = []
        
        for verse in granth._verses:
            verse_seq = verse._seq_num or 0
            language = verse._language or granth._metadata._language or "hi"
            page_num = verse._page_num or 1
            
            # Extract teeka paragraphs
            if verse._teeka:
                teeka_list = verse._teeka if isinstance(verse._teeka, list) else [verse._teeka]
                for i, para in enumerate(teeka_list):
                    if para and para.strip():
                        chunk_id = f"{granth_id}_v{verse_seq}_teeka_{i}"
                        paragraphs.append({
                            "chunk_id": chunk_id,
                            "content": para.strip(),
                            "content_type": "teeka",
                            "verse_seq_num": verse_seq,
                            "verse_type": verse._type,
                            "verse_type_num": verse._type_num,
                            "language": language,
                            "page_num": page_num,
                            "adhikar": verse._adhikar
                        })
            
            # Extract bhavarth paragraphs
            if verse._bhavarth:
                bhavarth_list = verse._bhavarth if isinstance(verse._bhavarth, list) else [verse._bhavarth]
                for i, para in enumerate(bhavarth_list):
                    if para and para.strip():
                        chunk_id = f"{granth_id}_v{verse_seq}_bhavarth_{i}"
                        paragraphs.append({
                            "chunk_id": chunk_id,
                            "content": para.strip(),
                            "content_type": "bhavarth",
                            "verse_seq_num": verse_seq,
                            "verse_type": verse._type,
                            "verse_type_num": verse._type_num,
                            "language": language,
                            "page_num": page_num,
                            "adhikar": verse._adhikar
                        })
        
        log_handle.info(f"Extracted {len(paragraphs)} paragraphs from {len(granth._verses)} verses")
        return paragraphs
    
    def _add_embeddings_to_paragraphs(self, paragraphs: list[dict]) -> list[dict]:
        """
        Generate vector embeddings for all paragraphs
        """
        if not paragraphs:
            return []
        
        embedding_model = get_embedding_model_factory(self._config)
        
        # Extract text content for embedding generation
        texts_to_embed = [para["content"] for para in paragraphs]
        
        log_handle.info(f"Generating embeddings for {len(texts_to_embed)} paragraphs...")
        
        # Generate embeddings in batches
        embeddings = embedding_model.get_embeddings_batch(texts_to_embed, batch_size=8)
        
        # Add embeddings to paragraphs
        for i, para in enumerate(paragraphs):
            para["vector_embedding"] = embeddings[i]
        
        log_handle.info(f"Generated embeddings for {len(paragraphs)} paragraphs")
        return paragraphs
    
    def _create_search_documents(
        self, paragraphs: list[dict], granth: Granth, granth_id: str, timestamp: str
    ) -> list[dict]:
        """
        Create documents in the format expected by search_index
        """
        search_docs = []
        
        for para in paragraphs:
            language = para["language"]
            
            # Determine the correct language field for search_index
            lang_key = self._index_keys_per_lang.get(language, self._index_keys_per_lang["hi"])
            
            # Create document matching search_index structure
            doc = {
                "chunk_id": para["chunk_id"],
                "document_id": granth_id,
                "original_filename": granth._original_filename,
                "page_number": para["page_num"],
                "paragraph_id": f"{para['content_type']}_{para['verse_seq_num']}",
                "vector_embedding": para["vector_embedding"],
                "metadata": {
                    "title": granth._name,
                    "language": language,
                    "author": granth._metadata._author,
                    "teekakar": granth._metadata._teekakar,
                    "anuyog": granth._metadata._anuyog,
                    "content_type": "granth",
                    "verse_content_type": para["content_type"],  # teeka or bhavarth
                    "verse_seq_num": para["verse_seq_num"],
                    "verse_type": para["verse_type"],
                    "verse_type_num": para["verse_type_num"],
                    "adhikar": para["adhikar"]
                },
                "timestamp_indexed": timestamp,
                "language": language
            }
            
            # Add content to the appropriate language field
            doc[lang_key] = para["content"]
            
            search_docs.append(doc)
        
        return search_docs
    
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