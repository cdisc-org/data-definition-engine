"""
Pytest configuration and fixtures for template2define tests.
"""
import os
import sys
from pathlib import Path
import pytest
import tempfile
import shutil

# Add the project root to the Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


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
def sample_sdtm_file(data_dir):
    """Return the path to the SDTM sample DDS JSON file."""
    return data_dir / "define_LZZT_SDTM.json"


@pytest.fixture
def sample_adam_file(data_dir):
    """Return the path to the ADaM sample DDS JSON file."""
    return data_dir / "define_LZZT_ADaM.json"


@pytest.fixture
def temp_output_dir():
    """Create a temporary directory for test output files."""
    temp_dir = tempfile.mkdtemp(prefix="template2define_test_")
    yield Path(temp_dir)
    # Cleanup after test
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_output_xml(temp_output_dir):
    """Return a path for a temporary output XML file."""
    return temp_output_dir / "test_output.xml"


@pytest.fixture
def original_working_dir():
    """Save and restore the original working directory."""
    original_dir = os.getcwd()
    yield original_dir
    os.chdir(original_dir)
