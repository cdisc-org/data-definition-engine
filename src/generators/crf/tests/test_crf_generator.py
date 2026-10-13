"""CrfGenerator pipeline: CLI surface, filters, dedup, and post-processing."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET

import pytest

from generators.crf.crf_generator import CrfGenerator, _index_items
from generators.crf.post_processing import peek
from generators.crf.targets import get_target


class TestConstruction:
    def test_rejects_an_unknown_odm_version(self, dds_file, tmp_path):
        with pytest.raises(ValueError, match="odm_version"):
            CrfGenerator(dds_file, str(tmp_path / "o.xml"), odm_version="3.0")

    def test_rejects_a_missing_dds_file(self, tmp_path):
        with pytest.raises(ValueError, match="cannot be found"):
            CrfGenerator(str(tmp_path / "nope.json"), str(tmp_path / "o.xml"))

    def test_invalid_json_exits_non_zero(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        generator = CrfGenerator(str(bad), str(tmp_path / "o.xml"), odm_version="2.0")
        with pytest.raises(SystemExit) as exc:
            generator.create()
        assert exc.value.code == 1

    def test_get_target_rejects_an_unknown_version(self):
        with pytest.raises(ValueError, match="unsupported ODM version"):
            get_target("9.9")

    def test_wrapped_dds_is_accepted(self, dds, tmp_path):
        wrapped = tmp_path / "wrapped.json"
        wrapped.write_text(json.dumps({"metaDataVersion": dds}), encoding="utf-8")
        generator = CrfGenerator(str(wrapped), str(tmp_path / "o.xml"), odm_version="2.0")
        odm = generator.create()
        assert odm.Study[0].StudyName == dds["studyName"]


class TestItemHandling:
    def test_shared_item_defs_are_emitted_once(self, odm20):
        """VSDAT is inlined in several concepts but must define one ItemDef."""
        generator, _, xml = odm20
        oids = [i.get("OID") for i in
                ET.fromstring(xml).findall(
                    ".//{http://www.cdisc.org/ns/odm/v2.0}ItemDef")]
        assert len(oids) == len(set(oids))

    def test_every_item_ref_resolves_to_an_item_def(self, odm20):
        _, _, xml = odm20
        ns = "{http://www.cdisc.org/ns/odm/v2.0}"
        root = ET.fromstring(xml)
        defined = {i.get("OID") for i in root.findall(f".//{ns}ItemDef")}
        referenced = {r.get("ItemOID") for r in root.findall(f".//{ns}ItemRef")}
        assert referenced <= defined

    def test_index_items_walks_slices(self, dds):
        index = _index_items(dds)
        assert "IT.CRF.SYSBP_VSORRES" in index
        assert "IT.VS.VSORRES" in index, "Define-side items are indexed too"

    def test_hidden_items_are_skipped_by_default(self, dds, tmp_path):
        concept = _first_concept(dds)
        concept["items"][0]["crfDisplayHidden"] = True
        hidden_oid = concept["items"][0]["OID"]
        path = tmp_path / "hidden.json"
        path.write_text(json.dumps(dds), encoding="utf-8")

        generator = CrfGenerator(str(path), str(tmp_path / "o.xml"), odm_version="2.0")
        xml = generator.write(generator.create())
        group = _group(xml, concept["OID"])
        assert hidden_oid not in {r.get("ItemOID") for r in
                                  group.findall("{http://www.cdisc.org/ns/odm/v2.0}ItemRef")}

    def test_include_hidden_emits_them(self, dds, tmp_path):
        concept = _first_concept(dds)
        concept["items"][0]["crfDisplayHidden"] = True
        hidden_oid = concept["items"][0]["OID"]
        path = tmp_path / "hidden.json"
        path.write_text(json.dumps(dds), encoding="utf-8")

        generator = CrfGenerator(str(path), str(tmp_path / "o.xml"), odm_version="2.0",
                                 include_hidden=True)
        xml = generator.write(generator.create())
        group = _group(xml, concept["OID"])
        assert hidden_oid in {r.get("ItemOID") for r in
                              group.findall("{http://www.cdisc.org/ns/odm/v2.0}ItemRef")}


class TestFormFilter:
    def test_forms_flag_limits_output(self, dds_file, tmp_path):
        generator = CrfGenerator(dds_file, str(tmp_path / "o.xml"), odm_version="2.0",
                                 forms=["IG.FORM.VITAL-SIGNS"])
        xml = generator.write(generator.create())
        forms = [g.get("OID") for g in
                 ET.fromstring(xml).findall(".//{http://www.cdisc.org/ns/odm/v2.0}ItemGroupDef")
                 if g.get("Type") == "Form"]
        assert forms == ["IG.FORM.VITAL-SIGNS"]

    def test_unknown_form_oid_is_rejected(self, dds_file, tmp_path):
        """The check needs the loaded DDS, so it fires on create(), not construction."""
        generator = CrfGenerator(dds_file, str(tmp_path / "o.xml"), odm_version="2.0",
                                 forms=["IG.FORM.NOPE"])
        with pytest.raises(ValueError, match="unknown Form OID"):
            generator.create()

    def test_filtered_visits_drop_references_to_omitted_forms(self, dds_file, tmp_path):
        generator = CrfGenerator(dds_file, str(tmp_path / "o.xml"), odm_version="2.0",
                                 forms=["IG.FORM.VITAL-SIGNS"])
        xml = generator.write(generator.create())
        ns = "{http://www.cdisc.org/ns/odm/v2.0}"
        for event in ET.fromstring(xml).findall(f".//{ns}StudyEventDef"):
            for ref in event.findall(f"{ns}ItemGroupRef"):
                assert ref.get("ItemGroupOID") == "IG.FORM.VITAL-SIGNS"


class TestPostProcessing:
    def test_unreferenced_codelists_are_pruned(self, dds, tmp_path):
        dds["codeLists"].append({"OID": "CL.CDASH.UNUSED", "name": "Unused",
                                 "dataType": "text",
                                 "codeListItems": [{"codedValue": "X", "decode": "X"}]})
        path = tmp_path / "extra.json"
        path.write_text(json.dumps(dds), encoding="utf-8")
        generator = CrfGenerator(str(path), str(tmp_path / "o.xml"), odm_version="2.0")
        xml = generator.write(generator.create())
        assert "CL.CDASH.UNUSED" not in xml

    def test_pruning_can_be_disabled(self, dds, tmp_path):
        dds["codeLists"].append({"OID": "CL.CDASH.UNUSED", "name": "Unused",
                                 "dataType": "text",
                                 "codeListItems": [{"codedValue": "X", "decode": "X"}]})
        path = tmp_path / "extra.json"
        path.write_text(json.dumps(dds), encoding="utf-8")
        generator = CrfGenerator(str(path), str(tmp_path / "o.xml"), odm_version="2.0",
                                 prune_codelists=False)
        xml = generator.write(generator.create())
        assert "CL.CDASH.UNUSED" in xml

    def test_subset_parent_codelists_survive_pruning(self, odm20):
        """A kept subset's wasDerivedFrom target must not be pruned away."""
        _, _, xml = odm20
        ns = "{http://www.cdisc.org/ns/odm/v2.0}"
        root = ET.fromstring(xml)
        defined = {c.get("OID") for c in root.findall(f".//{ns}CodeList")}
        for codelist in root.findall(f".//{ns}CodeList"):
            for alias in codelist.findall(f"{ns}Alias"):
                if alias.get("Context") == "subsetOf":
                    assert alias.get("Name") in defined

    def test_placeholders_are_reported(self, odm20):
        generator, _, _ = odm20
        assert any("__PLACEHOLDER__" in w for w in generator.warnings)

    def test_peek_does_not_materialize_missing_children(self):
        """getattr on an unset odmlib list child corrupts element order; peek must not."""
        import odmlib.odm_2_0.model as ODM

        event = ODM.StudyEventDef(OID="SE.X", Name="X", Repeating="No", Type="Scheduled")
        before = list(vars(event))
        assert peek(event, "ItemGroupRef") is None
        assert list(vars(event)) == before


class TestSummary:
    def test_summary_counts_match_the_document(self, odm20):
        generator, _, xml = odm20
        summary = generator.summary()
        assert "forms .................... 2" in summary
        assert "study event groups" in summary

    def test_summary_reports_measurement_units_for_132(self, odm132):
        generator, _, _ = odm132
        assert "measurement units" in generator.summary()


def _first_concept(dds):
    for group in dds["itemGroups"]:
        for section in group.get("slices") or []:
            for concept in section.get("slices") or []:
                return concept
    raise AssertionError("no concept in fixture")


def _group(xml, oid):
    ns = "{http://www.cdisc.org/ns/odm/v2.0}"
    return next(g for g in ET.fromstring(xml).findall(f".//{ns}ItemGroupDef")
                if g.get("OID") == oid)
