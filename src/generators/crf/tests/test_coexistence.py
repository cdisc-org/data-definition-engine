"""One combined DDS must drive both generators without either disturbing the other.

The Define generator runs in a subprocess because that package uses flat top-level
imports (``import items``) that only resolve with its own directory as the working
directory — importing it in-process would corrupt this package's import state.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[3]
DEFINE_DIR = SRC / "generators" / "define"
DEFINE_NS = {"odm": "http://www.cdisc.org/ns/odm/v1.3",
             "def": "http://www.cdisc.org/ns/def/v2.1"}

CRF_OID_PATTERN = re.compile(r"\b(IG\.FORM\.|IG\.SEC\.|IG\.CON\.|IT\.CRF\.|SE\.)")


def run_define_generator(dds_path: Path, out_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "define_generator.py", "-t", str(dds_path), "-d", str(out_path)],
        cwd=DEFINE_DIR, capture_output=True, text=True,
    )


@pytest.fixture
def define_only_dds(dds, tmp_path) -> Path:
    """The same DDS with every CRF-owned section removed."""
    stripped = json.loads(json.dumps(dds))
    stripped["itemGroups"] = [g for g in stripped["itemGroups"]
                              if g.get("type") not in ("Form", "Section", "Concept")]
    stripped["codeLists"] = [c for c in stripped["codeLists"]
                             if not str(c["OID"]).startswith(("CL.CDASH", "CL.CRF"))]
    stripped["standards"] = [s for s in stripped["standards"]
                             if s["OID"] not in ("STD.CDASHIG", "STD.CDASHCT")]
    stripped.pop("studyEvents", None)
    path = tmp_path / "define-only.json"
    path.write_text(json.dumps(stripped, indent=2), encoding="utf-8")
    return path


class TestDefineGeneratorOnCombinedDds:
    def test_it_succeeds(self, dds_file, tmp_path):
        out = tmp_path / "define.xml"
        result = run_define_generator(Path(dds_file), out)
        assert result.returncode == 0, result.stderr[-1500:]
        assert out.is_file()

    def test_no_crf_oids_leak_into_define_xml(self, dds_file, tmp_path):
        out = tmp_path / "define.xml"
        run_define_generator(Path(dds_file), out)
        text = out.read_text(encoding="utf-8")
        leaked = CRF_OID_PATTERN.findall(text)
        assert not leaked, f"CRF OIDs leaked into Define-XML: {set(leaked)}"

    def test_only_the_tabulation_dataset_is_emitted(self, dds_file, tmp_path):
        out = tmp_path / "define.xml"
        run_define_generator(Path(dds_file), out)
        groups = ET.parse(out).getroot().findall(".//odm:ItemGroupDef", DEFINE_NS)
        assert [g.get("OID") for g in groups] == ["IG.VS"]

    def test_dataset_content_matches_the_define_only_run(self, dds_file, define_only_dds,
                                                         tmp_path):
        """Adding CRF metadata must not change the tabulation content of the Define-XML.

        The two runs are not byte-identical: the combined DDS also carries the CRF
        codelists (``CL.CDASH.*``) and the CDASH standards, and the Define generator
        emits every codelist and standard it is given. Both are legal but unreferenced
        in Define-XML — see the ``--prune-unreferenced`` note in FIXES.md. What must
        match is everything that describes the datasets.
        """
        combined_out = tmp_path / "from-combined.xml"
        define_out = tmp_path / "from-define-only.xml"
        assert run_define_generator(Path(dds_file), combined_out).returncode == 0
        assert run_define_generator(define_only_dds, define_out).returncode == 0

        for tag in ("odm:ItemGroupDef", "odm:ItemDef", "odm:MethodDef"):
            assert _elements(combined_out, tag) == _elements(define_out, tag), tag

    def test_extra_content_is_confined_to_crf_codelists_and_standards(
            self, dds_file, define_only_dds, tmp_path):
        """Pin the known delta so anything new shows up as a failure."""
        combined_out = tmp_path / "from-combined.xml"
        define_out = tmp_path / "from-define-only.xml"
        run_define_generator(Path(dds_file), combined_out)
        run_define_generator(define_only_dds, define_out)

        extra_lists = _oids(combined_out, "odm:CodeList") - _oids(define_out, "odm:CodeList")
        assert all(oid.startswith(("CL.CDASH", "CL.CRF")) for oid in extra_lists)

        extra_standards = (_oids(combined_out, "def:Standards/def:Standard")
                           - _oids(define_out, "def:Standards/def:Standard"))
        assert extra_standards <= {"STD.CDASHIG", "STD.CDASHCT"}


class TestCrfGeneratorIgnoresDefineContent:
    def test_tabulation_datasets_are_not_emitted(self, odm20):
        _, _, xml = odm20
        ns = "{http://www.cdisc.org/ns/odm/v2.0}"
        oids = {g.get("OID") for g in ET.fromstring(xml).findall(f".//{ns}ItemGroupDef")}
        assert "IG.VS" not in oids

    def test_sdtm_items_are_referenced_but_not_defined(self, odm20):
        """crfSdtmTarget names IT.VS.* items; the CRF must not redefine them."""
        _, _, xml = odm20
        ns = "{http://www.cdisc.org/ns/odm/v2.0}"
        defined = {i.get("OID") for i in ET.fromstring(xml).findall(f".//{ns}ItemDef")}
        assert not any(oid.startswith("IT.VS.") for oid in defined)

    def test_both_versions_build_from_the_same_file(self, odm20, odm132):
        _, _, xml20 = odm20
        _, _, xml132 = odm132
        ns20 = "{http://www.cdisc.org/ns/odm/v2.0}"
        ns132 = "{http://www.cdisc.org/ns/odm/v1.3}"
        forms20 = {g.get("OID") for g in ET.fromstring(xml20).findall(f".//{ns20}ItemGroupDef")
                   if g.get("Type") == "Form"}
        forms132 = {f.get("OID") for f in ET.fromstring(xml132).findall(f".//{ns132}FormDef")}
        assert forms20 == forms132


class TestNamespaceIsolation:
    def test_building_both_versions_keeps_namespaces_correct(self, dds_file, tmp_path):
        """odmlib's namespace registry is global; the second build must not corrupt it."""
        from generators.crf.crf_generator import CrfGenerator

        xml_by_version = {}
        for version in ("2.0", "1.3.2", "2.0"):
            generator = CrfGenerator(dds_file, str(tmp_path / f"c-{version}.xml"),
                                     odm_version=version)
            xml_by_version[version] = generator.write(generator.create())

        assert ET.fromstring(xml_by_version["2.0"]).tag == \
            "{http://www.cdisc.org/ns/odm/v2.0}ODM"
        assert ET.fromstring(xml_by_version["1.3.2"]).tag == \
            "{http://www.cdisc.org/ns/odm/v1.3}ODM"


def _elements(path: Path, tag: str) -> list[str]:
    """Canonical serialization of every element matching a tag, in document order."""
    return [ET.canonicalize(ET.tostring(e, encoding="unicode"))
            for e in ET.parse(path).getroot().findall(f".//{tag}", DEFINE_NS)]


def _oids(path: Path, tag: str) -> set[str]:
    return {e.get("OID") for e in ET.parse(path).getroot().findall(f".//{tag}", DEFINE_NS)}
