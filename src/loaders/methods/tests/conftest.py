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


# -- a small DDS -------------------------------------------------------------------
def o(type_: str, source: str = "Sponsor") -> list[dict]:
    return [{"type": type_, "source": source}]


def it(dataset: str, name: str, origin: list[dict] | None, **extra) -> dict:
    item = {"OID": f"IT.{dataset}.{name}", "name": name, "dataType": "text", **extra}
    if origin is not None:
        item["origin"] = origin
    return item


def check(oid: str, variable_oid: str, comparator: str, *values: str) -> dict:
    return {"OID": oid, "rangeChecks": [{"comparator": comparator, "checkValues": list(values),
                                         "item": variable_oid, "softHard": "Soft"}]}


CUSTOM = method("MT.LB.CUSTOM", name="Sponsor LBSTRESC", basis=None)
del CUSTOM["basis"]


@pytest.fixture
def dds() -> dict:
    """Derived items for most seed assignments, plus every case the loader treats specially:
    a study-specific item (placeholder), an item that already names a method (kept), value-level
    BMI, a variable Derived at both levels, a Protocol --DY, and a CRF Form (never a Define item)."""
    return {
        "OID": "MDV.T", "studyOID": "ODM.T", "studyName": "STUDY01",
        "itemGroups": [
            {"OID": "IG.AE", "name": "AE", "domain": "AE", "items": [
                it("AE", "STUDYID", o("Assigned")),
                it("AE", "USUBJID", o("Derived")),
                it("AE", "AESEQ", o("Derived")),
                it("AE", "AESTDTC", o("Collected", "Investigator")),
                it("AE", "AESTDY", o("Derived")),
                it("AE", "AEDTC", [{"type": "Derived", "source": "Sponsor",
                                    "documents": [{"leafID": "LF.acrf", "pages": [3]}]}]),
                it("AE", "AEENRF", o("Derived")),
                it("AE", "AETERM", o("Collected", "Investigator"))]},
            {"OID": "IG.TS", "name": "TS", "domain": "TS", "items": [it("TS", "TSSEQ", o("Derived"))]},
            {"OID": "IG.SV", "name": "SV", "domain": "SV", "items": [
                it("SV", "VISITDY", o("Protocol")), it("SV", "SVSTDTC", o("Derived"))]},
            {"OID": "IG.SE", "name": "SE", "domain": "SE", "items": [it("SE", "EPOCH", o("Derived"))]},
            {"OID": "IG.LB", "name": "LB", "domain": "LB", "items": [
                it("LB", "LBSTRESC", o("Derived"), method="MT.LB.CUSTOM")]},
            {"OID": "IG.VS", "name": "VS", "domain": "VS", "items": [
                it("VS", "VSTESTCD", o("Protocol")), it("VS", "VSORRES", None)],
             "slices": [{"OID": "VL.VS.VSORRES", "type": "ValueList", "items": [
                 {**it("VS", "VSORRES", o("Derived"), applicableWhen=["WC.VS.BMI"]), "OID": "IT.VS.VSORRES.BMI"},
                 {**it("VS", "VSORRES", o("Collected", "Investigator"), applicableWhen=["WC.VS.WEIGHT"]),
                  "OID": "IT.VS.VSORRES.WEIGHT"}]}]},
            {"OID": "IG.QS", "name": "QS", "domain": "QS", "items": [
                it("QS", "QSTESTCD", o("Protocol")), it("QS", "QSSTRESN", o("Derived"))],
             "slices": [{"OID": "VL.QS.QSSTRESN", "type": "ValueList", "items": [
                 {**it("QS", "QSSTRESN", o("Derived"), applicableWhen=["WC.QS.TOTAL"]),
                  "OID": "IT.QS.QSSTRESN.TOTAL"}]}]},
            {"OID": "IG.FORM.AE", "name": "Adverse Events", "type": "Form", "slices": [], "items": [
                {"OID": "IT.CRF.AEDY", "name": "AEDY", "dataType": "integer", "origin": o("Derived")}]},
        ],
        "conditions": [
            check("COND.VS.BMI", "IT.VS.VSTESTCD", "EQ", "BMI"),
            check("COND.VS.WEIGHT", "IT.VS.VSTESTCD", "EQ", "WEIGHT"),
            check("COND.QS.TOTAL", "IT.QS.QSTESTCD", "IN", "TOTAL", "SUBTOTAL"),
        ],
        "whereClauses": [
            {"OID": "WC.VS.BMI", "conditions": ["COND.VS.BMI"]},
            {"OID": "WC.VS.WEIGHT", "conditions": ["COND.VS.WEIGHT"]},
            {"OID": "WC.QS.TOTAL", "conditions": ["COND.QS.TOTAL"]},
        ],
        "methods": [copy.deepcopy(CUSTOM)],
    }


@pytest.fixture
def run(tmp_path):
    """Write a DDS, run the loader over it (seed library unless given) and return the loader."""
    from loaders.methods.methods_loader import MethodsLoader

    def _run(content: dict, libraries: list[str] | None = None, name: str = "dds-in.json"):
        dds_in = tmp_path / name
        dds_in.write_text(json.dumps(content), encoding="utf-8")
        loader = MethodsLoader(str(dds_in), str(tmp_path / "dds-out.json"), libraries)
        loader.process()
        return loader
    return _run
