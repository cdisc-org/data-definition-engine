"""Tests for the CRF metadata sources: specializations, CDASHIG, and CDASH CT."""
from __future__ import annotations

import pytest

from loaders.crf.sources.cdash_ct import CdashCtSource
from loaders.crf.sources.cdashig import CdashigSource
from loaders.crf.sources.crf_specializations import (CsvCrfSpecializationSource,
                                                     LibraryCrfSpecializationSource,
                                                     open_source)


class TestCrfSpecializationSource:
    def test_groups_are_keyed_by_crf_group_id(self, spec_source):
        groups = spec_source.groups()
        assert "SYSBP_DENORMALIZED" in groups
        assert groups["SYSBP_DENORMALIZED"].bc_id == "C25298"
        assert groups["SYSBP_DENORMALIZED"].vlm_group_id == "SYSBP"
        assert groups["SYSBP_DENORMALIZED"].domain == "VS"

    def test_items_are_ordered_by_order_number(self, spec_source):
        items = spec_source.groups()["SYSBP_DENORMALIZED"].items
        assert [i.order_number for i in items] == sorted(i.order_number for i in items)
        assert items[0].crf_item == "VSDAT"

    def test_semicolon_lists_are_split(self, spec_source):
        pos = next(i for i in spec_source.groups()["SYSBP_DENORMALIZED"].items
                   if i.crf_item == "SYSBP_VSPOS")
        assert "SITTING" in pos.value_list
        assert "Sitting" in pos.value_display_list
        assert len(pos.value_list) == len(pos.value_display_list)

    def test_sdtm_target_variables_are_split(self, spec_source):
        res = next(i for i in spec_source.groups()["SYSBP_DENORMALIZED"].items
                   if i.crf_item == "SYSBP_VSORRES")
        assert "VSORRES" in res.sdtm_target_variable
        assert res.sdtm_annotation == "VSORRES when VSTESTCD = SYSBP"

    def test_normalized_flag(self, spec_source):
        groups = spec_source.groups()
        assert groups["SYSBP_NORMALIZED"].is_normalized is True
        assert groups["SYSBP_DENORMALIZED"].is_normalized is False

    def test_index_by_bc_and_vlm(self, spec_source):
        by_bc = spec_source.index_by_bc()
        by_vlm = spec_source.index_by_vlm()
        # C25298 has both a Normalized and a Denormalized group
        assert len(by_bc["C25298"]) == 2
        assert {g.crf_group_id for g in by_vlm["SYSBP"]} == {"SYSBP_DENORMALIZED",
                                                            "SYSBP_NORMALIZED"}

    def test_open_source_selects_csv_by_extension(self, crf_spec_csv):
        assert isinstance(open_source(crf_spec_csv), CsvCrfSpecializationSource)

    def test_open_source_library_is_not_implemented_yet(self):
        source = open_source(None, "library", client=None)
        assert isinstance(source, LibraryCrfSpecializationSource)
        with pytest.raises(NotImplementedError, match="no CRF Specializations endpoint"):
            source.groups()

    def test_open_source_requires_a_file(self):
        with pytest.raises(ValueError, match="crf_spec_file is required"):
            open_source(None, "csv")


class TestCdashigSource:
    def test_domain_fields_are_indexed_by_name(self, mock_client):
        source = CdashigSource(mock_client, "2.3")
        assert "VSORRES" in source.domain_fields("VS")

    def test_lookup_returns_field_content(self, mock_client):
        source = CdashigSource(mock_client, "2.3")
        field = source.lookup("VS", "VSORRES")
        assert field["definition"].startswith("Result of the vital signs")
        assert field["completionInstructions"] == "Record the vital sign result."

    def test_lookup_falls_back_to_the_class_level_field(self, mock_client):
        """VSORRESU is published only as the class-level --ORRESU."""
        source = CdashigSource(mock_client, "2.3")
        field = source.lookup("VS", "VSORRESU")
        assert field.get("label") == "Original Units"

    def test_unknown_variable_returns_empty(self, mock_client):
        assert CdashigSource(mock_client, "2.3").lookup("VS", "NOSUCHVAR") == {}

    def test_missing_domain_is_a_soft_miss(self):
        from unittest.mock import MagicMock
        client = MagicMock()
        client.get_api_json.side_effect = RuntimeError("404")
        source = CdashigSource(client, "2.3")
        assert source.domain_fields("ZZ") == {}
        assert source.missing_domains

    def test_scenario_href_is_discovered_not_guessed(self, mock_client):
        source = CdashigSource(mock_client, "2.3")
        href = source._scenario_href("VS", "Horizontal Generic")
        assert href == "/mdr/cdashig/2-3/scenarios/VS.HorizontalGeneric"

    def test_unknown_scenario_returns_empty(self, mock_client):
        source = CdashigSource(mock_client, "2.3")
        assert source.scenario_fields("VS", "No Such Scenario") == {}


class TestCdashCtSource:
    def test_codelist_terms(self, mock_client):
        source = CdashCtSource(mock_client, "2026-03-27")
        assert len(source.terms("C66770")) == 4

    def test_decode_and_code_maps(self, mock_client):
        source = CdashCtSource(mock_client, "2026-03-27")
        assert source.decode_map("C66770")["mmHg"] == "Millimeter of Mercury"
        assert source.code_map("C66770")["mmHg"] == "C49670"

    def test_missing_codelist_is_recorded(self, mock_client):
        source = CdashCtSource(mock_client, "2026-03-27")
        assert source.codelist("C00000") == {}
        assert "C00000" in source.missing

    def test_empty_code_returns_empty(self, mock_client):
        assert CdashCtSource(mock_client, "2026-03-27").codelist("") == {}
