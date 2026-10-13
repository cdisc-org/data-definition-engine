"""Fixtures for the crf_generator tests.

Unlike the Define generator, this package is a real Python package with absolute imports,
so no working-directory juggling is needed — only ``src/`` on the path.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[3]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def dds_file() -> str:
    return str(FIXTURES / "dds-360i-crf.json")


@pytest.fixture
def dds(dds_file) -> dict:
    with open(dds_file, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def generated(request, dds_file, tmp_path):
    """Build a document for the ODM version named by the test's ``odm_version`` param."""
    from generators.crf.crf_generator import CrfGenerator

    version = getattr(request, "param", "2.0")
    out = tmp_path / f"crf-{version}.xml"
    generator = CrfGenerator(dds_file=dds_file, odm_file=str(out), odm_version=version)
    odm = generator.create()
    xml = generator.write(odm)
    return generator, odm, xml


@pytest.fixture
def odm20(dds_file, tmp_path):
    from generators.crf.crf_generator import CrfGenerator

    generator = CrfGenerator(dds_file=dds_file,
                             odm_file=str(tmp_path / "crf-2.0.xml"), odm_version="2.0")
    odm = generator.create()
    return generator, odm, generator.write(odm)


@pytest.fixture
def odm132(dds_file, tmp_path):
    from generators.crf.crf_generator import CrfGenerator

    generator = CrfGenerator(dds_file=dds_file,
                             odm_file=str(tmp_path / "crf-1.3.2.xml"), odm_version="1.3.2")
    odm = generator.create()
    return generator, odm, generator.write(odm)
