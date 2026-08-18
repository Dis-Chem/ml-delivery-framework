# tests/conftest.py
import pytest
from utils import generated_project_dir, databricks_cli

# Re-export fixtures cleanly for the test suite
__all__ = ["generated_project_dir", "databricks_cli"]


def pytest_addoption(parser):
    # 1. Retain the MLflow markers
    parser.addoption(
        "--large-only",
        action="store_true",
        dest="large_only",
        default=False,
        help="Run only tests decorated with 'large' annotation",
    )
    parser.addoption(
        "--large",
        action="store_true",
        dest="large",
        default=False,
        help="Run tests decorated with 'large' annotation",
    )
    # 2. Add the matrix controlling path argument
    parser.addoption(
        "--template-path",
        action="store",
        default="all",
        help="Specific template folder to test, or 'all' to run across the matrix loop.",
    )


def pytest_configure(config):
    # Register markers to suppress `PytestUnknownMarkWarning`
    config.addinivalue_line("markers", "large")


def pytest_runtest_setup(item):
    # Enforce MLflow large execution routing rules
    markers = [mark.name for mark in item.iter_markers()]
    marked_as_large = "large" in markers
    large_option = item.config.getoption("--large")
    large_only_option = item.config.getoption("--large-only")
    if marked_as_large and not (large_option or large_only_option):
        pytest.skip("use `--large` or `--large-only` to run this test")
    if not marked_as_large and large_only_option:
        pytest.skip("remove `--large-only` to run this test")


def pytest_generate_tests(metafunc):
    """
    Dynamically generates separate matrix test cases for any fixture or test
    function requiring the 'template_path' argument.
    """
    if "template_path" in metafunc.fixturenames:
        specified_path = metafunc.config.getoption("--template-path")

        if specified_path == "all":
            # Matrix Mode: Run the test against EVERY template variant sequentially
            metafunc.parametrize("template_path", ".", scope="function")
        else:
            # Isolated Mode: Run only against the user-specified subfolder
            metafunc.parametrize("template_path", [specified_path], scope="function")


@pytest.fixture
def template_path(request):
    """Fixture that surfaces the currently executing matrix path variable."""
    return request.param
