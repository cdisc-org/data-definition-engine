"""ODM 2.0 output: typed ItemGroupDefs, native elements, and the visit structure."""
from __future__ import annotations

import xml.etree.ElementTree as ET

NS = {"odm": "http://www.cdisc.org/ns/odm/v2.0"}


def find_all(xml: str, path: str):
    return ET.fromstring(xml).findall(path, NS)


class TestStructure:
    def test_namespace_is_odm_2_0(self, odm20):
        _, _, xml = odm20
        assert ET.fromstring(xml).tag == "{http://www.cdisc.org/ns/odm/v2.0}ODM"

    def test_forms_are_typed_item_groups(self, odm20):
        _, _, xml = odm20
        forms = [g for g in find_all(xml, ".//odm:ItemGroupDef")
                 if g.get("Type") == "Form"]
        assert len(forms) == 2
        assert {f.get("OID") for f in forms} == {"IG.FORM.VITAL-SIGNS", "IG.FORM.CBC"}

    def test_form_section_concept_nesting_is_preserved(self, odm20):
        _, _, xml = odm20
        groups = {g.get("OID"): g for g in find_all(xml, ".//odm:ItemGroupDef")}
        form = groups["IG.FORM.VITAL-SIGNS"]
        section_oid = form.find("odm:ItemGroupRef", NS).get("ItemGroupOID")
        assert groups[section_oid].get("Type") == "Section"
        concept_oid = groups[section_oid].find("odm:ItemGroupRef", NS).get("ItemGroupOID")
        assert groups[concept_oid].get("Type") == "Concept"

    def test_item_group_ref_order_numbers_start_at_one(self, odm20):
        _, _, xml = odm20
        groups = {g.get("OID"): g for g in find_all(xml, ".//odm:ItemGroupDef")}
        section = next(g for g in groups.values() if g.get("Type") == "Section")
        orders = [int(r.get("OrderNumber")) for r in section.findall("odm:ItemGroupRef", NS)]
        assert orders == list(range(1, len(orders) + 1))

    def test_concept_carries_coding_provenance(self, odm20):
        _, _, xml = odm20
        concept = next(g for g in find_all(xml, ".//odm:ItemGroupDef")
                       if g.get("OID") == "IG.CON.SYSBP_DENORMALIZED")
        codes = {c.get("Code") for c in concept.findall("odm:Coding", NS)}
        assert {"C25298", "SYSBP", "SYSBP_DENORMALIZED"} <= codes


class TestNativeElements:
    def test_question_and_prompt_are_native(self, odm20):
        _, _, xml = odm20
        item = next(i for i in find_all(xml, ".//odm:ItemDef")
                    if i.get("OID") == "IT.CRF.SYSBP_VSORRES")
        assert item.find("odm:Question/odm:TranslatedText", NS) is not None
        assert item.find("odm:Prompt/odm:TranslatedText", NS) is not None

    def test_cdashig_prose_uses_native_elements(self, odm20):
        _, _, xml = odm20
        items = find_all(xml, ".//odm:ItemDef")
        assert any(i.find("odm:Definition", NS) is not None for i in items)
        assert any(i.find("odm:CRFCompletionInstructions", NS) is not None for i in items)

    def test_translated_text_type_is_set(self, odm20):
        """ODM 2.0 makes TranslatedText/@Type required."""
        _, _, xml = odm20
        texts = find_all(xml, ".//odm:TranslatedText")
        assert texts and all(t.get("Type") for t in texts)

    def test_units_item_and_prespecified_value_on_item_ref(self, odm20):
        _, _, xml = odm20
        refs = find_all(xml, ".//odm:ItemRef")
        assert any(r.get("UnitsItemOID") == "IT.CRF.SYSBP_VSORRESU" for r in refs)
        assert any(r.get("PreSpecifiedValue") == "mmHg" for r in refs)

    def test_origin_is_on_the_item_ref(self, odm20):
        _, _, xml = odm20
        origins = find_all(xml, ".//odm:ItemRef/odm:Origin")
        assert origins
        assert all(o.get("Type") and o.get("Source") for o in origins)


class TestAnnotations:
    def test_sdtm_annotations_are_embedded(self, odm20):
        """The aCRF is a rendering of this file, so annotations ship in both modes."""
        _, _, xml = odm20
        names = [a.get("Name") for a in find_all(xml, ".//odm:ItemDef/odm:Alias")
                 if a.get("Context") == "SDTM"]
        assert any("when VSTESTCD = SYSBP" in n for n in names)

    def test_cdash_variable_alias(self, odm20):
        _, _, xml = odm20
        names = [a.get("Name") for a in find_all(xml, ".//odm:ItemDef/odm:Alias")
                 if a.get("Context") == "CDASH"]
        assert "VSORRES" in names

    def test_retired_phase1_contexts_are_not_emitted(self, odm20):
        _, _, xml = odm20
        contexts = {a.get("Context") for a in find_all(xml, ".//odm:Alias")}
        assert not contexts & {"formAnnotation", "formSectionAnnotation",
                               "formSectionCompletionInstruction"}


class TestVisits:
    def test_study_event_defs(self, odm20):
        _, _, xml = odm20
        assert len(find_all(xml, ".//odm:StudyEventDef")) == 3

    def test_visits_reference_forms_with_item_group_ref(self, odm20):
        _, _, xml = odm20
        event = next(e for e in find_all(xml, ".//odm:StudyEventDef")
                     if e.get("OID") == "SE.C1D1")
        refs = {r.get("ItemGroupOID") for r in event.findall("odm:ItemGroupRef", NS)}
        assert refs == {"IG.FORM.VITAL-SIGNS", "IG.FORM.CBC"}

    def test_protocol_reaches_events_through_a_study_event_group(self, odm20):
        """ODM 2.0 removed Protocol/StudyEventRef; the group is the only path."""
        _, _, xml = odm20
        root = ET.fromstring(xml)
        assert root.find(".//odm:Protocol/odm:StudyEventRef", NS) is None
        group_refs = root.findall(".//odm:Protocol/odm:StudyEventGroupRef", NS)
        assert group_refs
        group_oids = {g.get("OID") for g in root.findall(".//odm:StudyEventGroupDef", NS)}
        assert {r.get("StudyEventGroupOID") for r in group_refs} <= group_oids

    def test_one_event_group_per_epoch(self, odm20, dds):
        _, _, xml = odm20
        names = {g.get("Name") for g in find_all(xml, ".//odm:StudyEventGroupDef")}
        expected = {e.get("category") for e in dds["studyEvents"]}
        assert names == expected


class TestStandards:
    def test_ct_standard_is_native(self, odm20):
        _, _, xml = odm20
        standards = find_all(xml, ".//odm:Standards/odm:Standard")
        assert any(s.get("Name") == "CDISC/NCI" and s.get("PublishingSet") == "CDASH"
                   for s in standards)

    def test_standard_status_is_title_case(self, odm20):
        _, _, xml = odm20
        for standard in find_all(xml, ".//odm:Standards/odm:Standard"):
            assert standard.get("Status") in {"Draft", "Final", "Provisional"}

    def test_cdashig_is_aliased_because_the_xsd_forbids_the_name(self, odm20):
        """Standard/@Name is a closed enum in the 2.0 XSD and excludes CDASHIG."""
        _, _, xml = odm20
        names = {s.get("Name") for s in find_all(xml, ".//odm:Standards/odm:Standard")}
        assert "CDASHIG" not in names
        aliases = [a.get("Name") for a in find_all(xml, ".//odm:Protocol/odm:Alias")
                   if a.get("Context") == "Standard"]
        assert any("CDASHIG" in n for n in aliases)


class TestSerialization:
    def test_xlink_namespace_is_declared_for_the_leaf(self, odm20):
        """odmlib writes Leaf/@xlink:href without declaring the prefix; see FIXES.md."""
        _, _, xml = odm20
        assert 'xmlns:xlink' in xml
        ET.fromstring(xml)  # would raise "unbound prefix" without the repair

    def test_annotated_crf_points_at_a_leaf(self, odm20):
        _, _, xml = odm20
        root = ET.fromstring(xml)
        leaf_id = root.find(".//odm:AnnotatedCRF/odm:DocumentRef", NS).get("LeafID")
        assert root.find(f".//odm:Leaf[@ID='{leaf_id}']", NS) is not None


class TestValidation:
    def test_odmlib_and_xsd_validation_pass(self, odm20):
        from generators.crf.validate import validate_odm

        generator, odm, xml = odm20
        assert validate_odm(odm, generator.target, xml) == []
