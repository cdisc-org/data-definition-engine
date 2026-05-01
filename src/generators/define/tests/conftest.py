"""
Pytest configuration and fixtures for template2define tests.
"""
import os
import sys
from pathlib import Path
import pytest
import tempfile
import shutil

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _chdir_project_root():
    """
    The generator package uses flat top-level imports (``import items``, etc.),
    which only resolve when the working directory is the package root. Rather
    than requiring every test to call ``os.chdir(project_root)``, this autouse
    fixture enters the directory for each test and restores it afterward.
    """
    original = os.getcwd()
    os.chdir(PROJECT_ROOT)
    try:
        yield
    finally:
        os.chdir(original)


@pytest.fixture
def project_root():
    """Return the project root directory."""
    return PROJECT_ROOT


@pytest.fixture
def data_dir(project_root):
    """Return the fixtures directory containing sample JSON files."""
    return project_root / "tests" / "fixtures"


@pytest.fixture
def sample_dds_file(data_dir):
    """Return the path to the main sample DDS JSON file."""
    return data_dir / "define-360i.json"


@pytest.fixture
def temp_output_dir():
    """Create a temporary directory for test output files."""
    temp_dir = tempfile.mkdtemp(prefix="template2define_test_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_output_xml(temp_output_dir):
    """Return a path for a temporary output XML file."""
    return temp_output_dir / "test_output.xml"
