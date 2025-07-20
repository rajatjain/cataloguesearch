import pytest

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