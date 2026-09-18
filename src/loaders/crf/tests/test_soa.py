"""Tests for reading the USDM Schedule of Activities."""
from __future__ import annotations

import json

from loaders.common.usdm_study import study_design, study_header
from loaders.crf.usdm.soa import SoA


class TestSoAOrdering:
    def test_activities_follow_the_previous_next_chain(self, usdm_soa):
        soa = SoA(study_design(usdm_soa))
        assert [a.id for a in soa.activities] == ["Activity_1", "Activity_2"]

    def test_encounters_follow_the_chain(self, usdm_soa):
        soa = SoA(study_design(usdm_soa))
        assert [e.name for e in soa.encounters] == ["SCREENING", "C1D1", "C1D15"]

    def test_broken_chain_falls_back_to_list_order(self, usdm_soa):
        design = study_design(usdm_soa)
        # two heads: no single starting point, so the chain cannot be walked
        design["encounters"][1]["previousId"] = None
        soa = SoA(design)
        assert len(soa.encounters) == 3

    def test_main_timeline_is_selected_by_flag_not_by_name(self, usdm_soa):
        design = study_design(usdm_soa)
        design["scheduleTimelines"][0]["name"] = "A study-specific name"
        soa = SoA(design)
        assert soa.timeline["mainTimeline"] is True

    def test_named_timeline_override(self, usdm_soa):
        soa = SoA(study_design(usdm_soa), timeline="MAIN_TIMELINE")
        assert soa.timeline["id"] == "Timeline_1"


class TestSoABindings:
    def test_epoch_name_resolved_onto_the_encounter(self, usdm_soa):
        soa = SoA(study_design(usdm_soa))
        assert soa.encounters[0].epoch_name == "Screening"
        assert soa.encounters[1].epoch_name == "Treatment"

    def test_activity_encounters_from_instances(self, usdm_soa):
        soa = SoA(study_design(usdm_soa))
        assert soa.activity_encounters("Activity_1") == ["Encounter_1", "Encounter_2"]
        assert soa.activity_encounters("Activity_2") == []

    def test_has_activity_binding_true_when_any_instance_names_one(self, usdm_soa):
        assert SoA(study_design(usdm_soa)).has_activity_binding is True

    def test_has_activity_binding_false_for_soa_workbench_exports(self, fixtures_dir):
        with open(fixtures_dir / "usdm_soa_unbound.json", encoding="utf-8") as f:
            unbound = json.load(f)
        soa = SoA(study_design(unbound))
        assert soa.has_activity_binding is False
        assert soa.activity_encounters("Activity_1") == []


class TestSoATiming:
    def test_timing_type_codes_map_to_dds_types(self, usdm_soa):
        soa = SoA(study_design(usdm_soa))
        assert soa.encounters[0].timing["type"] == "Before"
        assert soa.encounters[1].timing["type"] == "Fixed"
        assert soa.encounters[2].timing["type"] == "After"

    def test_timing_carries_iso_duration_and_label(self, usdm_soa):
        soa = SoA(study_design(usdm_soa))
        timing = soa.encounters[2].timing
        assert timing["value"] == "P14D"
        assert timing["label"] == "Day 15"
        assert timing["isNominal"] is True

    def test_missing_timing_id_returns_empty(self, usdm_soa):
        assert SoA(study_design(usdm_soa)).encounter_timing(None) == {}


class TestStudyHeader:
    def test_falls_back_to_study_name_when_no_acronym_title(self, usdm_soa):
        header = study_header(usdm_soa)
        assert header["studyName"] == "PRE0102"
        assert header["OID"] == "MDV.PRE0102.Version1.Design1"
        assert "None" not in header["studyOID"]

    def test_acronym_title_wins(self, usdm_soa):
        usdm_soa["study"]["versions"][0]["titles"].append(
            {"type": {"code": "C207646"}, "text": "ACRONYM"})
        assert study_header(usdm_soa)["studyName"] == "ACRONYM"

    def test_last_resort_is_the_literal_study(self):
        assert study_header({"study": {"versions": [{}]}})["studyName"] == "STUDY"
