"""Tests for the codelist, item, form and study-event builders."""
from __future__ import annotations

import pytest

from loaders.crf.builders.codelists import CodeListBuilder
from loaders.crf.builders.forms import FormBuilder
from loaders.crf.builders.items import ItemBuilder
from loaders.crf.builders.study_events import StudyEventBuilder
from loaders.crf.sources.cdash_ct import CdashCtSource
from loaders.crf.sources.cdashig import CdashigSource
from loaders.common.usdm_study import study_design
from loaders.crf.usdm.soa import SoA


@pytest.fixture
def cdashig(mock_client):
    return CdashigSource(mock_client, "2.3")


@pytest.fixture
def cdash_ct(mock_client):
    return CdashCtSource(mock_client, "2026-03-27")


@pytest.fixture
def codelists(cdash_ct):
    return CodeListBuilder(cdash_ct, "2026-03-27")


@pytest.fixture
def items(cdashig, codelists):
    return ItemBuilder(cdashig, codelists,
                       sdtm_item_oids={"IT.VS.VSORRES", "IT.VS.VSTESTCD", "IT.VS.VSDTC"})


class TestCodeListBuilder:
    def test_full_codelist_when_nothing_restricts_it(self, codelists, spec_source):
        group = spec_source.groups()["SYSBP_DENORMALIZED"]
        unit = next(i for i in group.items if i.crf_item == "SYSBP_VSORRESU")
        oid = codelists.codelist_for(unit, group)
        assert oid == "CL.CDASH.C66770"
        assert len(codelists.code_lists[oid]["codeListItems"]) == 4

    def test_subset_codelist_when_value_list_restricts_it(self, codelists, spec_source):
        group = spec_source.groups()["SYSBP_DENORMALIZED"]
        pos = next(i for i in group.items if i.crf_item == "SYSBP_VSPOS")
        oid = codelists.codelist_for(pos, group)
        assert oid == "CL.CDASH.C71148.SYSBP_DENORMALIZED"
        subset = codelists.code_lists[oid]
        assert subset["wasDerivedFrom"] == "CL.CDASH.C71148"
        assert {t["codedValue"] for t in subset["codeListItems"]} == set(pos.value_list)

    def test_subset_decodes_come_from_the_display_list(self, codelists, spec_source):
        group = spec_source.groups()["SYSBP_DENORMALIZED"]
        pos = next(i for i in group.items if i.crf_item == "SYSBP_VSPOS")
        oid = codelists.codelist_for(pos, group)
        terms = {t["codedValue"]: t["decode"] for t in codelists.code_lists[oid]["codeListItems"]}
        assert terms["SITTING"] == "Sitting"

    def test_no_codelist_for_a_plain_field(self, codelists, spec_source):
        group = spec_source.groups()["SYSBP_DENORMALIZED"]
        result = next(i for i in group.items if i.crf_item == "SYSBP_VSORRES")
        assert codelists.codelist_for(result, group) is None

    def test_codelists_are_deduplicated(self, codelists, spec_source):
        groups = spec_source.groups()
        for name in ("SYSBP_DENORMALIZED", "DIABP_DENORMALIZED"):
            group = groups[name]
            for item in group.items:
                codelists.codelist_for(item, group)
        oids = [c["OID"] for c in codelists.as_list()]
        assert len(oids) == len(set(oids))


class TestItemBuilder:
    def test_item_oid_and_core_attributes(self, items, spec_source):
        group = spec_source.groups()["SYSBP_DENORMALIZED"]
        built = {i["OID"]: i for i in items.build_group_items(group)}
        result = built["IT.CRF.SYSBP_VSORRES"]
        assert result["name"] == "SYSBP_VSORRES"
        assert result["dataType"] == "integer"
        assert result["mandatory"] is True

    def test_cdashig_fills_what_the_specialization_leaves_blank(self, items, spec_source):
        group = spec_source.groups()["SYSBP_DENORMALIZED"]
        built = {i["OID"]: i for i in items.build_group_items(group)}
        result = built["IT.CRF.SYSBP_VSORRES"]
        assert result["definition"].startswith("Result of the vital signs")
        assert result["crfCompletionInstructions"] == "Record the vital sign result."

    def test_specialization_question_wins_over_cdashig(self, items, spec_source):
        group = spec_source.groups()["SYSBP_DENORMALIZED"]
        built = {i["OID"]: i for i in items.build_group_items(group)}
        assert built["IT.CRF.SYSBP_VSORRES"]["question"] == \
            "What was the result of the Systolic Blood Pressure measurement?"

    def test_units_item_links_result_to_its_unit_sibling(self, items, spec_source):
        group = spec_source.groups()["SYSBP_DENORMALIZED"]
        built = {i["OID"]: i for i in items.build_group_items(group)}
        assert built["IT.CRF.SYSBP_VSORRES"]["unitsItem"] == "IT.CRF.SYSBP_VSORRESU"

    def test_sdtm_target_resolves_to_existing_define_items(self, items, spec_source):
        group = spec_source.groups()["SYSBP_DENORMALIZED"]
        built = {i["OID"]: i for i in items.build_group_items(group)}
        target = built["IT.CRF.SYSBP_VSORRES"]["crfSdtmTarget"]
        assert target["annotation"] == "VSORRES when VSTESTCD = SYSBP"
        assert "IT.VS.VSORRES" in target["items"]

    def test_origin_is_collected_by_default(self, items, spec_source):
        group = spec_source.groups()["SYSBP_DENORMALIZED"]
        built = {i["OID"]: i for i in items.build_group_items(group)}
        assert built["IT.CRF.SYSBP_VSORRES"]["origin"] == [
            {"type": "Collected", "source": "Investigator"}]

    def test_prepopulated_value_becomes_a_protocol_origin(self, items, spec_source):
        """A pre-populated unit is stated by the protocol, not collected."""
        groups = spec_source.groups()
        prepopulated = None
        for group in groups.values():
            for built in items.build_group_items(group):
                if built.get("preSpecifiedValue"):
                    prepopulated = built
                    break
        if prepopulated is None:
            pytest.skip("no pre-populated item in the fixture extract")
        assert prepopulated["origin"][0]["type"] == "Protocol"

    def test_cdash_alias_records_the_source_variable(self, items, spec_source):
        group = spec_source.groups()["SYSBP_DENORMALIZED"]
        built = {i["OID"]: i for i in items.build_group_items(group)}
        assert {"context": "CDASH", "name": "VSORRES"} in \
            built["IT.CRF.SYSBP_VSORRES"]["aliases"]

    def test_shared_item_is_defined_once_and_shared(self, items, spec_source):
        """VSDAT is collected by every Vital Signs concept but is one field."""
        groups = spec_source.groups()
        first = items.build_group_items(groups["SYSBP_DENORMALIZED"])
        second = items.build_group_items(groups["DIABP_DENORMALIZED"])
        a = next(i for i in first if i["OID"] == "IT.CRF.VSDAT")
        b = next(i for i in second if i["OID"] == "IT.CRF.VSDAT")
        assert a is b, "the shared item must be the same object in both concepts"
        assert len([i for i in items.as_list() if i["OID"] == "IT.CRF.VSDAT"]) == 1

    def test_complementary_definitions_merge_rather_than_split(self, items, spec_source):
        """One row supplies a question, another a prompt: one field, both values."""
        groups = spec_source.groups()
        items.build_group_items(groups["SYSBP_DENORMALIZED"])
        items.build_group_items(groups["HR_DENORMALIZED"])
        vsdat = items.by_oid("IT.CRF.VSDAT")
        assert vsdat["question"]
        assert not any("VSDAT" in c for c in items.conflicts)

    def test_concept_property_is_linked_by_dec_code(self, items, spec_source):
        group = spec_source.groups()["SYSBP_DENORMALIZED"]
        built = {i["OID"]: i
                 for i in items.build_group_items(group, {"C70856": "CONCPROP.BCP_44"})}
        assert built["IT.CRF.SYSBP_VSORRES"]["conceptProperty"] == "CONCPROP.BCP_44"


class TestFormBuilder:
    def _build(self, items, spec_source, usdm_soa):
        soa = SoA(study_design(usdm_soa))
        activity = soa.activities[0]
        groups = spec_source.groups()
        resolutions = [
            {"group": groups["SYSBP_DENORMALIZED"], "concept_oid": "CONC.BiomedicalConcept_7",
             "bc_name": "Systolic Blood Pressure"},
            {"group": groups["DIABP_DENORMALIZED"], "concept_oid": None,
             "bc_name": "Diastolic Blood Pressure"},
        ]
        return FormBuilder(items, "2025-12-31").build_form(activity, resolutions)

    def test_form_section_concept_nesting(self, items, spec_source, usdm_soa):
        form = self._build(items, spec_source, usdm_soa)
        assert form["type"] == "Form"
        section = form["slices"][0]
        assert section["type"] == "Section"
        assert [c["type"] for c in section["slices"]] == ["Concept", "Concept"]

    def test_oid_conventions(self, items, spec_source, usdm_soa):
        form = self._build(items, spec_source, usdm_soa)
        assert form["OID"] == "IG.FORM.VITAL-SIGNS"
        assert form["slices"][0]["OID"] == "IG.SEC.VITAL-SIGNS.1"
        assert form["slices"][0]["slices"][0]["OID"] == "IG.CON.SYSBP_DENORMALIZED"

    def test_concept_order_follows_biomedical_concept_ids(self, items, spec_source, usdm_soa):
        form = self._build(items, spec_source, usdm_soa)
        assert [c["OID"] for c in form["slices"][0]["slices"]] == \
            ["IG.CON.SYSBP_DENORMALIZED", "IG.CON.DIABP_DENORMALIZED"]

    def test_concept_carries_provenance_coding(self, items, spec_source, usdm_soa):
        form = self._build(items, spec_source, usdm_soa)
        codings = form["slices"][0]["slices"][0]["coding"]
        systems = {c["codeSystem"].rsplit("/", 1)[-1]: c["code"] for c in codings}
        assert systems["biomedicalconcepts"] == "C25298"
        assert systems["datasetspecializations"] == "SYSBP"
        assert systems["specializations"] == "SYSBP_DENORMALIZED"

    def test_implements_concept_is_set_when_known(self, items, spec_source, usdm_soa):
        form = self._build(items, spec_source, usdm_soa)
        concepts = form["slices"][0]["slices"]
        assert concepts[0]["implementsConcept"] == "CONC.BiomedicalConcept_7"
        assert "implementsConcept" not in concepts[1]

    def test_normalized_group_repeats(self, items, spec_source, usdm_soa):
        soa = SoA(study_design(usdm_soa))
        groups = spec_source.groups()
        form = FormBuilder(items).build_form(
            soa.activities[0],
            [{"group": groups["SYSBP_NORMALIZED"], "concept_oid": None, "bc_name": "SBP"}])
        assert form["slices"][0]["slices"][0]["repeating"] == "Simple"

    def test_usdm_activity_provenance(self, items, spec_source, usdm_soa):
        form = self._build(items, spec_source, usdm_soa)
        assert form["crfActivityRef"] == "Activity_1"
        assert {"context": "USDM", "name": "Activity_1"} in form["aliases"]


class TestStudyEventBuilder:
    def test_one_event_per_encounter(self, usdm_soa):
        soa = SoA(study_design(usdm_soa))
        events = StudyEventBuilder(soa).build({})
        assert [e["OID"] for e in events] == ["SE.SCREENING", "SE.C1D1", "SE.C1D15"]

    def test_epoch_becomes_the_category(self, usdm_soa):
        soa = SoA(study_design(usdm_soa))
        events = StudyEventBuilder(soa).build({})
        assert events[0]["category"] == "Screening"
        assert events[1]["category"] == "Treatment"

    def test_forms_bind_through_activity_ids(self, usdm_soa):
        soa = SoA(study_design(usdm_soa))
        events = StudyEventBuilder(soa).build({"Activity_1": "IG.FORM.VITAL-SIGNS"})
        by_oid = {e["OID"]: e for e in events}
        assert by_oid["SE.SCREENING"]["itemGroups"] == ["IG.FORM.VITAL-SIGNS"]
        assert by_oid["SE.C1D15"]["itemGroups"] == []

    def test_unbound_events_are_reported(self, usdm_soa):
        soa = SoA(study_design(usdm_soa))
        builder = StudyEventBuilder(soa)
        builder.build({"Activity_1": "IG.FORM.VITAL-SIGNS"})
        assert builder.unbound == ["SE.C1D15"]

    def test_occurrence_carries_the_timing(self, usdm_soa):
        soa = SoA(study_design(usdm_soa))
        events = StudyEventBuilder(soa).build({})
        assert events[1]["occurrence"]["timing"]["value"] == "P0D"
        assert events[1]["occurrence"]["event"] == "SAI_2"

    def test_encounter_type_becomes_coding(self, usdm_soa):
        soa = SoA(study_design(usdm_soa))
        events = StudyEventBuilder(soa).build({})
        assert events[0]["coding"][0]["code"] == "C25716"
