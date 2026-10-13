"""Tests for the CRF refinement YAML: generation, application, and round-tripping."""
from __future__ import annotations

from unittest.mock import patch as mock_patch

import pytest
import yaml

from loaders.common.patch import PLACEHOLDER, is_placeholder, yaml_list, yaml_scalar
from loaders.crf import patch as crf_patch
from loaders.crf.crf_loader import CrfLoader


@pytest.fixture
def processed(tmp_path, fixtures_dir, mock_client, crf_spec_csv):
    out = tmp_path / "combined.json"
    with mock_patch("cdisc_library_client.CDISCLibraryClient", return_value=mock_client):
        loader = CrfLoader(
            dds_in=str(fixtures_dir / "dds_define_minimal.json"),
            usdm_file=str(fixtures_dir / "usdm_soa_minimal.json"),
            dds_out=str(out), crf_spec_file=str(crf_spec_csv),
            cdashct="2026-03-27", sdtmct="2026-03-27",
            cdisc_api_key="fake-key", use_cache=False,
        )
    loader.client = mock_client
    loader.cdashig.client = mock_client
    loader.cdash_ct.client = mock_client
    loader.process()
    return loader


class TestScalarRendering:
    def test_placeholder_detection(self):
        assert is_placeholder(PLACEHOLDER)
        assert is_placeholder(None)
        assert is_placeholder("")
        assert not is_placeholder("a real value")

    def test_text_with_colons_is_quoted(self):
        assert yaml_scalar("VSORRES when VSTESTCD: SYSBP").startswith('"')

    def test_plain_text_is_unquoted(self):
        assert yaml_scalar("Vital Signs") == "Vital Signs"

    def test_none_and_booleans(self):
        assert yaml_scalar(None) == "null"
        assert yaml_scalar(True) == "true"

    @pytest.mark.parametrize("text", ["No", "Yes", "N", "Y", "on", "off", "null",
                                      "true", "False", "~", "007", "1.3.2e5"])
    def test_yaml_reserved_spellings_round_trip_as_strings(self, text):
        """`repeating: No` would otherwise come back as the boolean False."""
        assert yaml.safe_load(f"v: {yaml_scalar(text)}")["v"] == text

    def test_repeating_no_survives_a_patch_round_trip(self, processed, tmp_path):
        path = tmp_path / "r.yaml"
        processed.generate_patch_file(str(path))
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert loaded["forms"]["IG.FORM.VITAL-SIGNS"]["repeating"] == "No"

    def test_list_rendering(self):
        assert yaml_list(["A", "B"]) == "[A, B]"


class TestPatchGeneration:
    def test_written_file_is_valid_yaml(self, processed, tmp_path):
        path = tmp_path / "refinement.yaml"
        processed.generate_patch_file(str(path))
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert set(loaded) >= {"forms", "sections", "studyEvents",
                               "uncoveredConcepts", "crfGroupChoices"}

    def test_instructional_comments_survive(self, processed, tmp_path):
        path = tmp_path / "refinement.yaml"
        processed.generate_patch_file(str(path))
        assert "__PLACEHOLDER__" in path.read_text(encoding="utf-8").splitlines()[3]

    def test_sections_list_their_placeholders(self, processed, tmp_path):
        path = tmp_path / "refinement.yaml"
        processed.generate_patch_file(str(path))
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        section = loaded["sections"]["IG.SEC.VITAL-SIGNS.1"]
        assert section["crfSectionInstructions"] == PLACEHOLDER

    def test_uncovered_concepts_are_listed(self, processed, tmp_path):
        path = tmp_path / "refinement.yaml"
        processed.generate_patch_file(str(path))
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert any(u["code"] == "C999999" for u in loaded["uncoveredConcepts"])

    def test_study_events_carry_candidate_forms(self, processed, tmp_path):
        path = tmp_path / "refinement.yaml"
        processed.generate_patch_file(str(path))
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "IG.FORM.VITAL-SIGNS" in loaded["studyEvents"]["SE.C1D15"]["candidates"]


class TestPatchApplication:
    def _write(self, tmp_path, content):
        path = tmp_path / "p.yaml"
        path.write_text(yaml.safe_dump(content), encoding="utf-8")
        return str(path)

    def test_section_instructions_are_applied(self, processed, tmp_path):
        path = self._write(tmp_path, {"sections": {"IG.SEC.VITAL-SIGNS.1": {
            "crfSectionInstructions": "Measure after 5 minutes seated."}}})
        crf_patch.apply_patch_file(path, processed.dds)
        section = _section(processed.dds, "IG.SEC.VITAL-SIGNS.1")
        assert section["crfSectionInstructions"] == "Measure after 5 minutes seated."

    def test_unfilled_placeholders_are_never_written_back(self, processed, tmp_path):
        path = self._write(tmp_path, {"sections": {"IG.SEC.VITAL-SIGNS.1": {
            "label": PLACEHOLDER}}})
        before = _section(processed.dds, "IG.SEC.VITAL-SIGNS.1")["label"]
        crf_patch.apply_patch_file(path, processed.dds)
        assert _section(processed.dds, "IG.SEC.VITAL-SIGNS.1")["label"] == before

    def test_study_event_binding_is_applied(self, processed, tmp_path):
        path = self._write(tmp_path, {"studyEvents": {"SE.C1D15": {
            "itemGroups": ["IG.FORM.VITAL-SIGNS"]}}})
        crf_patch.apply_patch_file(path, processed.dds)
        event = next(e for e in processed.dds["studyEvents"] if e["OID"] == "SE.C1D15")
        assert event["itemGroups"] == ["IG.FORM.VITAL-SIGNS"]

    def test_binding_an_unknown_form_is_refused(self, processed, tmp_path):
        path = self._write(tmp_path, {"studyEvents": {"SE.C1D15": {
            "itemGroups": ["IG.FORM.NOT-A-FORM"]}}})
        crf_patch.apply_patch_file(path, processed.dds)
        event = next(e for e in processed.dds["studyEvents"] if e["OID"] == "SE.C1D15")
        assert event["itemGroups"] == []

    def test_concepts_can_be_reordered_within_a_section(self, processed, tmp_path):
        section = _section(processed.dds, "IG.SEC.VITAL-SIGNS.1")
        original = [c["OID"] for c in section["slices"]]
        path = self._write(tmp_path, {"sections": {"IG.SEC.VITAL-SIGNS.1": {
            "concepts": list(reversed(original))}}})
        crf_patch.apply_patch_file(path, processed.dds)
        assert [c["OID"] for c in
                _section(processed.dds, "IG.SEC.VITAL-SIGNS.1")["slices"]] == \
            list(reversed(original))

    def test_naming_an_unknown_concept_leaves_the_layout_alone(self, processed, tmp_path):
        section = _section(processed.dds, "IG.SEC.VITAL-SIGNS.1")
        original = [c["OID"] for c in section["slices"]]
        path = self._write(tmp_path, {"sections": {"IG.SEC.VITAL-SIGNS.1": {
            "concepts": ["IG.CON.NOPE"]}}})
        crf_patch.apply_patch_file(path, processed.dds)
        assert [c["OID"] for c in
                _section(processed.dds, "IG.SEC.VITAL-SIGNS.1")["slices"]] == original

    def test_item_patch_reaches_every_copy_of_a_shared_item(self, processed, tmp_path):
        path = self._write(tmp_path, {"items": {"IT.CRF.VSDAT": {
            "crfCompletionInstructions": "Use the date of the visit."}}})
        crf_patch.apply_patch_file(path, processed.dds)
        copies = [i for c in _concepts(processed.dds) for i in c["items"]
                  if i["OID"] == "IT.CRF.VSDAT"]
        assert copies, "fixture should share VSDAT across concepts"
        assert all(i["crfCompletionInstructions"] == "Use the date of the visit."
                   for i in copies)

    def test_unknown_oids_are_skipped_not_fatal(self, processed, tmp_path):
        path = self._write(tmp_path, {"forms": {"IG.FORM.NOPE": {"label": "x"}},
                                      "items": {"IT.CRF.NOPE": {"question": "x"}}})
        assert crf_patch.apply_patch_file(path, processed.dds) == []

    def test_empty_patch_is_a_no_op(self, processed, tmp_path):
        path = tmp_path / "empty.yaml"
        path.write_text("", encoding="utf-8")
        assert crf_patch.apply_patch_file(str(path), processed.dds) == []

    def test_round_trip_generate_apply_regenerate(self, processed, tmp_path):
        first = tmp_path / "one.yaml"
        processed.generate_patch_file(str(first))
        content = yaml.safe_load(first.read_text(encoding="utf-8"))
        content["sections"]["IG.SEC.VITAL-SIGNS.1"]["crfSectionInstructions"] = "Answered."
        answered = tmp_path / "answered.yaml"
        answered.write_text(yaml.safe_dump(content), encoding="utf-8")

        crf_patch.apply_patch_file(str(answered), processed.dds)
        second = tmp_path / "two.yaml"
        processed.generate_patch_file(str(second))
        regenerated = yaml.safe_load(second.read_text(encoding="utf-8"))
        # the answered placeholder is gone from the regenerated file
        assert regenerated["sections"]["IG.SEC.VITAL-SIGNS.1"][
            "crfSectionInstructions"] == "Answered."


def _section(dds, oid):
    for group in dds["itemGroups"]:
        for section in group.get("slices") or []:
            if section.get("OID") == oid:
                return section
    raise AssertionError(f"section {oid} not found")


def _concepts(dds):
    return [c for g in dds["itemGroups"] for s in g.get("slices") or []
            for c in s.get("slices") or []]
