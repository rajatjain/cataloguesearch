from backend.common import embedding_models
from backend.common.opensearch import get_opensearch_client
from backend.crawler.discovery import Discovery
from backend.crawler.index_state import IndexState
from backend.index.embedding_module import IndexingEmbeddingModule
from backend.crawler.pdf_processor import PDFProcessor
from backend.search.index_searcher import IndexSearcher
from tests.backend.common import setup, get_all_documents
from tests.backend.base import *

log_handle = logging.getLogger(__name__)

# simplify the logs. change opensearch's logging to WARN to avoid chunk indexing mesasges.
# comment it out if you need to debug something.
logging.getLogger('opensearch').setLevel(logging.WARNING)

class MockPDFProcessor(PDFProcessor):
    def __init__(self, config: Config):
        """
        Initializes the MockPDFProcessor with a given configuration.
        """
        super().__init__(config)

    def process_pdf(self, pdf_path: str, output_dir: str, images_dir: str, file_metadata):
        """
        1. Return the page_text_paths from the BASE_TEXT_PATH
        2. Return the bookmarks of the PDF file
        Returns the repsonse.
        """
        relpath = os.path.relpath(pdf_path, Config().BASE_PDF_PATH)
        relpath = os.path.splitext(relpath)[0]
        log_handle.info(f"relpath: {relpath}")
        output_text_folder = os.path.join(
            self._output_text_folder, relpath)
        log_handle.info(f"output_text_folder: {output_text_folder}")

        # get the sorted list of text files in the output_text_folder
        page_text_paths = sorted([
            os.path.join(output_text_folder, f) for f in os.listdir(output_text_folder)
            if f.endswith('.txt')
        ])

        # fetch bookmarks from the PDF file
        bookmarks = self.fetch_bookmarks(pdf_path)

        return page_text_paths, bookmarks

@pytest.fixture(scope="module", autouse=True)
def build_index(initialise):
    """
    Test the search functionality.
    This will use the MockPDFProcessor to simulate PDF processing.
    """
    # Initialize the mock PDF processor
    setup(copy_text_files=True)
    config = Config()
    pdf_processor = MockPDFProcessor(config)
    opensearch_client = get_opensearch_client(config, force_clean=True)
    discovery = Discovery(
        config, IndexingEmbeddingModule(config, opensearch_client),
        pdf_processor, IndexState(config.SQLITE_DB_PATH)
    )

    # Crawl
    log_handle.info("Starting crawling")
    discovery.crawl()

    # basic sanity test that indexes are present
    os_all_docs = get_all_documents()
    doc_ids = set()
    for hit in os_all_docs:
        doc_id = hit.get("_source", {}).get("document_id")
        if doc_id:
            doc_ids.add(doc_id)

    yield

    # delete index
    opensearch_client.indices.delete(index=config.OPENSEARCH_INDEX_NAME, ignore=[400, 404])


def test_basic_query():
    config = Config()
    index_searcher = IndexSearcher(config)
    query = "जलवायु"

    log_handle.info(f"Running basic query: {query}")
    results = index_searcher.perform_lexical_search(query, 5, False, {}, "hi", 10, 1)
    log_handle.verbose(f"Results: {json_dumps(results)}")

def test_multi_phrase_query():
    config = Config()
    index_searcher = IndexSearcher(config)
    query = "बढ़ते जलवायु"

    log_handle.info(f"Running multi-phrase query: {query}")
    results, _ = index_searcher.perform_lexical_search(query, 30, False, {}, "hi", 10, 1)
    log_handle.verbose(f"Results: {json_dumps(results)}")
    assert len(results) == 2

def test_category_query():
    config = Config()
    index_searcher = IndexSearcher(config)
    query = "बेंगलुरु सुल्तान"

    log_handle.info(f"Running category query: {query}")
    results, _ = index_searcher.perform_lexical_search(
        query, 30, False, {"type": ["t2"]}, "hi", 10, 1)
    log_handle.verbose(f"Results: {json_dumps(results)}")
    assert len(results) == 2

def test_vector_search():
    config = Config()
    index_searcher = IndexSearcher(config)
    query = "बढ़ते जलवायु"

    log_handle.info(f"Running vector search for query: {query}")
    embedding = embedding_models.get_embedding(config.EMBEDDING_MODEL_NAME, query)
    if embedding is None:
        log_handle.error("Embedding for the query could not be generated.")
        return

    results, _ = index_searcher.perform_vector_search(
        embedding, {}, 10, 1, "hi")
    log_handle.verbose(f"Vector Search Results: {json_dumps(results)}")
    assert len(results) > 0

def test_vector_search_with_categories():
    config = Config()
    index_searcher = IndexSearcher(config)
    query = "बढ़ते जलवायु"

    log_handle.info(f"Running vector search for query: {query}")
    embedding = embedding_models.get_embedding(config.EMBEDDING_MODEL_NAME, query)
    if embedding is None:
        log_handle.error("Embedding for the query could not be generated.")
        return

    results, _ = index_searcher.perform_vector_search(
        embedding, {"type": ["t2"]}, 10, 1, "hi")
    log_handle.verbose(f"Vector Search Results with categories: {json_dumps(results)}")
    assert len(results) == 2

    results1, _ = index_searcher.perform_vector_search(
        embedding, {}, 10, 1, "hi")
    log_handle.verbose(
        f"Vector Search Results without categories: {json_dumps(results1)}")
    assert len(results1) == 10
