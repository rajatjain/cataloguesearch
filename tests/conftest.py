import pytest

@pytest.fixture(scope="session")
def bookmark_cache():
    """
    Session-scoped bookmark cache for CachedBookmarkExtractor.

    This cache is shared across ALL test files in the entire pytest session,
    dramatically reducing test time by avoiding redundant LLM calls for the
    same bookmarks.

    The cache maps hash(indexed_titles) -> LLM response, making it
    self-invalidating when bookmarks change.

    Expected savings: ~19 minutes (88 LLM calls → ~12 LLM calls)
    """
    cache = {}
    yield cache
    # Log cache statistics at end of session
    print(f"\n📊 Bookmark Cache Statistics:")
    print(f"   Total cached entries: {len(cache)}")


@pytest.fixture(scope="session", autouse=True)
def enable_bookmark_caching_for_tests(bookmark_cache):
    """
    Automatically enable bookmark caching for all tests.

    This fixture runs once at the start of the test session and enables
    caching by monkey-patching the bookmark extractor factory.

    The autouse=True means this runs automatically without being explicitly
    requested by tests.
    """
    from tests.backend.bookmark_cache_helper import enable_bookmark_caching, disable_bookmark_caching

    # Enable caching at session start
    enable_bookmark_caching(bookmark_cache)

    yield

    # Disable at session end (cleanup)
    disable_bookmark_caching()

def pytest_addoption(parser):
    """Adds the --run-slow command-line option to pytest."""
    parser.addoption(
        "--run-slow", action="store_true", default=False, help="run slow tests"
    )
    parser.addoption(
        "--run-integration", action="store_true", default=False,
        help="run integration tests"
    )
    parser.addoption(
        "--run-all", action="store_true", default=False,
        help="run all tests, including slow and integration tests"
    )

def pytest_configure(config):
    """Adds the 'slow' marker to the pytest configuration."""
    config.addinivalue_line("markers", "slow: mark test as slow to run")

def pytest_collection_modifyitems(config, items):
    """
    Skips tests marked as 'slow' if the --run-slow option is not given.
    """
    skip_slow = True
    skip_integration = True

    if config.getoption("--run-all"):
        # If --run-all is given, do not skip any tests
        skip_slow = False
        skip_integration = False
    elif config.getoption("--run-slow"):
        # If --run-slow is given, do not skip slow tests
        skip_slow = False
    elif config.getoption("--run-integration"):
        # If --run-integration is given, do not skip integration tests
        skip_integration = False



    if skip_slow:
        # If skip all tests marked as 'slow'
        skip_slow = pytest.mark.skip(
            reason="need --run-slow or --run-all option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)

    if skip_integration:
        # If --run-integration or --run-all is not given,
        # skip all tests marked as 'integration'
        skip_integration = pytest.mark.skip(
            reason="need --run-integration or --run-all option to run")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)