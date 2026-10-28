"""Fixtures for the defaults loader: a small DDS with placeholders of every kind, and a dictionary.

No network. The DDS mixes tabulation datasets (LB with a value list, SE, TA, TV, AE), a CRF Form
whose one CRF item is shared by two Concepts (as the CRF loader shares items by identity), and a
codelist with a placeholder term.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[3]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

P = "__PLACEHOLDER__"
PAGES = [{"leafID": "LF.acrf", "pages": [4]}]


def ph():
    return [{"type": P, "source": P}]


def o(type_, source):
    return [{"type": type_, "source": source}]


@pytest.fixture
def dds() -> dict:
    crf_aeterm = {"OID": "IT.CRF.AETERM", "name": "AETERM", "dataType": "text", "question": None,
                  "prompt": "Term", "origin": o("Collected", "Investigator")}
    content = {
        "OID": "MDV.T", "studyOID": "ODM.T", "studyName": "STUDY01", "protocolName": "STUDY01",
        "itemGroups": [
            {"OID": "IG.LB", "name": "LB", "domain": "LB", "description": "Laboratory Test Results",
             "keySequence": [P], "standardOID": "STD.SDTMIG", "items": [
                 {"OID": "IT.LB.STUDYID", "name": "STUDYID", "dataType": "text", "origin": ph()},
                 {"OID": "IT.LB.LBSEQ", "name": "LBSEQ", "dataType": "integer", "origin": ph()},
                 {"OID": "IT.LB.LBSCAT", "name": "LBSCAT", "dataType": "text", "origin": ph()},
                 {"OID": "IT.LB.LBTESTCD", "name": "LBTESTCD", "dataType": "text", "length": 8,
                  "origin": [{"type": "Protocol", "source": "Sponsor", "documents": copy.deepcopy(PAGES)}]},
                 {"OID": "IT.LB.LBORNRLO", "name": "LBORNRLO", "dataType": "text",
                  "origin": [{"type": "Collected", "source": P, "documents": copy.deepcopy(PAGES)}]},
                 {"OID": "IT.LB.LBSTRESN", "name": "LBSTRESN", "dataType": "float", "origin": ph()},
                 {"OID": "IT.LB.LBDTC", "name": "LBDTC", "dataType": "datetime", "origin": ph()},
                 {"OID": "IT.LB.LBORRES", "name": "LBORRES", "dataType": "text"},
                 {"OID": "IT.LB.VISITNUM", "name": "VISITNUM", "dataType": "integer", "origin": ph()}],
             "slices": [{"OID": "VL.LB.LBORRES", "type": "ValueList", "wasDerivedFrom": "IT.LB.LBORRES",
                         "items": [{"OID": "IT.LB.LBORRES.ALT", "name": "LBORRES", "dataType": "float",
                                    "length": 12, "origin": [{"type": "Collected", "source": "Investigator",
                                                              "documents": copy.deepcopy(PAGES)}]}]}]},
            {"OID": "IG.SE", "name": "SE", "domain": "SE", "keySequence": ["STUDYID", "USUBJID", "SESTDTC"],
             "standardOID": "STD.SDTMIG", "items": [
                 {"OID": "IT.SE.SESTDTC", "name": "SESTDTC", "dataType": "datetime", "origin": ph()},
                 {"OID": "IT.SE.ETCD", "name": "ETCD", "dataType": "text", "origin": ph()},
                 {"OID": "IT.SE.SESTDY", "name": "SESTDY", "dataType": "integer", "origin": ph()}]},
            {"OID": "IG.TA", "name": "TA", "domain": "TA", "keySequence": [P], "standardOID": "STD.SDTMIG",
             "items": [
                 {"OID": "IT.TA.STUDYID", "name": "STUDYID", "dataType": "text", "origin": ph()},
                 {"OID": "IT.TA.ARM", "name": "ARM", "dataType": "text", "origin": ph()},
                 {"OID": "IT.TA.EPOCH", "name": "EPOCH", "dataType": "text", "origin": ph()}]},
            {"OID": "IG.TV", "name": "TV", "domain": "TV", "keySequence": ["STUDYID", "VISITNUM"],
             "standardOID": "STD.SDTMIG", "items": [
                 {"OID": "IT.TV.VISITDY", "name": "VISITDY", "dataType": "integer", "origin": ph()}]},
            {"OID": "IG.AE", "name": "AE", "domain": "AE", "keySequence": ["STUDYID", "USUBJID", "AESEQ"],
             "standardOID": "STD.SDTMIG", "items": [
                 {"OID": "IT.AE.AETERM", "name": "AETERM", "dataType": "text", "length": 200,
                  "origin": [{"type": "Collected", "source": "Investigator", "documents": copy.deepcopy(PAGES)}]},
                 {"OID": "IT.AE.AESOCCD", "name": "AESOCCD", "dataType": "integer", "origin": ph()}]},
            {"OID": "IG.FORM.AE", "name": "AE", "type": "Form", "domain": "AE", "slices": [
                {"OID": "IG.SEC.AE.1", "name": "Adverse Events", "type": "Section",
                 "crfSectionInstructions": P, "slices": [
                     {"OID": "IG.CON.AE1", "name": "AE1", "type": "Concept", "items": [crf_aeterm]},
                     {"OID": "IG.CON.AE2", "name": "AE2", "type": "Concept", "items": [crf_aeterm]}]}]},
        ],
        "codeLists": [{"OID": "CL.X", "name": "X", "codeListItems": [{"codedValue": P, "decode": P}]}],
    }
    for group in content["itemGroups"]:
        if group.get("type") != "Form":
            group.setdefault("description", f"{group['name']} dataset")
            group.update(purpose="Tabulation", structure="One record per subject")
    return content


PS, AS, DS = o("Protocol", "Sponsor"), o("Assigned", "Sponsor"), o("Derived", "Sponsor")
CI, CV = o("Collected", "Investigator"), o("Collected", "Vendor")


@pytest.fixture
def dictionary() -> dict:
    return {
        "schemaVersion": "1.0",
        "items": [
            {"name": "STUDYID", "values": {"length": {"lengthOf": "studyName"}, "origin": PS}},
            {"name": "--SEQ", "values": {"length": 3, "origin": DS}},
            {"name": "--CAT", "values": {"length": 40, "origin": AS}},
            {"name": "--SCAT", "values": {"length": 30}},
            {"name": "--TESTCD", "values": {"length": 20, "origin": AS}},
            {"name": "LBORNRLO", "values": {"dataType": "float", "length": 6, "significantDigits": 2,
                                            "origin": CV}},
            {"name": "--STRESN", "values": {"length": 8, "significantDigits": 3, "origin": DS}},
            {"name": "--DTC", "values": {"length": 20, "origin": CI}},
            {"name": "--DTC", "domains": ["SE", "SV"], "values": {"origin": DS}},
            {"name": "LBORRES", "values": {"origin": CV}},
            {"name": "VISITNUM", "values": {"dataType": "integer", "length": 2, "displayFormat": "Z2.",
                                            "origin": AS}},
            {"name": "VISITDY", "values": {"dataType": "integer", "length": 4, "origin": PS}},
            {"name": "--DY", "values": {"dataType": "integer", "length": 3, "origin": DS}},
            {"name": "EPOCH", "excludeDomains": ["TA"], "values": {"length": 40, "origin": DS}},
            {"name": "*", "domains": ["TA", "TV"], "values": {"origin": PS}},
            {"name": "*", "domains": ["SE"], "values": {"origin": DS}},
            {"name": "--SOCCD", "domains": ["AE"], "values": {"dataType": "integer", "length": 8, "origin": AS}},
            {"name": "AETERM", "values": {"length": 100}},
            {"name": "NOSUCH", "values": {"length": 1}},
        ],
        "itemGroups": [{"name": "LB", "values": {"keySequence": ["STUDYID", "USUBJID", "LBTESTCD"]}},
                       {"name": "SE", "values": {"keySequence": ["STUDYID", "SESTDTC"]}}],
        "crfItems": [{"name": "AETERM", "values": {"length": 50, "question": "What is the adverse event term?"}}],
        "crfSections": [{"name": "*", "domains": ["AE"],
                         "values": {"crfSectionInstructions": "Record each adverse event."}}],
    }


@pytest.fixture
def files(tmp_path, dds, dictionary):
    """Write the inputs; returns a function that writes (possibly edited) copies and the paths."""
    def write(dds_=None, dictionaries=None):
        dds_path = tmp_path / "dds-origin.json"
        dds_path.write_text(json.dumps(dds if dds_ is None else dds_), encoding="utf-8")
        paths = []
        for n, content in enumerate(dictionaries if dictionaries is not None else [dictionary]):
            path = tmp_path / f"defaults-{n}.json"
            path.write_text(json.dumps(content), encoding="utf-8")
            paths.append(str(path))
        return str(dds_path), str(tmp_path / "dds-defaults.json"), paths
    return write
