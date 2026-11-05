"""Fixtures for the pagerefs loader: a small CRF-enriched DDS, a CRF file and its pagerefs JSON.

No network and no rendering: the pagerefs JSON is written by hand in the crfpdf schema 2.1 shape.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[3]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

DSS = "https://library.cdisc.org/api/mdr/specializations/sdtm/datasetspecializations"
HEADER = {"OID": "MDV.T.Version1.Design1", "studyOID": "ODM.T.Version1.Design1",
          "fileOID": "ODM.DEFINE-JSON.T.Version1.Design1", "creationDateTime": "2026-10-24T10:00:00+00:00",
          "studyName": "T"}


def _cond(oid, item, comparator, values):
    return {"OID": oid, "rangeChecks": [{"item": item, "comparator": comparator, "checkValues": values,
                                         "softHard": "Soft"}]}


def _origin(type_, source):
    return [{"type": type_, "source": source}]


@pytest.fixture
def dds2() -> dict:
    """VS with a VSORRES value list whose where clauses carry IN ranges, LB with a Collected/Vendor
    value list, AE with placeholder and missing origins, and one CRF Form group to be ignored."""
    return {
        **HEADER,
        "annotatedCRFs": [{"leafID": "LF.acrf", "title": "Annotated CRF", "href": "acrf.pdf"}],
        "itemGroups": [
            {"OID": "IG.VS", "name": "VS", "domain": "VS", "items": [
                {"OID": "IT.VS.VSORRES", "name": "VSORRES"},
                {"OID": "IT.VS.VSTESTCD", "name": "VSTESTCD", "origin": _origin("Assigned", "Sponsor")},
                {"OID": "IT.VS.VSPOS", "name": "VSPOS", "origin": _origin("Collected", "Investigator")},
                {"OID": "IT.VS.VSDTC", "name": "VSDTC", "origin": _origin("__PLACEHOLDER__", "__PLACEHOLDER__")}],
             "slices": [{"OID": "VL.VS.VSORRES", "type": "ValueList", "wasDerivedFrom": "IT.VS.VSORRES", "items": [
                 {"OID": "IT.VS.VSORRES.SYSBP", "name": "VSORRES", "origin": _origin("Collected", "Investigator"),
                  "coding": [{"code": "SYSBP", "codeSystem": DSS}], "applicableWhen": ["WC.VS.1"]},
                 {"OID": "IT.VS.VSORRES.DIABP", "name": "VSORRES", "origin": _origin("Collected", "Investigator"),
                  "applicableWhen": ["WC.VS.2"]}]}]},
            {"OID": "IG.LB", "name": "LB", "domain": "LB", "items": [{"OID": "IT.LB.LBORRES", "name": "LBORRES"}],
             "slices": [{"OID": "VL.LB.LBORRES", "type": "ValueList", "wasDerivedFrom": "IT.LB.LBORRES", "items": [
                 {"OID": "IT.LB.LBORRES.ALT", "name": "LBORRES", "origin": _origin("Collected", "Vendor"),
                  "applicableWhen": ["WC.LB.1"]},
                 {"OID": "IT.LB.LBORRES.AST", "name": "LBORRES", "origin": _origin("Collected", "Vendor"),
                  "applicableWhen": ["WC.LB.2"]}]}]},
            {"OID": "IG.AE", "name": "AE", "domain": "AE", "items": [
                {"OID": "IT.AE.AETERM", "name": "AETERM"},
                {"OID": "IT.AE.AESER", "name": "AESER", "origin": _origin("Collected", "Investigator")},
                {"OID": "IT.AE.AEENRF", "name": "AEENRF", "origin": _origin("Assigned", "Sponsor")}]},
            {"OID": "IG.FORM.AE", "name": "AE", "type": "Form", "slices": []},
        ],
        "conditions": [_cond("C.1", "IT.VS.VSTESTCD", "EQ", ["SYSBP"]),
                       _cond("C.2", "IT.VS.VSPOS", "IN", ["PRONE", "SEMI-RECUMBENT", "SITTING"]),
                       _cond("C.3", "IT.VS.VSTESTCD", "EQ", ["DIABP"]),
                       _cond("C.4", "IT.LB.LBTESTCD", "EQ", ["ALT"]),
                       _cond("C.5", "IT.LB.LBTESTCD", "EQ", ["AST"])],
        "whereClauses": [{"OID": "WC.VS.1", "conditions": ["C.1", "C.2"]},
                         {"OID": "WC.VS.2", "conditions": ["C.3", "C.2"]},
                         {"OID": "WC.LB.1", "conditions": ["C.4"]}, {"OID": "WC.LB.2", "conditions": ["C.5"]}],
        "codeLists": [],
    }


def _entry(type_, source, pages, basis="ItemRef/Origin", values=(), items=(), mapping=()):
    return {"type": type_, "source": source, "description": "__PLACEHOLDER__" if type_ == "Derived" else None,
            "basis": [basis], "mapping": list(mapping), "values": list(values), "items": list(items),
            "pages": list(pages)}


def _target(dataset, variable, where=(), define_item_oid=None):
    from_where = [{"variable": v, "comparator": c, "values": list(vals), "source": s} for v, c, vals, s in where]
    key = f"{dataset}.{variable}" + (" where " + " and ".join(
        f"{v} = {vals[0]}" for v, c, vals, s in sorted(where)) if where else "")
    return {"dataset": dataset, "variable": variable, "where": from_where, "key": key,
            "define_item_oid": define_item_oid}


@pytest.fixture
def crf_file(tmp_path) -> Path:
    path = tmp_path / "crf-2.0.xml"
    path.write_text('<ODM FileOID="ODM.DEFINE-JSON.T.Version1.Design1"/>\n', encoding="utf-8")
    return path


@pytest.fixture
def pagerefs(crf_file) -> dict:
    """What crfpdf writes for the CRF: SYSBP, ALT, AETERM, AEENRF and VSTESTCD paired by OID; DIABP
    and VSPOS only by key; one OID the DDS does not have; one unpaired warning."""
    collected = _entry("Collected", "Investigator", [5])
    return {
        "schema_version": "2.1",
        "crf_sha256": hashlib.sha256(crf_file.read_bytes()).hexdigest(),
        "file_oid": HEADER["fileOID"], "creation_datetime": HEADER["creationDateTime"],
        "pdf_file": "/out/acrf.pdf",
        "study": {"oid": HEADER["studyOID"], "mdv_oid": HEADER["OID"]},
        "annotations": [
            {"targets": [_target("VS", "VSORRES", [("VSTESTCD", "EQ", ["DIABP"], "annotation"),
                                                   ("VSPOS", "EQ", ["SITTING"], "concept")])]},
            {"targets": [_target("VS", "VSPOS")]},
        ],
        "origins": {
            "VS.VSORRES where VSPOS = SITTING and VSTESTCD = DIABP": [_entry("Collected", "Investigator", [6])],
            "VS.VSPOS": [_entry("Collected", "Investigator", [5, 6])],
        },
        "define_items": {
            "IT.VS.VSORRES.SYSBP": [collected],
            "IT.LB.LBORRES.ALT": [_entry("Collected", "Investigator", [12, 13])],
            "IT.LB.LBORRES.AST": [_entry("Collected", "Investigator", [12, 13])],
            "IT.AE.AETERM": [_entry("Collected", "Investigator", [20])],
            "IT.AE.AEENRF": [_entry("Derived", "Sponsor", [20], basis="mappingInstructions",
                                    mapping=["relative_timing"])],
            "IT.VS.VSTESTCD": [_entry("Protocol", "Sponsor", [5], basis="concept", values=["SYSBP"])],
            "IT.VS.VSDTC": [_entry("Collected", "Investigator", [5, 6])],
            "IT.XX.UNKNOWN": [collected],
        },
        "warnings": [{"check": "define_oid_unpaired",
                      "text": "LBORRESU when LBTESTCD = ALT: target LB.LBORRESU where LBTESTCD = ALT has no "
                              "SDTMItemOIDs pair", "form_oid": "IG.FORM.LB", "item_oid": "IT.CRF.ALT_LBORRESU"}],
    }


@pytest.fixture
def files(tmp_path, dds2, pagerefs, crf_file):
    """Write the inputs; returns a function that writes (possibly edited) copies and the output path."""
    def write(dds=None, refs=None):
        dds_path, refs_path = tmp_path / "dds-crf.json", tmp_path / "acrf.pagerefs.json"
        dds_path.write_text(json.dumps(dds if dds is not None else dds2), encoding="utf-8")
        refs_path.write_text(json.dumps(refs if refs is not None else pagerefs), encoding="utf-8")
        return str(dds_path), str(refs_path), str(crf_file), str(tmp_path / "dds-origin.json")
    return write


@pytest.fixture
def edited():
    return copy.deepcopy
