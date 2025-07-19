import pytest

def pytest_addoption(parser):
    """Adds the --run-slow command-line option to pytest."""
    parser.addoption(
        "--run-slow", action="store_true", default=False, help="run slow tests"
    )

def pytest_configure(config):
    """Adds the 'slow' marker to the pytest configuration."""
    config.addinivalue_line("markers", "slow: mark test as slow to run")

def pytest_collection_modifyitems(config, items):
    """
    Skips tests marked as 'slow' if the --run-slow option is not given.
    """
    if not config.getoption("--run-slow"):
        # If --run-slow is not given, skip all tests marked as 'slow'
        skip_slow = pytest.mark.skip(reason="need --run-slow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
