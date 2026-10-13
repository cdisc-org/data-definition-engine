"""
Shared fixtures for create_define_json tests.

The core challenge is that USDMDefineJSONProcessor.__init__ opens a USDM file
from disk and instantiates CDISCLibraryClient (which requires a real API key).
We handle this by:
  1. Providing a minimal but structurally complete USDM fixture file.
  2. Patching CDISCLibraryClient during __init__ so proc.client IS mock_client.

Tests that call API-dependent methods configure mock_client.<method>.return_value
before exercising the method under test.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make create_define_json importable (src/define-xml has a hyphen, so not a package)
DEFINE_XML_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(DEFINE_XML_DIR))

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def minimal_usdm_file():
    """Path to the minimal USDM JSON fixture file."""
    return FIXTURES_DIR / "minimal_usdm.json"


@pytest.fixture
def two_bc_usdm_file():
    """
    Path to a USDM fixture carrying one biomedical concept of each producer layout.

    BiomedicalConcept_1 uses the SoA Workbench layout (concept reference plus an
    sdtm specialization extension attribute); BiomedicalConcept_2 uses the CDISC
    USDM E2J layout (a package-dated specialization reference).
    """
    return FIXTURES_DIR / "two_bc_usdm.json"


@pytest.fixture
def mock_client():
    """A fresh MagicMock standing in for CDISCLibraryClient."""
    return MagicMock()


@pytest.fixture
def processor(minimal_usdm_file, mock_client, tmp_path):
    """
    A USDMDefineJSONProcessor instance with a mocked CDISC client.

    CDISCLibraryClient is patched during __init__ so that proc.client IS
    mock_client.  Tests configure mock_client.<method>.return_value as needed
    before calling the method under test.
    """
    return _build_processor(minimal_usdm_file, mock_client, tmp_path)


@pytest.fixture
def two_bc_processor(two_bc_usdm_file, mock_client, tmp_path):
    """A processor loaded from the two-layout USDM fixture, with a mocked client."""
    return _build_processor(two_bc_usdm_file, mock_client, tmp_path)


def _build_processor(usdm_file, mock_client, tmp_path):
    from create_define_json import USDMDefineJSONProcessor

    output_path = tmp_path / "output.json"
    with patch("create_define_json.CDISCLibraryClient", return_value=mock_client):
        proc = USDMDefineJSONProcessor(
            usdm_file=str(usdm_file),
            output_template=str(output_path),
            sdtmig="3.4",
            sdtmct="2025-03-28",
            studyversion=0,
            studydesign=0,
            docversion=0,
            cdisc_api_key="fake-key",
            cosmosversion="v2",
            debug=False,
        )
    return proc
