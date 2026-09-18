"""Fixtures for the crf_loader tests.

The CDISC Library client is replaced with a ``MagicMock`` throughout, as in
``src/define-xml/tests/conftest.py`` — no test in this suite reaches the network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# src/ on the path so ``loaders.crf...`` imports resolve however pytest is invoked.
SRC_DIR = Path(__file__).resolve().parents[3]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def crf_spec_csv() -> Path:
    return FIXTURES / "crf_specs_vs_extract.csv"


@pytest.fixture
def usdm_soa() -> dict:
    with open(FIXTURES / "usdm_soa_minimal.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def dds_define_minimal() -> dict:
    with open(FIXTURES / "dds_define_minimal.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def cdashig_fields() -> dict:
    with open(FIXTURES / "cdashig_vs_fields.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def cdash_codelist() -> dict:
    with open(FIXTURES / "cdashct_C66770.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def mock_client(cdashig_fields, cdash_codelist) -> MagicMock:
    """A Library client that answers the CDASHIG and CDASH CT calls from fixtures."""
    client = MagicMock()

    def get_api_json(path: str, *args, **kwargs):
        if "/cdashig/" in path and "/domains/VS" in path:
            return cdashig_fields
        if "/codelists/C66770" in path:
            return cdash_codelist
        if "/codelists/" in path:
            return {}
        return {}

    client.get_api_json.side_effect = get_api_json
    return client


@pytest.fixture
def spec_source(crf_spec_csv):
    from loaders.crf.sources.crf_specializations import CsvCrfSpecializationSource
    return CsvCrfSpecializationSource(crf_spec_csv)
