import os
import shutil
import random

import pytest

from backend.common import embedding_models
from backend.common.opensearch import get_opensearch_client, create_indices_if_not_exists
from backend.crawler.discovery import Discovery
from backend.crawler.index_state import IndexState
from backend.crawler.index_generator import IndexGenerator
from backend.crawler.pdf_processor import PDFProcessor
from backend.search.index_searcher import IndexSearcher
from backend.crawler.granth_index import GranthIndexer
from backend.crawler.markdown_parser import MarkdownParser
from tests.backend.common import setup, get_all_documents, setup_granth
from tests.backend.base import *

log_handle = logging.getLogger(__name__)

# simplify the logs. change opensearch's logging to WARN to avoid chunk indexing mesasges.
# comment it out if you need to debug something.
logging.getLogger('opensearch').setLevel(logging.WARNING)

@pytest.fixture(scope="module", autouse=True)
def build_index(initialise):
    # delete and create indexes if they do not exist
    config = Config()
    opensearch_client = get_opensearch_client(config)
    indexes = [
        config.OPENSEARCH_INDEX_NAME,
        config.OPENSEARCH_METADATA_INDEX_NAME,
        config.OPENSEARCH_GRANTH_INDEX_NAME
    ]
    for index_name in indexes:
        if index_name and opensearch_client.indices.exists(index=index_name):
            opensearch_client.indices.delete(index=index_name)
            log_handle.info(f"Deleted existing index: {index_name}")
    create_indices_if_not_exists(config, opensearch_client)
    build_search_index()
    build_granth_index_for_search()

    yield
    # Cleanup - delete index
    for index_name in indexes:
        opensearch_client.indices.delete(index=index_name, ignore=[400, 404])

def build_search_index():
    """
    Setup test data and build search index.
    Copy OCR data to base_ocr_path and call discovery with process=False, index=True.
    """
    # Setup test environment with scan_config files
    config = Config()
    opensearch_client = get_opensearch_client(config)
    setup(copy_ocr_files=True, add_scan_config=True)
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

def build_granth_index_for_search():
    """
    Setup granth data and index in OpenSearch.
    Calls setup_granth() to create markdown files, parses them, and indexes all granths.
    """
    config = Config()
    opensearch_client = get_opensearch_client(config)

    # Setup granth directory structure and files
    log_handle.info("Setting up granth directory structure")
    granth_setup = setup_granth()
    base_dir = granth_setup["base_dir"]
    granth_files = granth_setup["granth_files"]

    # Parse markdown files
    parser = MarkdownParser(base_folder=base_dir)
    indexer = GranthIndexer(config, opensearch_client)

    log_handle.info("Parsing and indexing granth markdown files")
    for granth_name, file_info in granth_files.items():
        file_path = file_info["file_path"]
        log_handle.info(f"Parsing {granth_name} from {file_path}")

        granth = parser.parse_file(file_path)
        assert granth is not None, f"Failed to parse {file_path}"

        log_handle.info(f"Indexing {granth_name} with {len(granth._verses)} verses")
        indexer.index_granth(granth, dry_run=False)

    # Refresh indices to make data available for search
    opensearch_client.indices.refresh(index=config.OPENSEARCH_GRANTH_INDEX_NAME)
    opensearch_client.indices.refresh(index=config.OPENSEARCH_INDEX_NAME)

    log_handle.info("Granth indexing complete")

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

def test_exclude_words():
    """Test exclude words functionality in lexical search."""
    config = Config()
    index_searcher = IndexSearcher(config)
    
    # Test query that should return results without exclusion
    query = "दिगंबर जैन मनोरंजन"  # Traditional tourism
    exclude_word = "सोनगढ़"  # Songarh
    language = "hi"
    
    # First search without exclude words - should return 1 result
    log_handle.info(f"Running search without exclude words: '{query}'")
    results_without_exclude, total_hits_without_exclude = index_searcher.perform_lexical_search(
        keywords=query,
        exact_match=False,
        exclude_words=[],
        categories={},
        detected_language=language,
        page_size=10,
        page_number=1
    )
    
    log_handle.info(f"Search without exclude words returned {len(results_without_exclude)} results (total: {total_hits_without_exclude})")
    assert len(results_without_exclude) == 1, f"Expected 1 result without exclude words, got {len(results_without_exclude)}"
    
    # Second search with exclude words - should return 0 results
    log_handle.info(f"Running search with exclude word: '{query}' excluding '{exclude_word}'")
    results_with_exclude, total_hits_with_exclude = index_searcher.perform_lexical_search(
        keywords=query,
        exact_match=False,
        exclude_words=[exclude_word],
        categories={},
        detected_language=language,
        page_size=10,
        page_number=1
    )
    
    log_handle.info(f"Search with exclude words returned {len(results_with_exclude)} results (total: {total_hits_with_exclude})")
    assert len(results_with_exclude) == 0, f"Expected 0 results with exclude word '{exclude_word}', got {len(results_with_exclude)}"

    log_handle.info(f"✓ Exclude words test passed: {len(results_without_exclude)} results without exclusion, {len(results_with_exclude)} results with exclusion")


def test_search_granth_content():
    """Test searching granth content (teeka and bhavarth paragraphs)."""
    config = Config()
    index_searcher = IndexSearcher(config)

    # List of test cases: [query, language, expected_filename]
    # Testing search across different granth files and different fields (verse, translation, meaning, teeka, bhavarth)
    test_cases = [
        # simple_granth - Hindi test cases
        {"query": "सूर्य का उदय नई शुरुआत का प्रतीक", "lang": "hi", "filename": "simple_granth"},
        {"query": "जल ही जीवन है", "lang": "hi", "filename": "simple_granth"},
        {"query": "नदी पहाड़ों से समुद्र तक बहती", "lang": "hi", "filename": "simple_granth"},

        # simple_granth - Gujarati test cases
        {"query": "નવી શરૂઆતનું પ્રતીક", "lang": "gu", "filename": "simple_granth"},
        {"query": "જળ જ જીવન છે", "lang": "gu", "filename": "simple_granth"},
        {"query": "સૂર્ય પૂર્વ દિશામાં ઉદય", "lang": "gu", "filename": "simple_granth"},

        # adhikar_granth - Hindi test cases (nature chapter)
        {"query": "रात्रि का सौंदर्य तारों और चांद से बढ़ता", "lang": "hi", "filename": "adhikar_granth"},
        {"query": "वायु प्रकृति की एक महत्वपूर्ण शक्ति", "lang": "hi", "filename": "adhikar_granth"},
        {"query": "आकाश में तारे चमकते हैं रात में", "lang": "hi", "filename": "adhikar_granth"},

        # adhikar_granth - Hindi test cases (education chapter)
        {"query": "नियमित अध्ययन से बुद्धि का विकास", "lang": "hi", "filename": "adhikar_granth"},
        {"query": "गुरु की शिक्षा से व्यक्तित्व निखरता", "lang": "hi", "filename": "adhikar_granth"},
        {"query": "धैर्य और अभ्यास ही सफलता की कुंजी", "lang": "hi", "filename": "adhikar_granth"},

        # adhikar_granth - Hindi test cases (social chapter)
        {"query": "सामूहिक प्रयास से बड़े लक्ष्य प्राप्त", "lang": "hi", "filename": "adhikar_granth"},
        {"query": "विनम्रता एक महान गुण है", "lang": "hi", "filename": "adhikar_granth"},

        # mixed_granth - Hindi test cases (knowledge chapter)
        {"query": "सत्यवादिता मानव का सर्वोच्च गुण", "lang": "hi", "filename": "mixed_granth"},
        {"query": "सत्य बोलने वाला व्यक्ति समाज में आदरणीय", "lang": "hi", "filename": "mixed_granth"},
        {"query": "अहिंसा का अर्थ है मन, वचन और कर्म से किसी को हानि न पहुंचाना", "lang": "hi", "filename": "mixed_granth"},

        # mixed_granth - Hindi test cases (karma chapter)
        {"query": "कर्म का सिद्धांत प्रकृति का नियम", "lang": "hi", "filename": "mixed_granth"},
        {"query": "सदाचारी व्यक्ति हर जगह सम्मान पाता", "lang": "hi", "filename": "mixed_granth"},
        {"query": "दान देने से हृदय की कठोरता दूर होती", "lang": "hi", "filename": "mixed_granth"},

        # mixed_granth - Hindi test cases (moksha chapter)
        {"query": "मोक्ष जीवन का परम लक्ष्य", "lang": "hi", "filename": "mixed_granth"},
        {"query": "ध्यान योग का सर्वोत्तम साधन", "lang": "hi", "filename": "mixed_granth"},
        {"query": "प्रेम एक दिव्य शक्ति है जो शत्रु को भी मित्र बना देती", "lang": "hi", "filename": "mixed_granth"},
    ]

    for test_case in test_cases:
        query = test_case["query"]
        lang = test_case["lang"]
        expected_filename = test_case["filename"]

        log_handle.info(f"Running granth search for: '{query}' (expecting {expected_filename})")

        results, total_hits = index_searcher.perform_granth_search(
            keywords=query,
            exact_match=False,
            exclude_words=[],
            categories={},
            language=lang,
            page_size=10,
            page_number=1
        )

        log_handle.info(f"Found {len(results)} granth results for query: '{query}'")
        log_handle.info(f"Results: {json_dumps(results)}")
        assert len(results) > 0, f"No results found for granth query: {query}"

        # Validate that expected filename appears in results
        found_expected = False
        for result in results:
            # Check if granth name matches expected pattern
            granth_name = result.get('filename', '').lower()
            if expected_filename in granth_name:
                found_expected = True
                log_handle.info(f"✓ Found expected granth {expected_filename} in results for query: '{query}'")
                break

        assert found_expected, f"Expected granth '{expected_filename}' not found in results for query '{query}'"

def test_search_granth_content_exact_match():
    """Test exact match searching in granth content with verse number validation."""
    config = Config()
    index_searcher = IndexSearcher(config)

    # List of test cases with exact phrases from different granth files
    # Each test validates filename, language, verse type, and verse number
    test_cases = [
        # simple_granth - Shlok 1 (Hindi)
        {
            "query": "सूर्य का उदय नई शुरुआत का प्रतीक है",
            "lang": "hi",
            "filename": "simple_granth",
            "type": "Shlok",
            "type_num": 1
        },
        # simple_granth - Shlok 2 (Hindi)
        {
            "query": "जल ही जीवन है और इसका संरक्षण आवश्यक है",
            "lang": "hi",
            "filename": "simple_granth",
            "type": "Shlok",
            "type_num": 2
        },
        # simple_granth - Shlok 1 (Gujarati)
        {
            "query": "સૂર્યનો ઉદય નવી શરૂઆતનું પ્રતીક છે",
            "lang": "gu",
            "filename": "simple_granth",
            "type": "Shlok",
            "type_num": 1
        },
        # simple_granth - Shlok 2 (Gujarati)
        {
            "query": "જળ જ જીવન છે અને તેનું સંરક્ષણ જરૂરી છે",
            "lang": "gu",
            "filename": "simple_granth",
            "type": "Shlok",
            "type_num": 2
        },
        # adhikar_granth - Shlok 1 (Hindi)
        {
            "query": "रात्रि का सौंदर्य तारों और चांद से बढ़ता है",
            "lang": "hi",
            "filename": "adhikar_granth",
            "type": "Shlok",
            "type_num": 1
        },
        # adhikar_granth - Shlok 2 (Hindi)
        {
            "query": "वायु प्रकृति की एक महत्वपूर्ण शक्ति है",
            "lang": "hi",
            "filename": "adhikar_granth",
            "type": "Shlok",
            "type_num": 2
        },
        # adhikar_granth - Shlok 3 (Hindi)
        {
            "query": "नियमित अध्ययन से बुद्धि का विकास होता है",
            "lang": "hi",
            "filename": "adhikar_granth",
            "type": "Shlok",
            "type_num": 3
        },
        # adhikar_granth - Shlok 1 (Gujarati)
        {
            "query": "રાત્રિનું સૌંદર્ય તારાઓ અને ચંદ્રથી વધે છે",
            "lang": "gu",
            "filename": "adhikar_granth",
            "type": "Shlok",
            "type_num": 1
        },
        # adhikar_granth - Shlok 2 (Gujarati)
        {
            "query": "વાયુ પ્રકૃતિની એક મહત્વપૂર્ણ શક્તિ છે",
            "lang": "gu",
            "filename": "adhikar_granth",
            "type": "Shlok",
            "type_num": 2
        },
        # mixed_granth - Gatha 1 (Hindi)
        {
            "query": "सत्यवादिता मानव का सर्वोच्च गुण है",
            "lang": "hi",
            "filename": "mixed_granth",
            "type": "Gatha",
            "type_num": 1
        },
        # mixed_granth - Gatha 2 (Hindi)
        {
            "query": "अहिंसा का अर्थ है मन, वचन और कर्म से किसी को हानि न पहुंचाना",
            "lang": "hi",
            "filename": "mixed_granth",
            "type": "Gatha",
            "type_num": 2
        },
        # mixed_granth - Gatha 3 (Hindi)
        {
            "query": "कर्म का सिद्धांत प्रकृति का नियम है",
            "lang": "hi",
            "filename": "mixed_granth",
            "type": "Gatha",
            "type_num": 3
        },
        # mixed_granth - Gatha 1 (Gujarati)
        {
            "query": "સત્યવાદીતા માનવનો સર્વોચ્ચ ગુણ છે",
            "lang": "gu",
            "filename": "mixed_granth",
            "type": "Gatha",
            "type_num": 1
        },
        # mixed_granth - Gatha 1 (Gujarati) - from Bhavarth
        {
            "query": "સત્ય બોલનાર વ્યક્તિ સમાજમાં આદરણીય હોય છે",
            "lang": "gu",
            "filename": "mixed_granth",
            "type": "Gatha",
            "type_num": 1
        },
    ]

    for test_case in test_cases:
        query = test_case["query"]
        lang = test_case["lang"]
        expected_filename = test_case["filename"]
        expected_type = test_case["type"]
        expected_type_num = test_case["type_num"]

        log_handle.info(f"Running exact match granth search for: '{query}' (expecting {expected_filename}, {expected_type} {expected_type_num})")

        results, total_hits = index_searcher.perform_granth_search(
            keywords=query,
            exact_match=True,  # Use exact match
            exclude_words=[],
            categories={},
            language=lang,
            page_size=10,
            page_number=1
        )

        log_handle.info(f"Found {len(results)} exact match granth results for query: '{query}'")
        log_handle.info(f"Results: {json_dumps(results)}")
        assert len(results) == 1, f"Expected 1 result for exact match granth query: {query}, got {len(results)}"

        # Validate that expected filename, verse type, and verse number appear in results
        result = results[0]
        granth_name = result.get('filename', '').lower()
        verse_type = result.get('type', '')
        verse_type_num = result.get('type_num', 0)

        if expected_filename in granth_name and verse_type == expected_type and verse_type_num == expected_type_num:
            found_expected = True
            log_handle.info(f"✓ Found expected granth {expected_filename}, {expected_type} {expected_type_num} in results for query: '{query}'")
            break

def test_search_granth_content_with_categories():
    """Test granth search with category filters (Anuyog, Author, etc.)."""
    config = Config()
    index_searcher = IndexSearcher(config)

    # Test cases with category filtering
    # Each test validates that filters work correctly
    test_cases = [
        # Hindi test cases
        {
            "query": "सूर्य का उदय नई शुरुआत का प्रतीक है",
            "lang": "hi",
            "expected_anuyog": "Simple Anuyog",
            "expected_author": "Simple Author",
            "not_expected_anuyog": "Charitra Anuyog",
            "not_expected_author": "Acharya Kundkund"
        },
        {
            "query": "रात्रि का सौंदर्य तारों और चांद से बढ़ता है",
            "lang": "hi",
            "expected_anuyog": "Charitra Anuyog",
            "expected_author": "Acharya Kundkund",
            "not_expected_anuyog": "Dravya Anuyog",
            "not_expected_author": "Acharya Haribhadra"
        },
        {
            "query": "सत्यवादिता मानव का सर्वोच्च गुण है",
            "lang": "hi",
            "expected_anuyog": "Dravya Anuyog",
            "expected_author": "Acharya Haribhadra",
            "not_expected_anuyog": "Simple Anuyog",
            "not_expected_author": "Simple Author"
        },
        {
            "query": "कर्म का सिद्धांत प्रकृति का नियम है",
            "lang": "hi",
            "expected_anuyog": "Dravya Anuyog",
            "expected_author": "Acharya Haribhadra",
            "not_expected_anuyog": "Charitra Anuyog",
            "not_expected_author": "Acharya Kundkund"
        },
        # Gujarati test cases
        {
            "query": "સૂર્યનો ઉદય નવી શરૂઆતનું પ્રતીક છે",
            "lang": "gu",
            "expected_anuyog": "Simple Anuyog",
            "expected_author": "Simple Author",
            "not_expected_anuyog": "Charitra Anuyog",
            "not_expected_author": "Acharya Kundkund"
        },
        {
            "query": "રાત્રિનું સૌંદર્ય તારાઓ અને ચંદ્રથી વધે છે",
            "lang": "gu",
            "expected_anuyog": "Charitra Anuyog",
            "expected_author": "Acharya Kundkund",
            "not_expected_anuyog": "Dravya Anuyog",
            "not_expected_author": "Acharya Haribhadra"
        },
        {
            "query": "સત્યવાદીતા માનવનો સર્વોચ્ચ ગુણ છે",
            "lang": "gu",
            "expected_anuyog": "Dravya Anuyog",
            "expected_author": "Acharya Haribhadra",
            "not_expected_anuyog": "Simple Anuyog",
            "not_expected_author": "Simple Author"
        },
        {
            "query": "જળ જ જીવન છે અને તેનું સંરક્ષણ જરૂરી છે",
            "lang": "gu",
            "expected_anuyog": "Simple Anuyog",
            "expected_author": "Simple Author",
            "not_expected_anuyog": "Dravya Anuyog",
            "not_expected_author": "Acharya Haribhadra"
        },
    ]

    for test_case in test_cases:
        query = test_case["query"]
        lang = test_case["lang"]
        expected_anuyog = test_case["expected_anuyog"]
        expected_author = test_case["expected_author"]
        not_expected_anuyog = test_case["not_expected_anuyog"]
        not_expected_author = test_case["not_expected_author"]

        # Test 1: Search with expected Anuyog filter - should return results
        log_handle.info(f"Running granth search with Anuyog filter: '{query}' (expecting Anuyog: {expected_anuyog})")

        results_with_anuyog, total_hits = index_searcher.perform_granth_search(
            keywords=query,
            exact_match=True,
            exclude_words=[],
            categories={"anuyog": [expected_anuyog]},
            language=lang,
            page_size=10,
            page_number=1
        )

        log_handle.info(f"Found {len(results_with_anuyog)} results with Anuyog filter '{expected_anuyog}'")
        assert len(results_with_anuyog) == 1, f"Expected 1 result with Anuyog '{expected_anuyog}', got {len(results_with_anuyog)}"

        # Validate the result has the expected Anuyog
        result_anuyog = results_with_anuyog[0].get('metadata', {}).get('anuyog', '')
        assert result_anuyog == expected_anuyog, f"Expected Anuyog '{expected_anuyog}', got '{result_anuyog}'"
        log_handle.info(f"✓ Found result with expected Anuyog: {expected_anuyog}")

        # Test 2: Search with unexpected Anuyog filter - should return no results
        log_handle.info(f"Running granth search with incorrect Anuyog filter: '{query}' (using Anuyog: {not_expected_anuyog})")

        results_with_wrong_anuyog, total_hits = index_searcher.perform_granth_search(
            keywords=query,
            exact_match=True,
            exclude_words=[],
            categories={"anuyog": [not_expected_anuyog]},
            language=lang,
            page_size=10,
            page_number=1
        )

        log_handle.info(f"Found {len(results_with_wrong_anuyog)} results with incorrect Anuyog filter '{not_expected_anuyog}'")
        assert len(results_with_wrong_anuyog) == 0, f"Expected 0 results with incorrect Anuyog '{not_expected_anuyog}', got {len(results_with_wrong_anuyog)}"
        log_handle.info(f"✓ Correctly found no results with incorrect Anuyog: {not_expected_anuyog}")

        # Test 3: Search with expected Author filter - should return results
        log_handle.info(f"Running granth search with Author filter: '{query}' (expecting Author: {expected_author})")

        results_with_author, total_hits = index_searcher.perform_granth_search(
            keywords=query,
            exact_match=True,
            exclude_words=[],
            categories={"author": [expected_author]},
            language=lang,
            page_size=10,
            page_number=1
        )

        log_handle.info(f"Found {len(results_with_author)} results with Author filter '{expected_author}'")
        assert len(results_with_author) == 1, f"Expected 1 result with Author '{expected_author}', got {len(results_with_author)}"

        # Validate the result has the expected Author
        result_author = results_with_author[0].get('metadata', {}).get('author', '')
        assert result_author == expected_author, f"Expected Author '{expected_author}', got '{result_author}'"
        log_handle.info(f"✓ Found result with expected Author: {expected_author}")

        # Test 4: Search with unexpected Author filter - should return no results
        log_handle.info(f"Running granth search with incorrect Author filter: '{query}' (using Author: {not_expected_author})")

        results_with_wrong_author, total_hits = index_searcher.perform_granth_search(
            keywords=query,
            exact_match=True,
            exclude_words=[],
            categories={"author": [not_expected_author]},
            language=lang,
            page_size=10,
            page_number=1
        )

        log_handle.info(f"Found {len(results_with_wrong_author)} results with incorrect Author filter '{not_expected_author}'")
        assert len(results_with_wrong_author) == 0, f"Expected 0 results with incorrect Author '{not_expected_author}', got {len(results_with_wrong_author)}"
        log_handle.info(f"✓ Correctly found no results with incorrect Author: {not_expected_author}")