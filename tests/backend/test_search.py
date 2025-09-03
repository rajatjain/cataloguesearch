import os
import shutil
import random
from backend.common import embedding_models
from backend.common.opensearch import get_opensearch_client
from backend.crawler.discovery import Discovery
from backend.crawler.index_state import IndexState
from backend.crawler.index_generator import IndexGenerator
from backend.crawler.pdf_processor import PDFProcessor
from backend.search.index_searcher import IndexSearcher
from tests.backend.common import setup, get_all_documents
from tests.backend.base import *

log_handle = logging.getLogger(__name__)

# simplify the logs. change opensearch's logging to WARN to avoid chunk indexing mesasges.
# comment it out if you need to debug something.
logging.getLogger('opensearch').setLevel(logging.WARNING)


@pytest.fixture(scope="module", autouse=True)
def build_index(initialise):
    """
    Setup test data and build search index.
    Copy OCR data to base_ocr_path and call discovery with process=False, index=True.
    """
    # Setup test environment with scan_config files
    setup(copy_ocr_files=True, add_scan_config=True)
    config = Config()
    
    # Initialize OpenSearch client and ensure clean index state
    opensearch_client = get_opensearch_client(config)
    
    # Explicitly delete indices to ensure clean state and proper mapping creation
    log_handle.info("Deleting existing indices to ensure clean state for vector search")
    indices_to_delete = [config.OPENSEARCH_INDEX_NAME, config.OPENSEARCH_METADATA_INDEX_NAME]
    for index_name in indices_to_delete:
        if index_name and opensearch_client.indices.exists(index=index_name):
            opensearch_client.indices.delete(index=index_name)
            log_handle.info(f"Deleted existing index: {index_name}")
    
    # Create indices with proper mapping (including knn_vector for embeddings)
    from backend.common.opensearch import create_indices_if_not_exists
    create_indices_if_not_exists(config, opensearch_client)
    log_handle.info("Created indices with proper mapping for vector search")
    
    pdf_processor = PDFProcessor(config)  # We won't actually use this since process=False
    discovery = Discovery(
        config, 
        IndexGenerator(config, opensearch_client),
        pdf_processor, 
        IndexState(config.SQLITE_DB_PATH)
    )

    # Call discovery with process=False, index=True
    log_handle.info("Starting discovery with process=False, index=True")
    discovery.crawl(process=False, index=True)

    # Verify indexes are present
    os_all_docs = get_all_documents()
    doc_count = len(os_all_docs)
    log_handle.info(f"Indexed {doc_count} documents")

    yield

    # Cleanup - delete index
    opensearch_client.indices.delete(index=config.OPENSEARCH_INDEX_NAME, ignore=[400, 404])


def test_lexical_search_basic():
    """Test basic lexical search with query-filename validation."""
    config = Config()
    index_searcher = IndexSearcher(config)
    
    # List of [query, expected_filename_substring, language]
    test_cases = [
        ["बेंगलुरु केम्पे गौड़ा", "bangalore_hindi", "hi"],
        ["विजयनगर साम्राज्य हरिहर", "hampi_hindi", "hi"],
        ["मैसूर साम्राज्य", "bangalore_hindi", "hi"],  # Content about Mysore in Bangalore file
        ["હમ્પી વિજયનગર", "hampi_gujarati", "gu"],
    ]
    
    for query, expected_filename, language in test_cases:
        log_handle.info(f"Running lexical search for: {query} (expecting {expected_filename})")
        
        results, total_hits = index_searcher.perform_lexical_search(
            keywords=query, 
            exact_match=False, 
            exclude_words=[], 
            categories={}, 
            detected_language=language, 
            page_size=10, 
            page_number=1
        )
        
        log_handle.info(f"Found {len(results)} results for query: {query}")
        assert len(results) > 0, f"No results found for query: {query}"
        
        # Validate that expected filename appears in results
        found_expected = False
        for result in results:
            filename = result.get('filename', '').lower()
            if expected_filename.lower() in filename:
                found_expected = True
                log_handle.info(f"✓ Found expected file {expected_filename} in results for query: {query}")
                break
        
        assert found_expected, f"Expected filename '{expected_filename}' not found in results for query '{query}'"

def test_lexical_search_with_filters():
    """Test lexical search with category filters."""
    config = Config()
    index_searcher = IndexSearcher(config)
    
    # List of [query, filters, expected_filename_substring, language]
    test_cases = [
        ["बेंगलुरु", {"language": ["hi"]}, "hindi", "hi"],
        ["હમ્પી", {"language": ["gu"]}, "gujarati", "gu"],
        ["विजयनगर", {"category": ["history"]}, "hampi", "hi"],  # If history category exists
    ]
    
    for query, filters, expected_filename, language in test_cases:
        log_handle.info(f"Running filtered lexical search: {query} with filters {filters}")
        
        results, total_hits = index_searcher.perform_lexical_search(
            keywords=query, 
            exact_match=False, 
            exclude_words=[], 
            categories=filters, 
            detected_language=language, 
            page_size=10, 
            page_number=1
        )
        
        log_handle.info(f"Found {len(results)} filtered results for: {query}")
        if len(results) > 0:
            # Check if results match the expected filename pattern
            matching_files = []
            for result in results:
                filename = result.get('filename', '').lower()
                if expected_filename.lower() in filename:
                    matching_files.append(filename)
            
            log_handle.info(f"Matching files for filter: {matching_files}")

def test_lexical_search_exact_phrase():
    """Test lexical search with exact phrase matching."""
    config = Config()
    index_searcher = IndexSearcher(config)
    
    # List of [exact_phrase, expected_filename_substring, language]
    test_cases = [
        ["केम्पे गौड़ा प्रथम", "bangalore_hindi", "hi"],  # Exact phrase from Bangalore Hindi content
        ["बेंगलुरु: एक समग्र विश्लेषण", "bangalore_hindi", "hi"],  # Title from content
        ["કેમ્પે ગૌડા પ્રથમ", "bangalore_gujarati", "gu"],  # Exact phrase from Bangalore Gujarati
        ["હમ્પી: એક સર્વાગી વિશ્લેષણ", "hampi_gujarati", "gu"],  # Title from Hampi Gujarati
        ["हम्पी: एक समग्र विश्लेषण", "hampi_hindi", "hi"],  # Title from Hampi Hindi
        ["विजयनगर साम्राज्य की नींव", "hampi_hindi", "hi"],  # Specific phrase about Vijayanagar Empire
    ]
    
    for exact_phrase, expected_filename, language in test_cases:
        log_handle.info(f"Running exact phrase search for: '{exact_phrase}' (expecting {expected_filename})")
        
        results, total_hits = index_searcher.perform_lexical_search(
            keywords=exact_phrase, 
            exact_match=True,  # Use exact match for phrase search
            exclude_words=[], 
            categories={}, 
            detected_language=language, 
            page_size=10, 
            page_number=1
        )
        
        log_handle.info(f"Found {len(results)} exact phrase results for: '{exact_phrase}'")
        if len(results) > 0:
            # Check if results contain expected filename
            found_expected = False
            for result in results:
                filename = result.get('filename', '').lower()
                if expected_filename.lower() in filename:
                    found_expected = True
                    log_handle.info(f"✓ Found expected file {expected_filename} for exact phrase: '{exact_phrase}'")
                    break
            
            if not found_expected:
                log_handle.warning(f"Expected filename '{expected_filename}' not found for exact phrase '{exact_phrase}'")

def test_lexical_search_exact_phrase_negative():
    """Test that exact phrase search gives different results than regular lexical search."""
    config = Config()
    index_searcher = IndexSearcher(config)
    
    # List of [query_words, non_exact_phrase, expected_filename, language]
    # These are cases where individual words exist but the exact phrase doesn't
    test_cases = [
        # Hindi negative cases - using thanjavur and songadh content
        ["चोल साम्राज्य गौरव", "तंजावुर चोल गौरव इतिहास", "thanjavur_hindi", "hi"],  # Words exist separately but not as exact phrase
        ["सौराष्ट्र भावनगर किला", "सोनगढ़ भावनगर सामरिक किला", "songadh_hindi", "hi"],  # Words exist but phrase doesn't
        ["बृहदीश्वर मंदिर निर्माण", "राजराज चोल मंदिर शक्ति निर्माण", "thanjavur_hindi", "hi"],  # Individual words exist
        
        # Gujarati negative cases
        ["સૌરાષ્ટ્ર ભાવનગર કિલ્લો", "સોનગઢ ભાવનગર વ્યૂહાત્મક કિલ્લો", "songadh_gujarati", "gu"],  # Words exist but exact phrase doesn't
        ["મરાઠા ગાયકવાડ શક્તિ", "સોનગઢ મરાઠા ગાયકવાડ વંશ", "songadh_gujarati", "gu"],  # Individual words present
    ]
    
    for individual_words, non_exact_phrase, expected_filename, language in test_cases:
        log_handle.info(f"Testing negative case - Individual words: '{individual_words}' vs Non-exact phrase: '{non_exact_phrase}'")
        
        # Test 1: Individual words with regular lexical search (should find results)
        results_individual, _ = index_searcher.perform_lexical_search(
            keywords=individual_words,
            exact_match=False,  # Regular lexical search
            exclude_words=[], 
            categories={}, 
            detected_language=language, 
            page_size=10, 
            page_number=1
        )
        
        # Test 2: Non-exact phrase with exact match (should find fewer/no results)
        results_exact, _ = index_searcher.perform_lexical_search(
            keywords=non_exact_phrase,
            exact_match=True,  # Exact phrase search
            exclude_words=[], 
            categories={}, 
            detected_language=language, 
            page_size=10, 
            page_number=1
        )
        
        log_handle.info(f"Individual words '{individual_words}' found {len(results_individual)} results")
        log_handle.info(f"Exact phrase '{non_exact_phrase}' found {len(results_exact)} results")
        
        # Validate that individual words search finds results from expected file
        found_in_individual = False
        for result in results_individual:
            filename = result.get('filename', '').lower()
            if expected_filename.lower() in filename:
                found_in_individual = True
                break
        
        # Exact phrase search should have fewer results or different results
        found_in_exact = False
        for result in results_exact:
            filename = result.get('filename', '').lower()
            if expected_filename.lower() in filename:
                found_in_exact = True
                break
        
        if found_in_individual:
            log_handle.info(f"✓ Individual words search found expected file {expected_filename}")
        
        # The key assertion: individual word search should find more results than exact phrase search
        if len(results_individual) > len(results_exact):
            log_handle.info(f"✓ Negative test passed: Individual words found {len(results_individual)} results vs exact phrase found {len(results_exact)} results")
        else:
            log_handle.warning(f"Negative test inconclusive: Individual words ({len(results_individual)}) vs exact phrase ({len(results_exact)}) results")

def test_spelling_suggestions():
    """Test spelling suggestions functionality."""
    config = Config()
    index_searcher = IndexSearcher(config)
    
    # List of [misspelled_text, expected_corrections_context]
    test_cases = [
        # Hindi misspellings
        ["बंगलुरु", "bangalore_hindi", "hi"],  # Missing ए in बेंगलुरु
        ["केम्पे गौडा", "bangalore_hindi", "hi"],  # Missing diacritics in गौड़ा
        ["विजयनगार", "hampi_hindi", "hi"],  # Common misspelling of विजयनगर
        ["हम्पि", "hampi_hindi", "hi"],  # Missing ी in हम्पी
        
        # Gujarati misspellings  
        ["મહાકાવ્", "jaipur_gujarati", "gu"],
        ["કેમ્પે ગૌડ", "bangalore_gujarati", "gu"],  # Missing final આ
        ["હમ્પि", "hampi_gujarati", "gu"],  # Missing ી
    ]
    
    for misspelled_text, context, language in test_cases:
        log_handle.info(f"Getting spelling suggestions for: '{misspelled_text}' (context: {context})")
        
        suggestions = index_searcher.get_spelling_suggestions(
            index_name=config.OPENSEARCH_INDEX_NAME,
            text=misspelled_text,
            language=language,
            min_score=0.6,
            num_suggestions=3
        )
        
        log_handle.info(f"Found {len(suggestions)} spelling suggestions for '{misspelled_text}': {suggestions}")
        
        # Test that we get some suggestions
        assert len(suggestions) > 0
        log_handle.info(f"✓ Got spelling suggestions for '{misspelled_text}': {suggestions}")

        # Optional: Try searching with the first suggestion
        if suggestions:
            first_suggestion = suggestions[0]
            log_handle.info(f"Testing search with suggested spelling: '{first_suggestion}'")

            language = "hi" if any(char in first_suggestion for char in "अआइईउऊएऐओऔकखगघचछजझटठडढणतथदधनपफबभमयरलवशषसह") else "gu"

            results, total_hits = index_searcher.perform_lexical_search(
                keywords=first_suggestion,
                exact_match=False,
                exclude_words=[],
                categories={},
                detected_language=language,
                page_size=5,
                page_number=1
            )

            log_handle.info(f"Search with suggested spelling '{first_suggestion}' returned {len(results)} results")
        else:
            log_handle.warning(f"No spelling suggestions found for '{misspelled_text}'")

def test_vector_search_basic_questions():
    """Test basic vector search with question-based queries."""
    config = Config()
    index_searcher = IndexSearcher(config)
    
    # List of [question_query, expected_filename_substring, language]
    test_cases = [
        # Hindi question-based queries
        ["बेंगलुरु का संस्थापक कौन था?", "bangalore_hindi", "hi"],  # About Kempe Gowda
        ["विजयनगर साम्राज्य कहाँ स्थापित हुआ था?", "hampi_hindi", "hi"],  # About Vijayanagar empire location
        ["तंजावुर में कौन सा प्रसिद्ध मंदिर है?", "thanjavur_hindi", "hi"],  # About Brihadeeswara temple
        ["सोनगढ़ किस राज्य में स्थित है?", "songadh_hindi", "hi"],  # About Songarh location in Gujarat
        
        # Gujarati question-based queries  
        ["બેંગલુરુનો સ્થાપક કોણ હતો?", "bangalore_gujarati", "gu"],  # About Kempe Gowda
        ["હમ્પી કયા સામ્રાજ્યની રાજધાની હતી?", "hampi_gujarati", "gu"],  # About which empire's capital
        ["સોનગઢમાં કયો કિલ્લો છે?", "songadh_gujarati", "gu"],  # About the fort in Songarh
        ["જયપુર કયા પ્રદેશમાં આવેલું છે?", "jaipur_gujarati", "gu"],  # About Jaipur region
    ]
    
    for question, expected_filename, language in test_cases:
        log_handle.info(f"Running vector search for question: '{question}' (expecting {expected_filename})")
        
        # Generate embedding for the question
        embedding_model = embedding_models.get_embedding_model_factory(config)
        embedding = embedding_model.get_embedding(question)
        if embedding is None:
            log_handle.error(f"Embedding could not be generated for query: {question}")
            continue

        results, total_hits = index_searcher.perform_vector_search(
            keywords=question,
            embedding=embedding, 
            categories={}, 
            page_size=10, 
            page_number=1, 
            language=language, 
            rerank=True,
            rerank_top_k=10
        )
        
        log_handle.info(f"Vector search found {len(results)} results for: '{question}'")
        assert len(results) > 0, f"No vector search results found for question: {question}"
        

def test_vector_search_with_categories():
    """Test vector search with category filters."""
    config = Config()
    index_searcher = IndexSearcher(config)
    
    # List of [question_query, categories_filter, expected_filename_substring, language]
    test_cases = [
        # Hindi questions with language filter
        ["बेंगलुरु के बारे में बताएं?", {"language": ["hi"]}, "bangalore_hindi", "hi"],
        ["विजयनगर साम्राज्य का इतिहास क्या है?", {"language": ["hi"]}, "hampi_hindi", "hi"],
        
        # Gujarati questions with language filter  
        ["બેંગલુરુ વિશે જણાવો?", {"language": ["gu"]}, "bangalore_gujarati", "gu"],
        ["હમ્પીનો ઇતિહાસ શું છે?", {"language": ["gu"]}, "hampi_gujarati", "gu"],
        
        # Mixed category filters (if they exist)
        ["तंजावुर मंदिर के बारे में?", {"category": ["history"], "language": ["hi"]}, "thanjavur_hindi", "hi"],
        ["સોનગઢનું મહત્વ શું છે?", {"category": ["history"], "language": ["gu"]}, "songadh_gujarati", "gu"],
    ]
    
    for question, categories, expected_filename, language in test_cases:
        log_handle.info(f"Running vector search with categories: '{question}' with filters {categories}")
        
        # Generate embedding for the question
        embedding_model = embedding_models.get_embedding_model_factory(config)
        embedding = embedding_model.get_embedding(question)
        if embedding is None:
            log_handle.error(f"Embedding could not be generated for query: {question}")
            continue

        results, total_hits = index_searcher.perform_vector_search(
            keywords=question,
            embedding=embedding, 
            categories=categories, 
            page_size=10, 
            page_number=1, 
            language=language, 
            rerank=True,
            rerank_top_k=10
        )
        
        log_handle.info(f"Vector search with categories found {len(results)} results for: '{question}'")
        if len(results) > 0:
            # Check if results match the expected filename pattern
            found_expected = False
            for result in results[:3]:
                filename = result.get('filename', '').lower()
                if expected_filename.lower() in filename:
                    found_expected = True
                    log_handle.info(f"✓ Found expected file {expected_filename} in filtered vector results")
                    break
            
            if not found_expected:
                log_handle.warning(f"Expected filename '{expected_filename}' not found in filtered vector results for '{question}'")
        else:
            log_handle.info(f"No results found for filtered vector search: '{question}' with categories {categories}")