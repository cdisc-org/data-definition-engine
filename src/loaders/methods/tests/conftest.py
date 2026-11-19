"""Fixtures for the methods loader: a small valid library and a writer for library files. No network."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[3]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def method(oid: str, **overrides) -> dict:
    entry = {
        "OID": oid, "name": f"Algorithm for {oid}", "type": "Computation",
        "description": f"Description of {oid}.",
        "signature": {
            "parameters": [{"name": "IN", "dataType": "text", "description": "input", "orderNumber": 1}],
            "returnValues": [{"name": "OUT", "dataType": "integer", "description": "output", "orderNumber": 1}],
        },
        "basis": "test",
    }
    entry.update(overrides)
    return entry


@pytest.fixture
def library() -> dict:
    return {
        "schemaVersion": "1.0",
        "methods": [method("MT.SEQ"), method("MT.TSSEQ"), method("MT.BMI")],
        "assignments": [
            {"name": "--SEQ", "method": "MT.SEQ"},
            {"name": "TSSEQ", "method": "MT.TSSEQ"},
            {"name": "VSORRES", "domains": ["VS"], "where": {"VSTESTCD": "BMI"}, "method": "MT.BMI"},
        ],
    }


@pytest.fixture
def write(tmp_path):
    """Write library contents to files in order; returns their paths."""
    def _write(*contents: dict) -> list[str]:
        paths = []
        for n, content in enumerate(contents):
            path = tmp_path / f"methods-{n}.json"
            path.write_text(json.dumps(copy.deepcopy(content)), encoding="utf-8")
            paths.append(str(path))
        return paths
    return _write
