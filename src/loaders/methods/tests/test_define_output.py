"""The methods loader's output through the Define generator, the Define-XML 2.1 XSD and the defineutils
conformance rules (methods plan M5).

Both programs run as the pipeline runs them (stages G and H), as subprocesses: the Define generator
uses flat imports and only runs from its own folder. The hand-built fixture must pass every rule
defineutils evaluates; the MSG v2 oracle leaves out the value lists that hold no Derived item, so
only the rules about methods and their leaves are held to it.
"""
from __future__ import annotations

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from loaders.methods.library import SEED_FILE

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PLACEHOLDER = "__PLACEHOLDER__"
SRC_DIR = Path(__file__).resolve().parents[3]
GENERATOR_DIR = SRC_DIR / "generators" / "define"
NS = {"odm": "http://www.cdisc.org/ns/odm/v1.3", "def": "http://www.cdisc.org/ns/def/v2.1"}
#: the Define-XML 2.1 conformance rules about MethodDefs, MethodOIDs and the leaves a method names
METHOD_RULES = {"42", "43", "56", "73", "74", "205", "206", "207", "208", "209", "210", "216", "218", "219",
                "221", "248", "259"}


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return completed


def stages_g_and_h(dds: Path, tmp: Path, libraries: list[Path]) -> tuple[Path, set[str]]:
    """The methods loader, then the Define generator with schema validation (a failure exits 1);
    returns the define.xml and the OIDs of the methods in the loader's DDS."""
    with_methods, define = tmp / "dds-methods.json", tmp / "define.xml"
    run([sys.executable, "-m", "loaders.methods", "--dds_in", str(dds), "--dds_out", str(with_methods),
         "--methods", *[str(p) for p in libraries], "--report", str(tmp / "methods-report.yaml")], SRC_DIR)
    run([sys.executable, "define_generator.py", "-t", str(with_methods), "-d", str(define), "--validate"],
        GENERATOR_DIR)
    return define, {m["OID"] for m in json.loads(with_methods.read_text(encoding="utf-8"))["methods"]}


def derived_refs(define: Path) -> dict[str, str | None]:
    """ItemOID -> MethodOID for every ItemRef whose ItemDef is Derived."""
    mdv = ET.parse(define).getroot().find(".//odm:MetaDataVersion", NS)
    derived = {i.get("OID") for i in mdv.findall("odm:ItemDef", NS)
               if any(o.get("Type") == "Derived" for o in i.findall("def:Origin", NS))}
    return {r.get("ItemOID"): r.get("MethodOID") for r in mdv.iter(f"{{{NS['odm']}}}ItemRef")
            if r.get("ItemOID") in derived}


def method_defs(define: Path) -> dict[str, str]:
    mdv = ET.parse(define).getroot().find(".//odm:MetaDataVersion", NS)
    return {m.get("OID"): m.findtext("odm:Description/odm:TranslatedText", namespaces=NS)
            for m in mdv.findall("odm:MethodDef", NS)}


def conformance(define: Path):
    checker = pytest.importorskip("defineutils.conformance", reason="defineutils >= 0.4.0 checks conformance")
    return checker.DefineConformanceChecker(define).check()


class TestDmBmiDates:
    @pytest.fixture(scope="class")
    def output(self, tmp_path_factory):
        return stages_g_and_h(FIXTURES / "dm_bmi_dates_dds.json", tmp_path_factory.mktemp("dm"), [SEED_FILE])

    def test_every_derived_item_names_a_seed_method_and_the_generator_makes_none(self, output):
        define, loader_methods = output
        refs = derived_refs(define)
        assert len(refs) == 18 and all(refs.values())
        assert refs["IT.VS.VSORRES.BMI"] == "MT.BMI" and refs["IT.VS.VSDTC"] == "MT.ISO8601"
        written = method_defs(define)
        assert set(written) == loader_methods and len(written) == 17      # none made by post-processing
        assert PLACEHOLDER not in written.values()

    def test_the_define_xml_passes_every_conformance_rule_defineutils_evaluates(self, output):
        result = conformance(output[0])
        assert [(f.rule, f.locations[0].detail) for f in result.errors] == []
        assert set(METHOD_RULES) <= set(result.passed)


class TestMsgV2:
    @pytest.fixture(scope="class")
    def output(self, tmp_path_factory):
        return stages_g_and_h(FIXTURES / "msg_v2_dds.json", tmp_path_factory.mktemp("msg"),
                              [SEED_FILE, FIXTURES / "msg_v2_methods.json"])

    def test_the_define_xml_has_msg_s_29_methods_on_msg_s_91_items(self, output):
        define, loader_methods = output
        refs = derived_refs(define)
        assert len(refs) == 91 and all(refs.values())
        written = method_defs(define)
        assert set(written) == loader_methods and len(written) == 29
        assert PLACEHOLDER not in written.values()

    def test_no_method_rule_fails(self, output):
        result = conformance(output[0])
        assert {f.rule for f in result.findings} & METHOD_RULES == set()
        assert METHOD_RULES <= set(result.passed)
