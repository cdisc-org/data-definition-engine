"""ODM 1.3.2 output: FormDef, the flattened Section level, and Alias fallbacks."""
from __future__ import annotations

import xml.etree.ElementTree as ET

NS = {"odm": "http://www.cdisc.org/ns/odm/v1.3"}


def find_all(xml: str, path: str):
    return ET.fromstring(xml).findall(path, NS)


def aliases(element) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for alias in element.findall("odm:Alias", NS):
        out.setdefault(alias.get("Context"), []).append(alias.get("Name"))
    return out


class TestStructure:
    def test_namespace_is_odm_1_3(self, odm132):
        _, _, xml = odm132
        assert ET.fromstring(xml).tag == "{http://www.cdisc.org/ns/odm/v1.3}ODM"

    def test_forms_are_form_defs(self, odm132):
        _, _, xml = odm132
        forms = find_all(xml, ".//odm:FormDef")
        assert {f.get("OID") for f in forms} == {"IG.FORM.VITAL-SIGNS", "IG.FORM.CBC"}

    def test_no_typed_item_groups(self, odm132):
        """ODM 1.3.2 ItemGroupDef has no @Type attribute at all."""
        _, _, xml = odm132
        assert all(g.get("Type") is None for g in find_all(xml, ".//odm:ItemGroupDef"))

    def test_sections_are_flattened_so_forms_point_at_concepts(self, odm132):
        _, _, xml = odm132
        form = next(f for f in find_all(xml, ".//odm:FormDef")
                    if f.get("OID") == "IG.FORM.VITAL-SIGNS")
        referenced = {r.get("ItemGroupOID") for r in form.findall("odm:ItemGroupRef", NS)}
        assert referenced
        assert all(oid.startswith("IG.CON.") for oid in referenced)
        # the Section itself is not emitted as a group
        group_oids = {g.get("OID") for g in find_all(xml, ".//odm:ItemGroupDef")}
        assert not any(oid.startswith("IG.SEC.") for oid in group_oids)

    def test_section_survives_as_an_alias_on_each_concept(self, odm132):
        _, _, xml = odm132
        concept = next(g for g in find_all(xml, ".//odm:ItemGroupDef")
                       if g.get("OID") == "IG.CON.SYSBP_DENORMALIZED")
        section = aliases(concept)["section"][0]
        assert section.startswith("IG.SEC.VITAL-SIGNS.1|")

    def test_form_records_its_section_order(self, odm132):
        _, _, xml = odm132
        form = next(f for f in find_all(xml, ".//odm:FormDef")
                    if f.get("OID") == "IG.FORM.VITAL-SIGNS")
        assert "IG.SEC.VITAL-SIGNS.1" in aliases(form)["sectionOrder"][0]


class TestAliasFallbacks:
    def test_prompt_becomes_an_alias(self, odm132):
        """1.3.2 ItemDef has no Prompt element."""
        _, _, xml = odm132
        item = next(i for i in find_all(xml, ".//odm:ItemDef")
                    if i.get("OID") == "IT.CRF.SYSBP_VSORRES")
        assert item.find("odm:Prompt", NS) is None
        assert aliases(item).get("prompt")

    def test_cdashig_prose_becomes_aliases(self, odm132):
        _, _, xml = odm132
        contexts = set()
        for item in find_all(xml, ".//odm:ItemDef"):
            contexts |= set(aliases(item))
        assert {"definition", "completionInstructions"} <= contexts

    def test_question_stays_a_native_element(self, odm132):
        _, _, xml = odm132
        item = next(i for i in find_all(xml, ".//odm:ItemDef")
                    if i.get("OID") == "IT.CRF.SYSBP_VSORRES")
        assert item.find("odm:Question/odm:TranslatedText", NS) is not None

    def test_sdtm_annotation_and_sds_var_name(self, odm132):
        _, _, xml = odm132
        item = next(i for i in find_all(xml, ".//odm:ItemDef")
                    if i.get("OID") == "IT.CRF.SYSBP_VSORRES")
        assert item.get("SDSVarName") == "VSORRES"
        assert "when VSTESTCD = SYSBP" in aliases(item)["SDTM"][0]

    def test_coding_becomes_provenance_aliases(self, odm132):
        _, _, xml = odm132
        concept = next(g for g in find_all(xml, ".//odm:ItemGroupDef")
                       if g.get("OID") == "IG.CON.SYSBP_DENORMALIZED")
        by_context = aliases(concept)
        assert any("C25298" in n for n in by_context.get("BC", []))
        assert by_context.get("CRFSpecialization")


class TestMeasurementUnits:
    def test_units_become_basic_definitions(self, odm132):
        """1.3.2 has no ItemRef/@UnitsItemOID, so units are MeasurementUnits."""
        _, _, xml = odm132
        units = find_all(xml, ".//odm:BasicDefinitions/odm:MeasurementUnit")
        assert units
        assert "MU.MMHG" in {u.get("OID") for u in units}

    def test_result_items_reference_their_unit(self, odm132):
        _, _, xml = odm132
        item = next(i for i in find_all(xml, ".//odm:ItemDef")
                    if i.get("OID") == "IT.CRF.SYSBP_VSORRES")
        refs = {r.get("MeasurementUnitOID")
                for r in item.findall("odm:MeasurementUnitRef", NS)}
        assert "MU.MMHG" in refs

    def test_every_referenced_unit_is_defined(self, odm132):
        _, _, xml = odm132
        defined = {u.get("OID") for u in
                   find_all(xml, ".//odm:BasicDefinitions/odm:MeasurementUnit")}
        referenced = {r.get("MeasurementUnitOID")
                      for r in find_all(xml, ".//odm:MeasurementUnitRef")}
        assert referenced <= defined


class TestVisits:
    def test_study_events_use_form_ref(self, odm132):
        _, _, xml = odm132
        event = next(e for e in find_all(xml, ".//odm:StudyEventDef")
                     if e.get("OID") == "SE.C1D1")
        refs = {r.get("FormOID") for r in event.findall("odm:FormRef", NS)}
        assert refs == {"IG.FORM.VITAL-SIGNS", "IG.FORM.CBC"}

    def test_protocol_references_events_directly(self, odm132):
        _, _, xml = odm132
        refs = find_all(xml, ".//odm:Protocol/odm:StudyEventRef")
        assert len(refs) == 3

    def test_standards_collapse_into_one_alias(self, odm132):
        """Protocol/Alias/@Context must be unique in the 1.3.2 XSD."""
        _, _, xml = odm132
        protocol = ET.fromstring(xml).find(".//odm:Protocol", NS)
        contexts = [a.get("Context") for a in protocol.findall("odm:Alias", NS)]
        assert contexts.count("Standard") == 1
        assert "CDASHIG" in aliases(protocol)["Standard"][0]


class TestValidation:
    def test_odmlib_and_xsd_validation_pass(self, odm132):
        from generators.crf.validate import validate_odm

        generator, odm, xml = odm132
        assert validate_odm(odm, generator.target, xml) == []
