import logging
import os
import tempfile
import uuid
import shutil
import logging
import time
import fitz

from backend.config import Config
from backend.crawler.discovery import Discovery
from backend.crawler.index_state import IndexState
from backend.index.embedding_module import IndexingEmbeddingModule
from backend.common.opensearch import get_opensearch_client, get_metadata
from backend.processor.pdf_processor import PDFProcessor
from backend.utils import json_dump, json_dumps
from tests.backend.base import *
from tests.backend import common
from tests.backend.common import are_dicts_same

log_handle = logging.getLogger(__name__)

# simplify the logs. change opensearch's logging to WARN to avoid chunk indexing mesasges.
# comment it out if you need to debug something.
logging.getLogger('opensearch').setLevel(logging.WARNING)

@pytest.mark.integration
def test_full_integration(initialise):
    config = Config()
    doc_ids = common.setup()
    index_state = IndexState(config.SQLITE_DB_PATH)
    opensearch_client = get_opensearch_client(config, force_clean=True)

    log_handle.info(f"Starting discovery with config: {json_dumps(config._settings)}")

    discovery = Discovery(
        config,
        IndexingEmbeddingModule(config, opensearch_client),
        PDFProcessor(config),
        index_state
    )

    discovery.crawl()

    ###########################################

    # total number of unique documents indexed should be 7
    log_handle.info(f"Test 1: re-crawling after changing file content")
    opensearch_client.indices.refresh(index=config.OPENSEARCH_INDEX_NAME)
    time.sleep(3)

    query = {
       "aggs": {
           "unique_document_ids": {
               "terms": {
                   "field": "document_id",
                   "size": 10000
               }
           }
       },
       "size": 0,
        "track_total_hits": True
    }
    response = opensearch_client.search(body=query, index=config.OPENSEARCH_INDEX_NAME)
    buckets = response["aggregations"]["unique_document_ids"]["buckets"]
    log_handle.verbose(f"Buckets: {json_dumps(buckets)}")
    assert len(buckets) == 7

    # assert that buckets has the same doc_ids
    only_doc_ids = [value[1] for value in doc_ids.values()]
    for item in buckets:
        assert item["key"] in only_doc_ids
    log_handle.info(f"Test 1 Passed")

    ###########################################

    # write a query
    log_handle.info(f"Test 2: search by query")
    query = {
        "query": {
            "span_near": {
                "clauses": [
                    { "span_term": { "text_content_hindi": "सुखद" } },
                    { "span_term": { "text_content_hindi": "प्रौद्योगिकी" } },
                    { "span_term": { "text_content_hindi": "जलवायु" } },
                    { "span_term": { "text_content_hindi": "भारत" } }
                ],
                "slop": 50,
                "in_order": False
            }
        },
        "_source": {
            "excludes": ["vector_embedding"]
        }
    }
    response = opensearch_client.search(
        body=query, index=config.OPENSEARCH_INDEX_NAME
    )
    hits = response['hits']['hits']
    assert len(hits) == 2
    fnames = ["a/bangalore_hindi.pdf", "a/b/c/bangalore_hindi.pdf"]
    assert {hit["_source"]["original_filename"] in fnames for hit in hits}
    log_handle.info(f"Test 2 Passed")

    ###########################################

    # search by filtering on a category
    log_handle.info(f"Test 3: search by category")
    query = {
         "aggs": {
             "unique_original_filenames": {
                 "terms": {
                     "field": "original_filename",
                     "size": 100  # Adjust this to the maximum number of unique filenames you expect
                 }
             }
         },
         "size": 0,  # Set size to 0 to only get aggregation results, not actual documents
        "query": {
            "terms": {
                "metadata.category.keyword": ["x", "b"] # Your existing query to filter documents
            }
        },
        "_source": {
            "excludes": "vector_embedding"
        },
        "track_total_hits": True
    }
    response = opensearch_client.search(body=query, index=config.OPENSEARCH_INDEX_NAME)
    buckets = response["aggregations"]["unique_original_filenames"]["buckets"]
    fnames = ["a/b/bangalore_english.pdf", "a/b/c/bangalore_hindi.pdf",
              "a/b/c/bangalore_gujarati.pdf", "x/bangalore_gujarati.pdf",
              "a/b/d/multi_language_document.pdf"]
    assert len(buckets) == len(fnames)
    assert {fname in fnames for fname, _ in buckets}
    log_handle.info(f"Test 3 Passed")

    ###########################################

    # change metadata file of one folder. reindex. confirm that things have changed.
    log_handle.info(f"Test 4: re-crawling after changing metadata")
    new_config = {"category": "updated_category", "type": "t1", "new": "blah"}
    common.write_config_file("%s/a/b/config.json" % config.BASE_PDF_PATH, new_config)
    os_old_docs = common.get_all_documents()
    discovery.crawl()

    changed_keys = [
        doc_ids["abcbh"][1],
        doc_ids["abcbg"][1],
        doc_ids["abbeng"][1],
        doc_ids["abdmld"][1]
    ]
    opensearch_client.indices.refresh(index=config.OPENSEARCH_INDEX_NAME)
    os_new_docs = common.get_all_documents()
    validate_changed_docs_timestamp(
        os_old_docs, os_new_docs, changed_keys, None,
    )

    query = {
        "aggs": {
            "unique_document_ids": {
                "terms": {
                    "field": "document_id",
                    "size": 100  # Adjust this to the maximum number of unique filenames you expect
                }
            }
        },
        "size": 0,  # Set size to 0 to only get aggregation results, not actual documents
        "query": {
            "terms": {
                "metadata.category.keyword": ["updated_category"] # Your existing query to filter documents
            }
        },
        "_source": {
            "excludes": "vector_embedding"
        },
        "track_total_hits": True
    }
    response = opensearch_client.search(
        body=query, index=config.OPENSEARCH_INDEX_NAME
    )
    log_handle.info(f"Response: {json_dumps(response)}")
    buckets = response["aggregations"]["unique_document_ids"]["buckets"]
    assert len(buckets) == len(changed_keys)
    assert {docid in changed_keys for docid, _ in buckets}
    log_handle.info(f"Test 4 Passed")

    ###########################################

    # change the  same config_json
    log_handle.info(f"Test 5: re-crawling after changing metadata")
    xbg = { "category": "c", "type": "t3", "new": "blah2" }
    fname = doc_ids["xbg"][0]
    config_fname = fname.replace(".pdf", "_config.json")
    common.write_config_file(config_fname, xbg)

    changed_keys = [doc_ids["xbg"][1]]
    os_old_docs = common.get_all_documents()
    discovery.crawl()
    opensearch_client.indices.refresh(index=config.OPENSEARCH_INDEX_NAME)
    os_new_docs = common.get_all_documents()
    validate_changed_docs_timestamp(
        os_old_docs, os_new_docs, changed_keys, None,
    )
    query = {
        "aggs": {
            "unique_document_ids": {
                "terms": {
                    "field": "document_id",
                    "size": 100  # Adjust this to the maximum number of unique filenames you expect
                }
            }
        },
        "size": 0,  # Set size to 0 to only get aggregation results, not actual documents
        "query": {
            "terms": {
                "metadata.new": ["blah2"] # Your existing query to filter documents
            }
        },
        "_source": {
            "excludes": "vector_embedding"
        },
        "track_total_hits": True
    }
    response = opensearch_client.search(body=query, index=config.OPENSEARCH_INDEX_NAME)
    log_handle.info(f"Response: {json_dumps(response)}")
    buckets = response["aggregations"]["unique_document_ids"]["buckets"]
    assert len(buckets) == len(changed_keys)
    assert {docid in changed_keys for docid, _ in buckets}
    log_handle.info(f"Test 5 Passed")

    ###########################################

    # change data in a file. should be full-reindex
    log_handle.info(f"Test 6: re-crawling after changing file content")
    xyzmld = doc_ids["xyzmld"][0]
    changed_keys = [doc_ids["xyzmld"][1]]
    add_bookmark_to_pdf(xyzmld, "new_bookmark", 1)

    # get original last_indexed_times
    query = {
        "query": {
            "match_all": {}
        },
        "_source": {
            "includes": [
                "document_id",
                "timestamp_indexed",
                "bookmarks"
            ],
            "excludes": ["vector_embedding"]
        },
        "size": 10000,
        "track_total_hits": True
    }
    response = opensearch_client.search(body=query, index=config.OPENSEARCH_INDEX_NAME)
    old_hits = parse_opensearch_hits(response["hits"]["hits"])
    log_handle.verbose(f"Old hits: {json_dumps(old_hits)}")

    discovery.crawl()
    opensearch_client.indices.refresh(index=config.OPENSEARCH_INDEX_NAME)
    response = opensearch_client.search(body=query, index=config.OPENSEARCH_INDEX_NAME)
    new_hits = parse_opensearch_hits(response["hits"]["hits"])
    log_handle.verbose(f"New hits: {json_dumps(new_hits)}")

    for docid in old_hits:
        old_data = old_hits[docid]
        new_data = new_hits[docid]
        if old_data["document_id"] in changed_keys:
            # values shouldn't match
            assert old_data["bookmarks"] != new_data["bookmarks"]
            assert old_data["timestamp_indexed"] != new_data["timestamp_indexed"]

    log_handle.info(f"Test 6 Passed")

    ###########################################

    # delete a file. it should no longer show in all_documents
    log_handle.info(f"Test 7: re-crawling after deleting file")

    os.remove(doc_ids["abbeng"][0])

    discovery.crawl()
    opensearch_client.indices.refresh(index=config.OPENSEARCH_INDEX_NAME)

    # get all documents
    query = {
        "query": {"match_all": {}},
        "_source": {
            "includes": [
                "document_id",
                "timestamp_indexed",
                "bookmarks",
                "original_filename"
            ],
            "excludes": ["vector_embedding"]
        },
        "size": 10000,
        "track_total_hits": True
    }
    response = opensearch_client.search(body=query, index=config.OPENSEARCH_INDEX_NAME)
    hits = parse_opensearch_hits(response["hits"]["hits"])
    log_handle.verbose(f"Hits: {json_dumps(hits)}")

    assert doc_ids["abbeng"][1] not in hits
    assert all(one_hit.get("document_id") in only_doc_ids for one_hit in hits.values()), \
    "Not all document_ids from hits are present in all_doc_ids."

    log_handle.info(f"Test 7 Passed")

    ###########################################

    # add a file. it should be indexed
    log_handle.info(f"Test 8: re-crawling after adding a file")
    new_file_path = "%s/x/y/test_8_file.pdf" % config.BASE_PDF_PATH
    shutil.copy(doc_ids["abdmld"][0], new_file_path)

    os_all_docs_old = common.get_all_documents()
    validate_total_num_docs(os_all_docs_old, 7)
    discovery.crawl()
    opensearch_client.indices.refresh(index=config.OPENSEARCH_INDEX_NAME)
    os_all_docs_new = common.get_all_documents()
    validate_total_num_docs(os_all_docs_new, 8)
    validate_changed_docs_timestamp(
        os_all_docs_old, os_all_docs_new, None, [doc_ids["abdmld"][1]]
    )
    log_handle.info(f"Test 8 Passed")

    ###########################################
    log_handle.info(f"Test 9: test metadata in OpenSearch and IndexState")
    index_state = IndexState(config.SQLITE_DB_PATH)
    metadata_os = get_metadata(config)
    index_state.update_metadata_cache(metadata_os)
    metadata_is = index_state.get_metadata_cache()
    assert are_dicts_same(metadata_os, metadata_is)
    log_handle.info(f"Test 9 Passed")


def add_bookmark_to_pdf(pdf_path, bookmark_name, page_number):
    doc = None
    # Define a temporary path for the new file
    temp_pdf_path = tempfile.mkstemp(suffix=".temp.pdf")[1]

    try:
        doc = fitz.open(pdf_path)
        toc = doc.get_toc()

        # Add the new bookmark
        toc.append([1, bookmark_name, page_number])

        doc.set_toc(toc)

        # Save the changes to the temporary file (this is a full rewrite)
        doc.save(temp_pdf_path, garbage=4, deflate=True, clean=True)
    except Exception as e:
        log_handle.error(f"An error occurred during PDF modification: {e}")
        # If the temp file was created, clean it up
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
        return  # Exit the function on error
    finally:
        if doc:
            doc.close()

    try:
        # If saving was successful, replace the original file with the new one
        os.replace(temp_pdf_path, pdf_path)
        log_handle.verbose(f"Successfully added bookmark '{bookmark_name}' to page {page_number}.")
        log_handle.verbose(f"The file '{pdf_path}' has been updated.")
    except Exception as e:
        log_handle.error(f"An error occurred during file replacement: {e}")

def parse_opensearch_hits(hits_list):
    """
    Parses a list of OpenSearch hit dictionaries and extracts
    _id, timestamp_indexed, bookmarks, and document_id.
    Timestamp is converted to datetime objects.

    Args:
        hits_list (list): A list of dictionaries, where each dictionary
                          represents an OpenSearch hit (containing '_id' and '_source').

    Returns:
        dict: A dictionary mapping _id to a dictionary of parsed field values.
              Example: { "_id_val": {"timestamp_indexed": datetime_obj, "bookmarks": "...", "document_id": "..."}, ... }
              Returns an empty dictionary if input is None or empty.
    """
    parsed_data = {}
    if not hits_list:
        return parsed_data

    for hit in hits_list:
        _id = hit.get("_id")
        source = hit.get("_source")
        if _id and source:
            timestamp_str = source.get("timestamp_indexed")
            bookmarks = source.get("bookmarks")
            document_id = source.get("document_id") # Keep this for special comparison
            filename = source.get("original_filename")

            parsed_data[_id] = {
                "timestamp_indexed": timestamp_str,
                "bookmarks": bookmarks,
                "document_id": document_id,
                "filename": filename
            }
    return parsed_data

def validate_total_num_docs(os_all_docs, expected_count):
    """
    Validates the total number of documents in OpenSearch.

    Args:
        os_all_docs (list): List of all documents retrieved from OpenSearch.
        expected_count (int): Expected number of documents.

    Returns:
        bool: True if the count matches, False otherwise.
    """
    if not os_all_docs:
        log_handle.error("No documents found in OpenSearch.")
        return False

    doc_ids = set()
    for hit in os_all_docs:
        doc_id = hit.get("_source", {}).get("document_id")
        if doc_id:
            doc_ids.add(doc_id)
    assert len(doc_ids) == expected_count, "Document IDs are not unique."

def validate_changed_docs_timestamp(
    old_hits, new_hits, changed_keys, ignore_keys=None):
    """
    Validates that the timestamps of changed documents have been updated.

    Args:
        old_hits (dict): Dictionary of old hits with document_id as keys.
        new_hits (dict): Dictionary of new hits with document_id as keys.
        changed_keys (list): List of document IDs that should have changed.
        ignore_keys (list): Optional list of document IDs *in old_hits* to ignore.

    Returns:
        bool: True if validation passes, False otherwise.
    """
    parsed_old_hits = parse_opensearch_hits(old_hits)
    parsed_new_hits = parse_opensearch_hits(new_hits)


    for doc_id in parsed_old_hits:
        if ignore_keys and doc_id in ignore_keys:
            continue
        old_data = parsed_old_hits[doc_id]
        new_data = parsed_new_hits[doc_id]

        if changed_keys and old_data["document_id"] in changed_keys:
            assert old_data["timestamp_indexed"] != new_data["timestamp_indexed"], \
                f"Timestamp for {doc_id} did not change as expected."
        else:
            assert old_data["timestamp_indexed"] == new_data["timestamp_indexed"], \
                f"Timestamp for {doc_id} changed unexpectedly."