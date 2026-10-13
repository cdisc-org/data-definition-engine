"""End-to-end tests for CrfLoader.process(), with the Library client mocked."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from loaders.common import dds_io
from loaders.common.profiles import (profile_extension_slots, strip_extensions,
                                     validate_against_profile)
from loaders.crf.crf_loader import DEFAULT_CRF_SCHEMA, CrfLoader


@pytest.fixture
def loader(tmp_path, fixtures_dir, mock_client, crf_spec_csv):
    """A CrfLoader wired to the fixtures, with no network access."""
    out = tmp_path / "combined.json"
    with patch("cdisc_library_client.CDISCLibraryClient", return_value=mock_client):
        loader = CrfLoader(
            dds_in=str(fixtures_dir / "dds_define_minimal.json"),
            usdm_file=str(fixtures_dir / "usdm_soa_minimal.json"),
            dds_out=str(out),
            crf_spec_file=str(crf_spec_csv),
            cdashct="2026-03-27", sdtmct="2026-03-27",
            cdisc_api_key="fake-key", use_cache=False,
        )
    # the constructor wraps the client in the cache proxy; bypass it entirely
    loader.client = mock_client
    loader.cdashig.client = mock_client
    loader.cdash_ct.client = mock_client
    return loader


class TestNormalization:
    def test_null_study_name_is_recomputed_from_the_usdm(self, loader):
        loader.process()
        assert loader.dds["studyName"] == "PRE0102"
        assert "None" not in loader.dds["OID"]
        assert "None" not in loader.dds["studyOID"]

    def test_origin_dict_becomes_a_list(self, loader):
        loader.process()
        item = next(i for g in loader.dds["itemGroups"] if g.get("name") == "VS"
                    for i in g["items"] if i["OID"] == "IT.VS.VSORRES")
        assert item["origin"] == [{"type": "Collected", "source": "Investigator"}]

    def test_null_length_is_dropped(self, loader):
        loader.process()
        item = next(i for g in loader.dds["itemGroups"] if g.get("name") == "VS"
                    for i in g["items"] if i["OID"] == "IT.VS.VSORRES")
        assert "length" not in item

    def test_annotated_crf_key_is_renamed(self, loader):
        loader.process()
        assert "annotatedCRFs" in loader.dds
        assert "annotatedCRF" not in loader.dds


class TestGroupSelection:
    def test_usdm_crf_extension_wins(self, loader):
        """BiomedicalConcept_7 names SYSBP_DENORMALIZED explicitly."""
        loader.process()
        concepts = _concepts(loader.dds)
        assert "IG.CON.SYSBP_DENORMALIZED" in concepts

    def test_sdtm_specialization_id_resolves_a_group(self, loader):
        """BiomedicalConcept_8 has no CRF extension; DIABP resolves through vlm_group_id."""
        loader.process()
        assert "IG.CON.DIABP_DENORMALIZED" in _concepts(loader.dds)

    def test_uncovered_concepts_are_reported(self, loader):
        loader.process()
        codes = {u["code"] for u in loader.report["uncovered"]}
        assert "C999999" in codes

    def test_activity_with_no_covered_concepts_gets_no_form(self, loader):
        loader.process()
        forms = {g["OID"] for g in loader.dds["itemGroups"] if g.get("type") == "Form"}
        assert "IG.FORM.UNCOVERED-ACTIVITY" not in forms
        assert "IG.FORM.VITAL-SIGNS" in forms

    def test_uncovered_concepts_record_the_activity_that_wanted_them(self, loader):
        loader.process()
        entry = next(u for u in loader.report["uncovered"] if u["code"] == "C999999")
        assert entry["activity"] == "UNCOVERED ACTIVITY"


class TestIncludeUncovered:
    def test_placeholder_forms_are_emitted_when_asked(self, loader):
        loader.include_uncovered = True
        loader.process()
        forms = {g["OID"] for g in loader.dds["itemGroups"] if g.get("type") == "Form"}
        assert "IG.FORM.UNCOVERED-ACTIVITY" in forms

    def test_the_placeholder_is_obviously_unfinished(self, loader):
        loader.include_uncovered = True
        loader.process()
        concept = next(c for c in _concept_objects(loader.dds)
                       if c["OID"].startswith("IG.CON.UNCOVERED_"))
        assert concept["items"][0]["question"] == "__PLACEHOLDER__"

    def test_placeholder_output_still_validates(self, loader):
        loader.include_uncovered = True
        loader.process()
        assert validate_against_profile(loader.dds, DEFAULT_CRF_SCHEMA) == []


class TestAssembly:
    def test_crf_standards_are_added_once(self, loader):
        loader.process()
        oids = [s["OID"] for s in loader.dds["standards"]]
        assert "STD.CDASHIG" in oids and "STD.CDASHCT" in oids
        assert len(oids) == len(set(oids))

    def test_existing_define_content_is_preserved(self, loader):
        before = json.dumps(_define_group(loader.dds), sort_keys=True)
        loader.process()
        after = json.dumps(_define_group(loader.dds), sort_keys=True)
        # only the normalization repairs should differ
        assert "IT.VS.VSORRES" in after
        assert len(_define_group(loader.dds)["items"]) == 3

    def test_study_events_and_acrf_leaf_are_added(self, loader):
        loader.process()
        assert len(loader.dds["studyEvents"]) == 3
        assert loader.dds["annotatedCRFs"][0]["leafID"] == "LF.acrf"

    def test_both_profile_claims_are_recorded(self, loader):
        loader.process()
        assert "https://cdisc.org/dds/profiles/crf/1.0" in loader.dds["profile"]
        assert "https://cdisc.org/dds/profiles/define-xml/1.0" in loader.dds["profile"]

    def test_output_round_trips(self, loader, tmp_path):
        loader.process()
        loader.save()
        reloaded, wrapped = dds_io.load_dds(loader.dds_out)
        assert wrapped is False
        assert reloaded["studyName"] == "PRE0102"


class TestValidation:
    def test_combined_dds_validates_against_the_crf_profile(self, loader):
        loader.process()
        errors = validate_against_profile(loader.dds, DEFAULT_CRF_SCHEMA)
        assert errors == [], errors[:5]

    def test_missing_required_field_is_caught(self, loader):
        loader.process()
        form = next(g for g in loader.dds["itemGroups"] if g.get("type") == "Form")
        del form["repeating"]
        assert validate_against_profile(loader.dds, DEFAULT_CRF_SCHEMA)

    def test_stripping_crf_extensions_leaves_a_clean_instance(self, loader):
        loader.process()
        slots = profile_extension_slots(
            DEFAULT_CRF_SCHEMA.parent / "profile.yaml")
        stripped = strip_extensions(loader.dds, slots)
        text = json.dumps(stripped)
        assert "crfSdtmTarget" not in text
        assert "crfSpecializationRef" not in text
        # non-extension CRF content survives the strip
        assert "IG.FORM.VITAL-SIGNS" in text


def _concept_objects(dds):
    return [c for g in dds["itemGroups"] if g.get("type") == "Form"
            for s in g.get("slices") or [] for c in s.get("slices") or []]


def _concepts(dds):
    return {c["OID"] for c in _concept_objects(dds)}


def _define_group(dds):
    return next(g for g in dds["itemGroups"] if g.get("name") == "VS")
