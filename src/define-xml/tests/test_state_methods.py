"""
Tests for methods that read/write internal state without calling the CDISC API.

State is set directly on the processor instance before each test so that the
method under test can be exercised in isolation.
"""

import pytest
from unittest.mock import patch, MagicMock


# ── __init__ validation ───────────────────────────────────────────────────────

class TestInit:
    """USDMDefineJSONProcessor.__init__ parameter validation and state setup."""

    def test_invalid_sdtmct_format_raises_value_error(self, minimal_usdm_file, mock_client, tmp_path):
        from create_define_json import USDMDefineJSONProcessor

        with patch("create_define_json.CDISCLibraryClient", return_value=mock_client):
            with pytest.raises(ValueError, match="sdtmct must be in yyyy-mm-dd format"):
                USDMDefineJSONProcessor(
                    usdm_file=str(minimal_usdm_file),
                    output_template=str(tmp_path / "out.json"),
                    sdtmig="3.4",
                    sdtmct="20250328",
                    studyversion=0, studydesign=0, docversion=0,
                    cdisc_api_key="fake", cosmosversion="v2", debug=False,
                )

    def test_none_sdtmct_skips_date_validation(self, minimal_usdm_file, mock_client, tmp_path):
        from create_define_json import USDMDefineJSONProcessor

        with patch("create_define_json.CDISCLibraryClient", return_value=mock_client):
            proc = USDMDefineJSONProcessor(
                usdm_file=str(minimal_usdm_file),
                output_template=str(tmp_path / "out.json"),
                sdtmig="3.4",
                sdtmct=None,
                studyversion=0, studydesign=0, docversion=0,
                cdisc_api_key="fake", cosmosversion="v2", debug=False,
            )
        assert proc is not None

    def test_template_has_required_top_level_keys(self, processor):
        for key in ["OID", "name", "description", "fileOID", "odmVersion",
                    "itemGroups", "conditions", "whereClauses", "codeLists", "standards"]:
            assert key in processor.template

    def test_study_version_data_extracted_from_usdm(self, processor):
        assert processor.study_version_data is not None

    def test_study_design_data_extracted_from_usdm(self, processor):
        assert processor.studyDesignData is not None
        assert "studyType" in processor.studyDesignData

    def test_internal_collections_initialised_empty(self, processor):
        assert processor.datasets_dict == {}
        assert processor.bc_dict == {}
        assert processor.vlm_lookup == {}
        assert processor.item_groups == []
        assert processor.conditions == []
        assert processor.where_clauses == []


# ── _build_global_codelist_terms ─────────────────────────────────────────────

class TestBuildGlobalCodelistTerms:
    """_build_global_codelist_terms() pre-scans datasets_dict for term unions."""

    def test_empty_datasets_dict_gives_empty_result(self, processor):
        processor.datasets_dict = {}
        processor._build_global_codelist_terms()
        assert processor.global_codelist_terms == {}

    def test_single_dataset_with_terms_indexed(self, processor):
        processor.datasets_dict = {
            "VS": {"VSTESTCD": {"codelist": {
                "C96664": {"codelist_concept_id": "C96664", "terms": ["SYSBP", "DIABP"]}
            }}}
        }
        processor._build_global_codelist_terms()
        assert "SYSBP" in processor.global_codelist_terms["C96664"]
        assert "DIABP" in processor.global_codelist_terms["C96664"]

    def test_multiple_datasets_same_codelist_id_are_unioned(self, processor):
        processor.datasets_dict = {
            "VS": {"VSTESTCD": {"codelist": {"C96664": {"codelist_concept_id": "C96664", "terms": ["SYSBP"]}}}},
            "LB": {"LBTESTCD": {"codelist": {"C96664": {"codelist_concept_id": "C96664", "terms": ["GLUCOSE"]}}}},
        }
        processor._build_global_codelist_terms()
        assert {"SYSBP", "GLUCOSE"}.issubset(processor.global_codelist_terms["C96664"])

    def test_empty_terms_list_stores_empty_set(self, processor):
        processor.datasets_dict = {
            "VS": {"VSTESTCD": {"codelist": {"C96664": {"codelist_concept_id": "C96664", "terms": []}}}}
        }
        processor._build_global_codelist_terms()
        assert processor.global_codelist_terms.get("C96664") == set()

    def test_entry_without_codelist_concept_id_is_skipped(self, processor):
        processor.datasets_dict = {
            "VS": {"VSTESTCD": {"codelist": {"C96664": {"terms": ["SYSBP"]}}}}  # no codelist_concept_id
        }
        processor._build_global_codelist_terms()
        assert processor.global_codelist_terms == {}

    def test_variable_without_codelist_key_is_skipped(self, processor):
        processor.datasets_dict = {"VS": {"VSTESTCD": {"role": "Topic"}}}
        processor._build_global_codelist_terms()
        assert processor.global_codelist_terms == {}

    def test_result_values_are_sets(self, processor):
        processor.datasets_dict = {
            "VS": {"VSTESTCD": {"codelist": {"C96664": {"codelist_concept_id": "C96664", "terms": ["SYSBP"]}}}}
        }
        processor._build_global_codelist_terms()
        assert isinstance(processor.global_codelist_terms["C96664"], set)


# ── _update_subset_codelist_names ────────────────────────────────────────────

class TestUpdateSubsetCodelistNames:
    """_update_subset_codelist_names() appends '(Subset X)' for underscore keys."""

    def test_key_without_underscore_left_unchanged(self, processor):
        processor.code_lists_map = {"UNIT": {"OID": "CL.UNIT", "name": "Unit"}}
        processor._update_subset_codelist_names()
        assert processor.code_lists_map["UNIT"]["name"] == "Unit"

    def test_key_with_underscore_appends_subset_qualifier(self, processor):
        processor.code_lists_map = {"UNIT_BMI": {"OID": "CL.UNIT_BMI", "name": "Unit"}}
        processor._update_subset_codelist_names()
        assert processor.code_lists_map["UNIT_BMI"]["name"] == "Unit (Subset BMI)"

    def test_calling_twice_is_idempotent(self, processor):
        processor.code_lists_map = {"UNIT_BMI": {"OID": "CL.UNIT_BMI", "name": "Unit"}}
        processor._update_subset_codelist_names()
        processor._update_subset_codelist_names()
        assert processor.code_lists_map["UNIT_BMI"]["name"] == "Unit (Subset BMI)"

    def test_multiple_underscores_splits_only_on_first(self, processor):
        processor.code_lists_map = {"UNIT_WEIGHT_KG": {"OID": "CL.UNIT_WEIGHT_KG", "name": "Unit"}}
        processor._update_subset_codelist_names()
        assert processor.code_lists_map["UNIT_WEIGHT_KG"]["name"] == "Unit (Subset WEIGHT_KG)"

    def test_only_subset_keys_are_modified(self, processor):
        processor.code_lists_map = {
            "UNIT": {"name": "Unit"},
            "UNIT_BMI": {"name": "Unit"},
        }
        processor._update_subset_codelist_names()
        assert processor.code_lists_map["UNIT"]["name"] == "Unit"
        assert processor.code_lists_map["UNIT_BMI"]["name"] == "Unit (Subset BMI)"


# ── _find_item_by_oid ─────────────────────────────────────────────────────────

class TestFindItemByOid:
    """_find_item_by_oid(oid) searches itemGroups items and slices."""

    def _load_template(self, processor):
        processor.template["itemGroups"] = [
            {
                "OID": "IG.VS",
                "items": [
                    {"OID": "IT.VS.VSTESTCD", "name": "VSTESTCD", "description": "Test Code"},
                    {"OID": "IT.VS.VSORRES", "name": "VSORRES", "description": "Original Result"},
                ],
                "slices": [
                    {
                        "OID": "VL.VS.VSORRES",
                        "items": [{"OID": "IT.VS.VSORRES.SYSBP", "name": "VSORRES"}],
                    }
                ],
            }
        ]

    def test_finds_item_in_items_list(self, processor):
        self._load_template(processor)
        item = processor._find_item_by_oid("IT.VS.VSTESTCD")
        assert item is not None
        assert item["name"] == "VSTESTCD"

    def test_finds_item_inside_a_slice(self, processor):
        self._load_template(processor)
        item = processor._find_item_by_oid("IT.VS.VSORRES.SYSBP")
        assert item is not None
        assert item["OID"] == "IT.VS.VSORRES.SYSBP"

    def test_returns_none_when_oid_not_found(self, processor):
        self._load_template(processor)
        assert processor._find_item_by_oid("IT.VS.NONEXISTENT") is None

    def test_returns_none_for_empty_item_groups(self, processor):
        processor.template["itemGroups"] = []
        assert processor._find_item_by_oid("IT.VS.VSTESTCD") is None

    def test_returns_first_match_across_item_groups(self, processor):
        processor.template["itemGroups"] = [
            {"OID": "IG.VS", "items": [{"OID": "IT.VS.VSTESTCD", "name": "first"}], "slices": []},
            {"OID": "IG.LB", "items": [{"OID": "IT.VS.VSTESTCD", "name": "second"}], "slices": []},
        ]
        assert processor._find_item_by_oid("IT.VS.VSTESTCD")["name"] == "first"


# ── _collect_item_placeholders ────────────────────────────────────────────────

class TestCollectItemPlaceholders:
    """_collect_item_placeholders(item, item_section) flags null/placeholder fields."""

    def test_null_length_is_collected(self, processor):
        item = {"OID": "IT.VS.VSORRES", "name": "VSORRES", "length": None}
        section = {}
        processor._collect_item_placeholders(item, section)
        assert "IT.VS.VSORRES" in section
        assert section["IT.VS.VSORRES"]["length"] is None

    def test_placeholder_origin_type_is_collected(self, processor):
        item = {"OID": "IT.VS.VSORRES", "origin": {"type": "__PLACEHOLDER__", "source": "Investigator"}}
        section = {}
        processor._collect_item_placeholders(item, section)
        assert "originType" in section.get("IT.VS.VSORRES", {})

    def test_placeholder_origin_source_is_collected(self, processor):
        item = {"OID": "IT.VS.VSORRES", "origin": {"type": "Collected", "source": "__PLACEHOLDER__"}}
        section = {}
        processor._collect_item_placeholders(item, section)
        assert "originSource" in section.get("IT.VS.VSORRES", {})

    def test_fully_valid_item_produces_no_entry(self, processor):
        item = {"OID": "IT.VS.VSTESTCD", "length": 8, "origin": {"type": "Collected", "source": "Investigator"}}
        section = {}
        processor._collect_item_placeholders(item, section)
        assert "IT.VS.VSTESTCD" not in section

    def test_missing_length_key_treated_same_as_null(self, processor):
        # item.get('length') returns None when the key is absent
        item = {"OID": "IT.VS.AESTDTC", "name": "AESTDTC"}
        section = {}
        processor._collect_item_placeholders(item, section)
        assert "IT.VS.AESTDTC" in section
        assert "length" in section["IT.VS.AESTDTC"]

    def test_only_length_placeholder_not_origin_when_origin_valid(self, processor):
        item = {"OID": "IT.VS.VSORRES", "length": None, "origin": {"type": "Collected", "source": "Investigator"}}
        section = {}
        processor._collect_item_placeholders(item, section)
        patches = section.get("IT.VS.VSORRES", {})
        assert "length" in patches
        assert "originType" not in patches
        assert "originSource" not in patches


# ── _apply_item_patch ─────────────────────────────────────────────────────────

class TestApplyItemPatch:
    """_apply_item_patch(item, item_patches) updates item in-place."""

    def test_applies_integer_length(self, processor):
        item = {"OID": "IT.VS.VSORRES", "length": None}
        processor._apply_item_patch(item, {"IT.VS.VSORRES": {"length": 20}})
        assert item["length"] == 20

    def test_null_length_in_patch_leaves_item_unchanged(self, processor):
        item = {"OID": "IT.VS.VSORRES", "length": None}
        processor._apply_item_patch(item, {"IT.VS.VSORRES": {"length": None}})
        assert item["length"] is None

    def test_applies_origin_type_and_source(self, processor):
        item = {"OID": "IT.VS.VSORRES", "origin": {"type": "__PLACEHOLDER__", "source": "__PLACEHOLDER__"}}
        processor._apply_item_patch(item, {"IT.VS.VSORRES": {"originType": "Collected", "originSource": "Investigator"}})
        assert item["origin"]["type"] == "Collected"
        assert item["origin"]["source"] == "Investigator"

    def test_placeholder_origin_type_in_patch_leaves_item_unchanged(self, processor):
        item = {"OID": "IT.VS.VSORRES", "origin": {"type": "__PLACEHOLDER__"}}
        processor._apply_item_patch(item, {"IT.VS.VSORRES": {"originType": "__PLACEHOLDER__"}})
        assert item["origin"]["type"] == "__PLACEHOLDER__"

    def test_creates_origin_dict_if_not_present(self, processor):
        item = {"OID": "IT.VS.VSORRES"}
        processor._apply_item_patch(item, {"IT.VS.VSORRES": {"originType": "Collected"}})
        assert item["origin"]["type"] == "Collected"

    def test_oid_absent_from_patches_leaves_item_unchanged(self, processor):
        item = {"OID": "IT.VS.VSORRES", "length": None}
        processor._apply_item_patch(item, {"IT.DM.USUBJID": {"length": 10}})
        assert item["length"] is None


# ── add_standards ─────────────────────────────────────────────────────────────

class TestAddStandards:
    """add_standards() writes SDTMIG and SDTMCT entries to template['standards']."""

    def test_exactly_two_standards_added(self, processor):
        processor.add_standards()
        assert len(processor.template["standards"]) == 2

    def test_sdtmig_oid_present(self, processor):
        processor.add_standards()
        oids = [s["OID"] for s in processor.template["standards"]]
        assert "STD.SDTMIG" in oids

    def test_sdtmig_version_matches_init_param(self, processor):
        processor.add_standards()
        entry = next(s for s in processor.template["standards"] if s["OID"] == "STD.SDTMIG")
        assert entry["version"] == "3.4"

    def test_sdtmig_type_is_ig(self, processor):
        processor.add_standards()
        entry = next(s for s in processor.template["standards"] if s["OID"] == "STD.SDTMIG")
        assert entry["type"] == "IG"

    def test_sdtmct_oid_present(self, processor):
        processor.add_standards()
        oids = [s["OID"] for s in processor.template["standards"]]
        assert "STD.SDTMCT" in oids

    def test_sdtmct_version_matches_init_param(self, processor):
        processor.add_standards()
        entry = next(s for s in processor.template["standards"] if s["OID"] == "STD.SDTMCT")
        assert entry["version"] == "2025-03-28"

    def test_sdtmct_publishing_set_is_sdtm(self, processor):
        processor.add_standards()
        entry = next(s for s in processor.template["standards"] if s["OID"] == "STD.SDTMCT")
        assert entry["publishingSet"] == "SDTM"


# ── populate_study_elements ───────────────────────────────────────────────────

class TestPopulateStudyElements:
    """populate_study_elements() reads USDM titles and populates template header fields."""

    def _set_titles(self, processor, acronym="MYSTUDY", official="A Study"):
        processor.usdm_data["study"]["versions"][0]["titles"] = [
            {"type": {"decode": "Study Acronym"}, "text": acronym},
            {"type": {"decode": "Official Study Title"}, "text": official},
        ]

    def test_study_name_from_acronym_title(self, processor):
        self._set_titles(processor, acronym="LZZT")
        processor.populate_study_elements()
        assert processor.template["studyName"] == "LZZT"

    def test_study_description_from_official_title(self, processor):
        self._set_titles(processor, official="A Phase III Study of LZZT")
        processor.populate_study_elements()
        assert processor.template["studyDescription"] == "A Phase III Study of LZZT"

    def test_file_oid_contains_study_name(self, processor):
        self._set_titles(processor, acronym="LZZT")
        processor.populate_study_elements()
        assert "LZZT" in processor.template["fileOID"]

    def test_study_oid_contains_study_name(self, processor):
        self._set_titles(processor, acronym="LZZT")
        processor.populate_study_elements()
        assert "LZZT" in processor.template["studyOID"]

    def test_mdv_oid_contains_study_name(self, processor):
        self._set_titles(processor, acronym="LZZT")
        processor.populate_study_elements()
        assert "LZZT" in processor.template["OID"]

    def test_protocol_name_equals_study_name(self, processor):
        self._set_titles(processor, acronym="LZZT")
        processor.populate_study_elements()
        assert processor.template["protocolName"] == processor.template["studyName"]

    def test_creation_datetime_is_populated(self, processor):
        processor.populate_study_elements()
        assert processor.template["creationDateTime"] != ""

    def test_study_version_zero_produces_version1_in_oid(self, processor):
        # studyversion=0 → Version1 in OID (1-indexed for display)
        self._set_titles(processor, acronym="LZZT")
        processor.populate_study_elements()
        assert "Version1" in processor.template["fileOID"]


# ── _get_or_create_condition_from_vlm / _create_where_clause_for_variable ────

class TestConditionAndWhereClauseCreation:
    """Condition deduplication and where-clause OID generation."""

    def _wc_data(self, variable="VSTESTCD", value="SYSBP"):
        return [{"Clause": [{"Dataset": "VS", "Variable": variable,
                              "item": f"IT.VS.{variable}", "Comparator": "EQ", "Values": [value]}]}]

    def test_creates_one_condition(self, processor):
        processor._get_or_create_condition_from_vlm(self._wc_data(), "VS", "VSORRES")
        assert len(processor.conditions) == 1

    def test_condition_oid_starts_with_cond_dataset(self, processor):
        processor._get_or_create_condition_from_vlm(self._wc_data(), "VS", "VSORRES")
        assert processor.conditions[0]["OID"].startswith("COND.VS.")

    def test_condition_contains_range_checks(self, processor):
        processor._get_or_create_condition_from_vlm(self._wc_data(), "VS", "VSORRES")
        rc = processor.conditions[0]["rangeChecks"][0]
        assert rc["comparator"] == "EQ"
        assert rc["checkValues"] == ["SYSBP"]

    def test_identical_where_clauses_deduplicated(self, processor):
        wc = self._wc_data()
        r1 = processor._get_or_create_condition_from_vlm(wc, "VS", "VSORRES")
        r2 = processor._get_or_create_condition_from_vlm(wc, "VS", "VSORRES")
        assert len(processor.conditions) == 1
        assert r1[0][0] == r2[0][0]

    def test_different_values_create_separate_conditions(self, processor):
        processor._get_or_create_condition_from_vlm(self._wc_data(value="SYSBP"), "VS", "VSORRES")
        processor._get_or_create_condition_from_vlm(self._wc_data(value="DIABP"), "VS", "VSORRES")
        assert len(processor.conditions) == 2

    def test_create_where_clause_returns_wc_oid(self, processor):
        oid = processor._create_where_clause_for_variable("VS", "VSORRES", ["COND.VS.VSTESTCD.abc12345"])
        assert oid.startswith("WC.VS.")

    def test_create_where_clause_appended_to_list(self, processor):
        oid = processor._create_where_clause_for_variable("VS", "VSORRES", ["COND.VS.VSTESTCD.abc12345"])
        assert len(processor.where_clauses) == 1
        assert processor.where_clauses[0]["OID"] == oid
        assert "COND.VS.VSTESTCD.abc12345" in processor.where_clauses[0]["conditions"]

    def test_where_clause_oid_deterministic_for_same_inputs(self, processor):
        oid1 = processor._create_where_clause_for_variable("VS", "VSORRES", ["COND.VS.abc"])
        oid2 = processor._create_where_clause_for_variable("VS", "VSORRES", ["COND.VS.abc"])
        assert oid1 == oid2


# ── build_vlm_lookup ──────────────────────────────────────────────────────────

class TestBuildVlmLookup:
    """build_vlm_lookup() aggregates bc_dict and generates TSPARMCD/IEORRES entries."""

    def _tsparmcd_values(self, processor):
        return {
            clause["Values"][0]
            for entry in processor.vlm_lookup.get("TSPARMCD", [])
            for wc in entry.get("WhereClause", [])
            for clause in wc.get("Clause", [])
            if clause.get("Values")
        }

    def test_aggregates_vlm_entries_from_bc_dict(self, processor):
        processor.bc_dict = {
            "BC001": [{"VSORRES": {"dataType": "text", "WhereClause": [], "codelist": {}}}]
        }
        processor.build_vlm_lookup()
        assert "VSORRES" in processor.vlm_lookup

    def test_tsparmcd_key_always_created(self, processor):
        processor.bc_dict = {}
        processor.build_vlm_lookup()
        assert "TSPARMCD" in processor.vlm_lookup

    def test_identical_bc_dict_entries_deduplicated(self, processor):
        entry = {"dataType": "text", "WhereClause": [], "codelist": {}}
        processor.bc_dict = {
            "BC001": [{"VSORRES": entry}],
            "BC002": [{"VSORRES": entry}],
        }
        processor.build_vlm_lookup()
        assert processor.vlm_lookup["VSORRES"].count(entry) == 1

    def test_adapt_added_when_c98704_characteristic_present(self, processor):
        processor.bc_dict = {}
        processor.studyDesignData["characteristics"] = [{"code": "C98704"}]
        processor.build_vlm_lookup()
        assert "ADAPT" in self._tsparmcd_values(processor)

    def test_adapt_not_added_when_c98704_absent(self, processor):
        processor.bc_dict = {}
        processor.studyDesignData["characteristics"] = []
        processor.build_vlm_lookup()
        assert "ADAPT" not in self._tsparmcd_values(processor)

    def test_narms_added_when_arms_present(self, processor):
        processor.bc_dict = {}
        processor.studyDesignData["arms"] = [{"name": "Arm A"}]
        processor.build_vlm_lookup()
        assert "NARMS" in self._tsparmcd_values(processor)

    def test_narms_not_added_when_no_arms(self, processor):
        processor.bc_dict = {}
        processor.studyDesignData["arms"] = []
        processor.build_vlm_lookup()
        assert "NARMS" not in self._tsparmcd_values(processor)

    def test_stype_added_when_study_type_decode_populated(self, processor):
        processor.bc_dict = {}
        processor.studyDesignData["studyType"] = {"code": "C98388", "decode": "Interventional"}
        processor.build_vlm_lookup()
        assert "STYPE" in self._tsparmcd_values(processor)

    def test_stype_not_added_when_decode_is_empty(self, processor):
        processor.bc_dict = {}
        processor.studyDesignData["studyType"] = {"code": "C98388", "decode": ""}
        processor.build_vlm_lookup()
        assert "STYPE" not in self._tsparmcd_values(processor)

    def test_objprim_added_when_primary_objective_present(self, processor):
        processor.bc_dict = {}
        processor.studyDesignData["objectives"] = [{"level": {"code": "C85826"}, "endpoints": []}]
        processor.build_vlm_lookup()
        assert "OBJPRIM" in self._tsparmcd_values(processor)

    def test_objsec_added_when_secondary_objective_present(self, processor):
        processor.bc_dict = {}
        processor.studyDesignData["objectives"] = [{"level": {"code": "C85827"}, "endpoints": []}]
        processor.build_vlm_lookup()
        assert "OBJSEC" in self._tsparmcd_values(processor)

    def test_tblind_added_when_blinding_schema_decode_set(self, processor):
        processor.bc_dict = {}
        processor.studyDesignData["blindingSchema"] = {"standardCode": {"decode": "Double Blind"}}
        processor.build_vlm_lookup()
        assert "TBLIND" in self._tsparmcd_values(processor)

    def test_tphase_added_when_study_phase_decode_set(self, processor):
        processor.bc_dict = {}
        processor.studyDesignData["studyPhase"] = {"standardCode": {"decode": "Phase III"}}
        processor.build_vlm_lookup()
        assert "TPHASE" in self._tsparmcd_values(processor)

    def test_hltsubji_added_when_population_includes_healthy_subjects(self, processor):
        processor.bc_dict = {}
        processor.studyDesignData["population"] = {"includesHealthySubjects": True, "cohorts": [], "plannedSex": []}
        processor.build_vlm_lookup()
        assert "HLTSUBJI" in self._tsparmcd_values(processor)

    def test_rdind_added_when_indication_is_rare_disease(self, processor):
        processor.bc_dict = {}
        processor.studyDesignData["indications"] = [{"isRareDisease": True}]
        processor.build_vlm_lookup()
        assert "RDIND" in self._tsparmcd_values(processor)

    def test_ieorres_entry_added_per_eligibility_criterion(self, processor):
        processor.bc_dict = {}
        processor.studyDesignData["eligibilityCriteria"] = [
            {"name": "IN01", "label": "Age >= 18", "category": {"decode": "Inclusion"}},
            {"name": "IN02", "label": "No prior treatment", "category": {"decode": "Inclusion"}},
        ]
        processor.build_vlm_lookup()
        assert "IEORRES" in processor.vlm_lookup
        assert len(processor.vlm_lookup["IEORRES"]) == 2

    def test_ieorres_where_clause_uses_criterion_name_as_value(self, processor):
        processor.bc_dict = {}
        processor.studyDesignData["eligibilityCriteria"] = [
            {"name": "EX01", "label": "Prior cancer", "category": {"decode": "Exclusion"}}
        ]
        processor.build_vlm_lookup()
        clause = processor.vlm_lookup["IEORRES"][0]["WhereClause"][0]["Clause"][0]
        assert clause["Values"] == ["EX01"]
        assert clause["Variable"] == "IETESTCD"

    def test_therarea_added_when_therapeutic_area_decode_set(self, processor):
        processor.bc_dict = {}
        processor.studyDesignData["therapeuticAreas"] = [{"decode": "Oncology"}]
        processor.build_vlm_lookup()
        assert "THERAREA" in self._tsparmcd_values(processor)

    def test_plansub_added_when_planned_enrollment_number_set(self, processor):
        processor.bc_dict = {}
        processor.studyDesignData["population"] = {
            "plannedEnrollmentNumber": {"value": 200},
            "cohorts": [], "plannedSex": []
        }
        processor.build_vlm_lookup()
        assert "PLANSUB" in self._tsparmcd_values(processor)
