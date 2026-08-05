"""
Tests for methods that call the CDISC Library API.

All network calls are intercepted via mock_client.  Tests configure
mock_client.<method>.return_value (or .side_effect) before exercising the
method under test.  The processor fixture ensures proc.client IS mock_client.
"""

import pytest


# ── Shared mock data ──────────────────────────────────────────────────────────

MOCK_VS_DATASET = {
    "label": "Vital Signs",
    "datasetStructure": "One record per visit per vital signs test",
    "_links": {"parentClass": {"title": "Findings"}},
    "datasetVariables": [
        {
            "name": "STUDYID", "label": "Study Identifier",
            "core": "Req", "role": "Identifier", "simpleDatatype": "Char", "_links": {},
        },
        {
            "name": "USUBJID", "label": "Unique Subject Identifier",
            "core": "Req", "role": "Identifier", "simpleDatatype": "Char", "_links": {},
        },
        {
            "name": "VSTESTCD", "label": "Vital Signs Test Short Name",
            "core": "Req", "role": "Topic", "simpleDatatype": "Char",
            "_links": {"codelist": [{"href": "/mdr/ct/packages/sdtmct-2025-03-28/codelists/C96664"}]},
        },
        {
            "name": "VSORRES", "label": "Result or Finding in Original Units",
            "core": "Exp", "role": "Result", "simpleDatatype": "Char", "_links": {},
        },
        {
            "name": "VSSEQ", "label": "Sequence Number",
            "core": "Req", "role": "Identifier", "simpleDatatype": "Num", "_links": {},
        },
    ],
}

MOCK_VS_CODELIST = {
    "conceptId": "C96664",
    "name": "VS Test Code",
    "submissionValue": "VSTESTCD",
    "terms": [
        {"conceptId": "C49670", "submissionValue": "SYSBP",  "synonyms": ["Systolic Blood Pressure"]},
        {"conceptId": "C49671", "submissionValue": "DIABP",  "synonyms": ["Diastolic Blood Pressure"]},
        {"conceptId": "C49673", "submissionValue": "PULSE",  "synonyms": ["Pulse Rate"]},
    ],
}

MOCK_TRIAL_DESIGN_DATASET = {
    "label": "Trial Arms",
    "datasetStructure": "One record per arm and per element",
    "_links": {"parentClass": {"title": "Trial Design"}},
    "datasetVariables": [
        {"name": "STUDYID", "label": "Study Identifier", "core": "Req", "role": "Identifier", "simpleDatatype": "Char", "_links": {}},
        {"name": "ARMCD",   "label": "Planned Arm Code",   "core": "Req", "role": "Identifier", "simpleDatatype": "Char", "_links": {}},
    ],
}


# ── _process_variables ────────────────────────────────────────────────────────

class TestProcessVariables:
    """_process_variables(variables, dataset_name, bc)."""

    def _bc(self, bc_id="BC001"):
        return {"id": bc_id, "properties": []}

    def test_creates_dataset_and_variable_entry(self, processor):
        processor._process_variables(
            [{"name": "VSTESTCD", "dataElementConceptId": "C96664", "role": "Topic"}],
            "VS", self._bc(),
        )
        assert "VS" in processor.datasets_dict
        assert "VSTESTCD" in processor.datasets_dict["VS"]

    def test_variable_without_data_element_concept_id_is_skipped(self, processor):
        # _process_variables always seeds datasets_dict[dataset_name] = {} before
        # iterating variables, so the dataset key exists even when no variable passes
        # the dataElementConceptId guard — only the variable entry is absent.
        processor._process_variables([{"name": "VSTESTCD"}], "VS", self._bc())
        assert "VS" in processor.datasets_dict
        assert "VSTESTCD" not in processor.datasets_dict["VS"]

    def test_existing_variable_entry_not_overwritten(self, processor):
        processor.datasets_dict["VS"] = {"VSTESTCD": {"role": "OriginalRole"}}
        processor._process_variables(
            [{"name": "VSTESTCD", "dataElementConceptId": "C96664", "role": "NewRole"}],
            "VS", self._bc(),
        )
        assert processor.datasets_dict["VS"]["VSTESTCD"]["role"] == "OriginalRole"

    def test_optional_fields_stored_when_present(self, processor):
        variables = [{
            "name": "VSORRES", "dataElementConceptId": "C70856",
            "role": "Result", "dataType": "text", "length": 200,
            "originType": "Collected", "originSource": "Investigator",
        }]
        processor._process_variables(variables, "VS", self._bc())
        var_data = processor.datasets_dict["VS"]["VSORRES"]
        assert var_data["role"] == "Result"
        assert var_data["length"] == 200

    def test_codelist_populated_when_response_codes_match(self, processor, mock_client):
        mock_client.get_codelist_terms.return_value = [
            {"conceptId": "C49670", "submissionValue": "SYSBP"},
        ]
        bc = {
            "id": "BC001",
            "properties": [{
                "code": {"standardCode": {"code": "C96664"}},
                "responseCodes": [{"code": {"code": "C49670"}}],
            }],
        }
        variables = [{"name": "VSTESTCD", "dataElementConceptId": "C96664",
                      "codelist": {"conceptId": "C96664", "submissionValue": "VSTESTCD"}, "vlmTarget": False}]
        processor._process_variables(variables, "VS", bc)
        terms = processor.datasets_dict["VS"]["VSTESTCD"]["codelist"]["C96664"]["terms"]
        assert "SYSBP" in terms

    def test_vlm_target_variables_skipped_for_response_code_lookup(self, processor, mock_client):
        bc = {
            "id": "BC001",
            "properties": [{"code": {"standardCode": {"code": "C96664"}}, "responseCodes": []}],
        }
        variables = [{"name": "VSORRES", "dataElementConceptId": "C96664",
                      "codelist": {"conceptId": "C96664", "submissionValue": "VSTESTCD"}, "vlmTarget": True}]
        processor._process_variables(variables, "VS", bc)
        assert "VSORRES" in processor.datasets_dict["VS"]
        assert "codelist" not in processor.datasets_dict["VS"]["VSORRES"]
        mock_client.get_codelist_terms.assert_not_called()

    def test_terms_merged_across_multiple_bc_calls_for_same_variable(self, processor, mock_client):
        mock_client.get_codelist_terms.return_value = [
            {"conceptId": "C49670", "submissionValue": "SYSBP"},
            {"conceptId": "C49671", "submissionValue": "DIABP"},
        ]
        variables = [{"name": "VSTESTCD", "dataElementConceptId": "C96664",
                      "codelist": {"conceptId": "C96664", "submissionValue": "VSTESTCD"}, "vlmTarget": False}]
        bc1 = {"id": "BC001", "properties": [{"code": {"standardCode": {"code": "C96664"}},
                                               "responseCodes": [{"code": {"code": "C49670"}}]}]}
        bc2 = {"id": "BC002", "properties": [{"code": {"standardCode": {"code": "C96664"}},
                                               "responseCodes": [{"code": {"code": "C49671"}}]}]}
        processor._process_variables(variables, "VS", bc1)
        processor._process_variables(variables, "VS", bc2)
        terms = processor.datasets_dict["VS"]["VSTESTCD"]["codelist"]["C96664"]["terms"]
        assert "SYSBP" in terms
        assert "DIABP" in terms


# ── _build_where_clause ───────────────────────────────────────────────────────

class TestBuildWhereClause:
    """_build_where_clause(bc, bc_data, dss_response, dataset_name)."""

    def test_empty_list_when_no_variable_has_comparator(self, processor):
        bc = {"id": "BC001", "properties": [{"name": "VSTESTCD", "responseCodes": []}]}
        bc_data = {"variables": [{"name": "VSTESTCD"}]}  # no 'comparator' key
        assert processor._build_where_clause(bc, bc_data, {"variables": []}, "VS") == []

    def test_builds_clause_item_with_response_code_values(self, processor, mock_client):
        mock_client.get_codelist_terms.return_value = [
            {"conceptId": "C49670_SYSBP", "submissionValue": "SYSBP"}
        ]
        bc = {"id": "BC001", "properties": [
            {"name": "VSTESTCD", "responseCodes": [{"code": {"code": "C49670_SYSBP"}}]}
        ]}
        bc_data = {"variables": [{"name": "VSTESTCD", "comparator": "EQ", "codelist": {"conceptId": "C96664"}}]}
        result = processor._build_where_clause(bc, bc_data, {"variables": []}, "VS")
        assert len(result) == 1
        clause_item = result[0]["Clause"][0]
        assert clause_item["Comparator"] == "EQ"
        assert "SYSBP" in clause_item["Values"]
        assert clause_item["Dataset"] == "VS"
        assert clause_item["item"] == "IT.VS.VSTESTCD"

    def test_falls_back_to_assigned_term_when_no_response_codes_match(self, processor, mock_client):
        mock_client.get_codelist_terms.return_value = []
        bc = {"id": "BC001", "properties": [{"name": "VSTESTCD", "responseCodes": []}]}
        bc_data = {"variables": [{"name": "VSTESTCD", "comparator": "EQ", "codelist": {"conceptId": "C96664"}}]}
        dss_response = {"variables": [{"name": "VSTESTCD", "assignedTerm": {"conceptId": "C12345", "value": "SYSBP"}}]}
        result = processor._build_where_clause(bc, bc_data, dss_response, "VS")
        assert "SYSBP" in result[0]["Clause"][0]["Values"]

    def test_falls_back_to_value_list_when_no_assigned_term(self, processor, mock_client):
        mock_client.get_codelist_terms.return_value = []
        bc = {"id": "BC001", "properties": [{"name": "VSTESTCD", "responseCodes": []}]}
        bc_data = {"variables": [{"name": "VSTESTCD", "comparator": "IN", "codelist": {"conceptId": "C96664"}}]}
        dss_response = {"variables": [{"name": "VSTESTCD", "valueList": ["SYSBP", "DIABP"]}]}
        result = processor._build_where_clause(bc, bc_data, dss_response, "VS")
        values = result[0]["Clause"][0]["Values"]
        assert "SYSBP" in values and "DIABP" in values

    def test_multiple_comparator_variables_combined_into_single_where_clause(self, processor, mock_client):
        mock_client.get_codelist_terms.return_value = [{"conceptId": "X1", "submissionValue": "VAL1"}]
        bc = {"id": "BC001", "properties": [
            {"name": "VSTESTCD", "responseCodes": [{"code": {"code": "X1"}}]},
            {"name": "VSPOS",   "responseCodes": [{"code": {"code": "X1"}}]},
        ]}
        bc_data = {"variables": [
            {"name": "VSTESTCD", "comparator": "EQ", "codelist": {"conceptId": "C96664"}},
            {"name": "VSPOS",   "comparator": "EQ", "codelist": {"conceptId": "C96665"}},
        ]}
        result = processor._build_where_clause(bc, bc_data, {"variables": []}, "VS")
        assert len(result) == 1
        assert len(result[0]["Clause"]) == 2  # implicit AND


# ── _process_variable_codelist ────────────────────────────────────────────────

class TestProcessVariableCodelist:
    """_process_variable_codelist(var, dataset, restriction_codes=None)."""

    def test_returns_none_when_var_has_no_codelist_link(self, processor):
        assert processor._process_variable_codelist({"name": "STUDYID", "_links": {}}, "VS") is None

    def test_returns_none_when_href_is_null(self, processor, mock_client):
        var = {"name": "VSTESTCD", "_links": {"codelist": [{"href": None}]}}
        assert processor._process_variable_codelist(var, "VS") is None
        mock_client.get_api_json.assert_not_called()

    def test_returns_codelist_oid(self, processor, mock_client):
        mock_client.get_api_json.return_value = MOCK_VS_CODELIST
        processor.global_codelist_terms = {}
        var = {"name": "VSTESTCD", "_links": {"codelist": [{"href": "/mdr/ct/packages/sdtmct-2025-03-28/codelists/C96664"}]}}
        assert processor._process_variable_codelist(var, "VS") == "CL.VSTESTCD"

    def test_codelist_added_to_code_lists_map(self, processor, mock_client):
        mock_client.get_api_json.return_value = MOCK_VS_CODELIST
        processor.global_codelist_terms = {}
        var = {"name": "VSTESTCD", "_links": {"codelist": [{"href": "/mdr/ct/packages/sdtmct-2025-03-28/codelists/C96664"}]}}
        processor._process_variable_codelist(var, "VS")
        assert "VSTESTCD" in processor.code_lists_map

    def test_restriction_filters_to_specified_terms(self, processor, mock_client):
        mock_client.get_api_json.return_value = MOCK_VS_CODELIST
        processor.global_codelist_terms = {}
        var = {"name": "VSTESTCD", "_links": {"codelist": [{"href": "/mdr/ct/packages/sdtmct-2025-03-28/codelists/C96664"}]}}
        restriction_codes = {"C96664": {"codelist_concept_id": "C96664", "terms": ["SYSBP"]}}
        processor._process_variable_codelist(var, "VS", restriction_codes)
        coded_values = [i["codedValue"] for i in processor.code_lists_map["VSTESTCD"]["codeListItems"]]
        assert "SYSBP" in coded_values
        assert "DIABP" not in coded_values

    def test_empty_restriction_list_falls_back_to_global_terms(self, processor, mock_client):
        mock_client.get_api_json.return_value = MOCK_VS_CODELIST
        processor.global_codelist_terms = {"C96664": {"SYSBP", "PULSE"}}
        var = {"name": "VSTESTCD", "_links": {"codelist": [{"href": "/mdr/ct/packages/sdtmct-2025-03-28/codelists/C96664"}]}}
        restriction_codes = {"C96664": {"codelist_concept_id": "C96664", "terms": []}}
        processor._process_variable_codelist(var, "VS", restriction_codes)
        coded_values = {i["codedValue"] for i in processor.code_lists_map["VSTESTCD"]["codeListItems"]}
        assert coded_values == {"SYSBP", "PULSE"}

    def test_empty_restriction_and_no_global_terms_produces_placeholder(self, processor, mock_client):
        mock_client.get_api_json.return_value = MOCK_VS_CODELIST
        processor.global_codelist_terms = {}
        var = {"name": "VSTESTCD", "_links": {"codelist": [{"href": "/mdr/ct/packages/sdtmct-2025-03-28/codelists/C96664"}]}}
        restriction_codes = {"C96664": {"codelist_concept_id": "C96664", "terms": []}}
        processor._process_variable_codelist(var, "VS", restriction_codes)
        coded_values = [i["codedValue"] for i in processor.code_lists_map["VSTESTCD"]["codeListItems"]]
        assert "__PLACEHOLDER__" in coded_values

    def test_no_restriction_and_no_global_terms_produces_placeholder(self, processor, mock_client):
        mock_client.get_api_json.return_value = MOCK_VS_CODELIST
        processor.global_codelist_terms = {}
        var = {"name": "VSTESTCD", "_links": {"codelist": [{"href": "/mdr/ct/packages/sdtmct-2025-03-28/codelists/C96664"}]}}
        processor._process_variable_codelist(var, "VS")
        coded_values = [i["codedValue"] for i in processor.code_lists_map["VSTESTCD"]["codeListItems"]]
        assert "__PLACEHOLDER__" in coded_values

    def test_subsequent_calls_do_not_duplicate_terms(self, processor, mock_client):
        mock_client.get_api_json.return_value = MOCK_VS_CODELIST
        processor.global_codelist_terms = {}
        var = {"name": "VSTESTCD", "_links": {"codelist": [{"href": "/mdr/ct/packages/sdtmct-2025-03-28/codelists/C96664"}]}}
        restriction_codes = {"C96664": {"codelist_concept_id": "C96664", "terms": ["SYSBP"]}}
        processor._process_variable_codelist(var, "VS", restriction_codes)
        processor._process_variable_codelist(var, "VS", restriction_codes)
        sysbp_count = sum(1 for i in processor.code_lists_map["VSTESTCD"]["codeListItems"] if i["codedValue"] == "SYSBP")
        assert sysbp_count == 1


# ── _process_vlm_codelist ─────────────────────────────────────────────────────

class TestProcessVlmCodelist:
    """_process_vlm_codelist(vlm_codelist)."""

    def test_returns_none_for_empty_dict(self, processor):
        assert processor._process_vlm_codelist({}) is None

    def test_returns_none_when_entry_has_no_codelist_concept_id(self, processor):
        assert processor._process_vlm_codelist({"key": {"codelist_name": "X", "terms": ["SYSBP"]}}) is None

    def test_returns_correct_oid(self, processor, mock_client):
        mock_client.get_api_json.return_value = MOCK_VS_CODELIST
        processor.global_codelist_terms = {}
        vlm_codelist = {"C96664": {"codelist_concept_id": "C96664", "codelist_name": "VS Test Code", "terms": ["SYSBP"]}}
        assert processor._process_vlm_codelist(vlm_codelist) == "CL.VSTESTCD"

    def test_uses_subset_codelist_name_as_short_name(self, processor, mock_client):
        mock_client.get_api_json.return_value = MOCK_VS_CODELIST
        processor.global_codelist_terms = {}
        vlm_codelist = {"C96664": {"codelist_concept_id": "C96664", "subsetCodelist": "VSTESTCD_VITALS", "terms": ["SYSBP"]}}
        result = processor._process_vlm_codelist(vlm_codelist)
        assert result == "CL.VSTESTCD_VITALS"
        assert "VSTESTCD_VITALS" in processor.code_lists_map

    def test_restriction_list_filters_terms(self, processor, mock_client):
        mock_client.get_api_json.return_value = MOCK_VS_CODELIST
        processor.global_codelist_terms = {}
        vlm_codelist = {"C96664": {"codelist_concept_id": "C96664", "terms": ["SYSBP"]}}
        processor._process_vlm_codelist(vlm_codelist)
        coded_values = [i["codedValue"] for i in processor.code_lists_map["VSTESTCD"]["codeListItems"]]
        assert "SYSBP" in coded_values
        assert "DIABP" not in coded_values


# ── _process_standard_dataset ─────────────────────────────────────────────────

class TestProcessStandardDataset:
    """_process_standard_dataset(dataset, dataset_data)."""

    def test_item_group_appended_to_item_groups_list(self, processor):
        processor.datasets_dict = {"VS": {}}
        processor.global_codelist_terms = {}
        processor._process_standard_dataset("VS", MOCK_VS_DATASET)
        assert len(processor.item_groups) == 1
        assert processor.item_groups[0]["OID"] == "IG.VS"

    def test_item_group_carries_correct_metadata(self, processor):
        processor.datasets_dict = {"VS": {}}
        processor.global_codelist_terms = {}
        processor._process_standard_dataset("VS", MOCK_VS_DATASET)
        ig = processor.item_groups[0]
        assert ig["name"] == "VS"
        assert ig["description"] == "Vital Signs"
        assert ig["purpose"] == "Tabulation"
        assert ig["standard"] == "STD.SDTMIG"

    def test_req_variables_always_included(self, processor):
        processor.datasets_dict = {"VS": {}}
        processor.global_codelist_terms = {}
        processor._process_standard_dataset("VS", MOCK_VS_DATASET)
        names = [i["name"] for i in processor.item_groups[0]["items"]]
        assert "STUDYID" in names
        assert "USUBJID" in names
        assert "VSSEQ" in names

    def test_exp_variables_always_included(self, processor):
        processor.datasets_dict = {"VS": {}}
        processor.global_codelist_terms = {}
        processor._process_standard_dataset("VS", MOCK_VS_DATASET)
        names = [i["name"] for i in processor.item_groups[0]["items"]]
        assert "VSORRES" in names

    def test_mandatory_true_for_req_variable(self, processor):
        processor.datasets_dict = {"VS": {}}
        processor.global_codelist_terms = {}
        processor._process_standard_dataset("VS", MOCK_VS_DATASET)
        studyid = next(i for i in processor.item_groups[0]["items"] if i["name"] == "STUDYID")
        assert studyid["mandatory"] is True

    def test_mandatory_false_for_exp_variable(self, processor):
        processor.datasets_dict = {"VS": {}}
        processor.global_codelist_terms = {}
        processor._process_standard_dataset("VS", MOCK_VS_DATASET)
        vsorres = next(i for i in processor.item_groups[0]["items"] if i["name"] == "VSORRES")
        assert vsorres["mandatory"] is False

    def test_is_reference_data_false_when_usubjid_present(self, processor):
        processor.datasets_dict = {"VS": {}}
        processor.global_codelist_terms = {}
        processor._process_standard_dataset("VS", MOCK_VS_DATASET)
        assert processor.item_groups[0]["isReferenceData"] is False

    def test_is_reference_data_true_for_trial_design_class(self, processor):
        processor.datasets_dict = {"TA": {}}
        processor.global_codelist_terms = {}
        processor._process_standard_dataset("TA", MOCK_TRIAL_DESIGN_DATASET)
        assert processor.item_groups[0]["isReferenceData"] is True

    def test_observation_class_from_parent_class_title(self, processor):
        processor.datasets_dict = {"VS": {}}
        processor.global_codelist_terms = {}
        processor._process_standard_dataset("VS", MOCK_VS_DATASET)
        assert processor.item_groups[0]["observationClass"]["name"] == "FINDINGS"

    def test_placeholder_origin_when_var_not_in_datasets_dict(self, processor):
        processor.datasets_dict = {"VS": {}}
        processor.global_codelist_terms = {}
        processor._process_standard_dataset("VS", MOCK_VS_DATASET)
        studyid = next(i for i in processor.item_groups[0]["items"] if i["name"] == "STUDYID")
        assert studyid["origin"]["type"] == "__PLACEHOLDER__"
        assert studyid["origin"]["source"] == "__PLACEHOLDER__"

    def test_origin_from_datasets_dict_when_present(self, processor):
        processor.datasets_dict = {"VS": {"VSTESTCD": {"originType": "Collected", "originSource": "Investigator"}}}
        processor.global_codelist_terms = {}
        processor._process_standard_dataset("VS", MOCK_VS_DATASET)
        vstestcd = next(i for i in processor.item_groups[0]["items"] if i["name"] == "VSTESTCD")
        assert vstestcd["origin"]["type"] == "Collected"
        assert vstestcd["origin"]["source"] == "Investigator"

    def test_dtc_variable_gets_datetime_type(self, processor):
        dataset = {
            "label": "Adverse Events",
            "datasetStructure": "One record per adverse event",
            "_links": {"parentClass": {"title": "Events"}},
            "datasetVariables": [
                {"name": "AESTDTC", "label": "Start Date/Time", "core": "Exp",
                 "role": "Timing", "simpleDatatype": "Char", "_links": {}},
            ],
        }
        processor.datasets_dict = {"AE": {}}
        processor.global_codelist_terms = {}
        processor._process_standard_dataset("AE", dataset)
        aestdtc = next(i for i in processor.item_groups[0]["items"] if i["name"] == "AESTDTC")
        assert aestdtc["dataType"] == "datetime"

    def test_vlm_slices_created_for_variable_in_vlm_lookup(self, processor):
        processor.datasets_dict = {"VS": {}}
        processor.global_codelist_terms = {}
        processor.vlm_lookup = {
            "VSTESTCD": [{
                "dataType": "text", "length": 8,
                "originType": "Collected", "originSource": "Investigator",
                "WhereClause": [{"Clause": [{
                    "Dataset": "VS", "Variable": "VSTESTCD",
                    "item": "IT.VS.VSTESTCD", "Comparator": "EQ", "Values": ["SYSBP"],
                }]}],
            }]
        }
        processor._process_standard_dataset("VS", MOCK_VS_DATASET)
        ig = processor.item_groups[0]
        assert "slices" in ig
        assert ig["slices"][0]["OID"] == "VL.VS.VSTESTCD"
        assert ig["slices"][0]["wasDerivedFrom"] == "IT.VS.VSTESTCD"

    def test_codelist_removed_from_parent_when_slice_has_codelist(self, processor, mock_client):
        mock_client.get_api_json.return_value = MOCK_VS_CODELIST
        processor.datasets_dict = {"VS": {"VSTESTCD": {}}}
        processor.global_codelist_terms = {"C96664": {"SYSBP"}}
        processor.vlm_lookup = {
            "VSTESTCD": [{
                "dataType": "text", "originType": "Collected", "originSource": "Investigator",
                "codelist": {"C96664": {"codelist_concept_id": "C96664", "codelist_name": "VS Test Code", "terms": ["SYSBP"]}},
                "WhereClause": [{"Clause": [{
                    "Dataset": "VS", "Variable": "VSTESTCD",
                    "item": "IT.VS.VSTESTCD", "Comparator": "EQ", "Values": ["SYSBP"],
                }]}],
            }]
        }
        processor._process_standard_dataset("VS", MOCK_VS_DATASET)
        vstestcd_parent = next(i for i in processor.item_groups[0]["items"] if i["name"] == "VSTESTCD")
        assert "codeList" not in vstestcd_parent

    def test_origin_removed_from_parent_when_slice_has_origin(self, processor):
        processor.datasets_dict = {"VS": {}}
        processor.global_codelist_terms = {}
        processor.vlm_lookup = {
            "VSTESTCD": [{
                "dataType": "text", "originType": "Collected", "originSource": "Investigator",
                "WhereClause": [{"Clause": [{
                    "Dataset": "VS", "Variable": "VSTESTCD",
                    "item": "IT.VS.VSTESTCD", "Comparator": "EQ", "Values": ["SYSBP"],
                }]}],
            }]
        }
        processor._process_standard_dataset("VS", MOCK_VS_DATASET)
        vstestcd_parent = next(i for i in processor.item_groups[0]["items"] if i["name"] == "VSTESTCD")
        assert "origin" not in vstestcd_parent


# ── _process_bc_type / _process_dss_type ─────────────────────────────────────

class TestProcessBcAndDssTypes:
    """_process_bc_type and _process_dss_type dispatch and population logic."""

    def test_bc_type_calls_dataset_specialization_api(self, processor, mock_client):
        bc = {"id": "BC001", "reference": "/biomedicalconcepts/C123", "properties": []}
        bc_data = {"conceptId": "C123"}
        mock_client.get_biomedicalconcept_latest_datasetspecializations.return_value = {"sdtm": []}
        processor._process_bc_type(bc, bc_data)
        mock_client.get_biomedicalconcept_latest_datasetspecializations.assert_called_once_with("v2", "C123")

    def test_bc_type_processes_variables_for_each_dataset_link(self, processor, mock_client):
        # all_dataset_data is initialised by process_biomedical_concepts(), not __init__
        processor.all_dataset_data = []
        bc = {"id": "BC001", "reference": "/biomedicalconcepts/C123", "properties": []}
        bc_data = {"conceptId": "C123"}
        mock_client.get_biomedicalconcept_latest_datasetspecializations.return_value = {
            "sdtm": [{"href": "/cosmos/v2/datasetspecializations/VS-SYSBP"}]
        }
        mock_client.get_sdtm_latest_sdtm_datasetspecialization.return_value = {
            "domain": "VS",
            "variables": [{"name": "VSTESTCD", "dataElementConceptId": "C96664"}],
        }
        processor._process_bc_type(bc, bc_data)
        assert "VS" in processor.datasets_dict
        assert "VSTESTCD" in processor.datasets_dict["VS"]

    def test_dss_type_calls_dataset_specialization_api(self, processor, mock_client):
        bc = {"id": "BC001", "reference": "/datasetspecializations/DS123", "properties": []}
        bc_data = {"datasetSpecializationId": "DS123", "variables": []}
        mock_client.get_sdtm_latest_sdtm_datasetspecialization.return_value = {"domain": "VS", "variables": []}
        processor._process_dss_type(bc, bc_data)
        mock_client.get_sdtm_latest_sdtm_datasetspecialization.assert_called_once_with("v2", "DS123")

    def test_dss_type_populates_datasets_dict(self, processor, mock_client):
        bc = {"id": "BC001", "reference": "/datasetspecializations/DS123", "properties": []}
        bc_data = {"datasetSpecializationId": "DS123", "variables": []}
        mock_client.get_sdtm_latest_sdtm_datasetspecialization.return_value = {
            "domain": "VS",
            "variables": [{"name": "VSTESTCD", "dataElementConceptId": "C96664"}],
        }
        processor._process_dss_type(bc, bc_data)
        assert "VS" in processor.datasets_dict


# ── process_biomedical_concepts ───────────────────────────────────────────────

class TestProcessBiomedicalConcepts:
    """process_biomedical_concepts() dispatches by concept type."""

    def test_empty_biomedical_concepts_is_a_no_op(self, processor):
        processor.study_version_data = {"biomedicalConcepts": []}
        processor.process_biomedical_concepts()
        assert processor.datasets_dict == {}

    def test_dispatches_to_bc_type_handler(self, processor, mock_client):
        processor.study_version_data = {
            "biomedicalConcepts": [{"id": "BC001", "reference": "/biomedicalconcepts/C123", "properties": []}]
        }
        mock_client.get_api_json.return_value = {
            "_links": {"self": {"type": "Biomedical Concept"}},
            "conceptId": "C123",
        }
        mock_client.get_biomedicalconcept_latest_datasetspecializations.return_value = {"sdtm": []}
        processor.process_biomedical_concepts()
        mock_client.get_biomedicalconcept_latest_datasetspecializations.assert_called_once()

    def test_dispatches_to_dss_type_handler(self, processor, mock_client):
        processor.study_version_data = {
            "biomedicalConcepts": [{"id": "BC001", "reference": "/datasetspecializations/DS123", "properties": []}]
        }
        mock_client.get_api_json.return_value = {
            "_links": {"self": {"type": "SDTM Dataset Specialization"}},
            "datasetSpecializationId": "DS123",
        }
        mock_client.get_sdtm_latest_sdtm_datasetspecialization.return_value = {"domain": "VS", "variables": []}
        processor.process_biomedical_concepts()
        mock_client.get_sdtm_latest_sdtm_datasetspecialization.assert_called_once()


# ── update_datasets_dict ──────────────────────────────────────────────────────

class TestUpdateDatasetsDictDomainSeeding:
    """update_datasets_dict() seeds domains and codelists from USDM design data."""

    def _api_side_effect(self, url):
        """Return minimal CT API responses keyed by codelist ID in the URL."""
        if "C66738" in url:  # TSPARMCD
            return {"terms": [{"conceptId": "C99078", "submissionValue": "STYPE"}]}
        if "C67152" in url:  # TSPARM
            return {"terms": [{"conceptId": "C99078", "submissionValue": "Study Type"}]}
        if "C171445" in url:  # CNTMODE
            return {"terms": [{"conceptId": "C123", "submissionValue": "On-site"}]}
        return {"terms": []}

    def test_ts_added_when_vlm_lookup_has_tsparmcd_entries(self, processor, mock_client):
        mock_client.get_api_json.side_effect = self._api_side_effect
        processor.vlm_lookup = {
            "TSPARMCD": [{"WhereClause": [{"Clause": [{"Values": ["STYPE"]}]}]}]
        }
        processor.update_datasets_dict()
        assert "TS" in processor.datasets_dict

    def test_tsparmcd_codelist_restricted_to_vlm_values(self, processor, mock_client):
        mock_client.get_api_json.side_effect = self._api_side_effect
        processor.vlm_lookup = {
            "TSPARMCD": [{"WhereClause": [{"Clause": [{"Values": ["STYPE"]}]}]}]
        }
        processor.update_datasets_dict()
        terms = processor.datasets_dict["TS"]["TSPARMCD"]["codelist"]["C66738"]["terms"]
        assert "STYPE" in terms

    def test_ta_added_when_arms_present(self, processor, mock_client):
        mock_client.get_api_json.side_effect = self._api_side_effect
        processor.vlm_lookup = {"TSPARMCD": []}
        processor.studyDesignData["arms"] = [{"name": "Arm A"}]
        processor.update_datasets_dict()
        assert "TA" in processor.datasets_dict

    def test_ta_not_added_when_no_arms(self, processor, mock_client):
        mock_client.get_api_json.side_effect = self._api_side_effect
        processor.vlm_lookup = {"TSPARMCD": []}
        processor.studyDesignData["arms"] = []
        processor.update_datasets_dict()
        assert "TA" not in processor.datasets_dict

    def test_epoch_codelist_added_to_ta_when_epochs_present(self, processor, mock_client):
        mock_client.get_api_json.side_effect = self._api_side_effect
        processor.vlm_lookup = {"TSPARMCD": []}
        processor.studyDesignData["arms"] = [{"name": "Arm A"}]
        processor.studyDesignData["epochs"] = [{"name": "Screening"}, {"name": "Treatment"}]
        processor.update_datasets_dict()
        assert "EPOCH" in processor.datasets_dict["TA"]
        terms = processor.datasets_dict["TA"]["EPOCH"]["codelist"]["C99079"]["terms"]
        assert "Screening" in terms and "Treatment" in terms

    def test_ie_and_tv_added_when_eligibility_criteria_present(self, processor, mock_client):
        mock_client.get_api_json.side_effect = self._api_side_effect
        processor.vlm_lookup = {"TSPARMCD": []}
        processor.studyDesignData["eligibilityCriteria"] = [
            {"name": "IN01", "label": "Age >= 18"}
        ]
        processor.update_datasets_dict()
        assert "IE" in processor.datasets_dict
        assert "TV" in processor.datasets_dict
        assert "TI" in processor.datasets_dict

    def test_sv_added_when_encounters_present(self, processor, mock_client):
        mock_client.get_api_json.side_effect = self._api_side_effect
        processor.vlm_lookup = {"TSPARMCD": []}
        processor.studyDesignData["encounters"] = [
            {"contactModes": [{"code": "C123"}]}
        ]
        processor.update_datasets_dict()
        assert "SV" in processor.datasets_dict

    def test_svcntmod_codelist_built_from_encounter_contact_modes(self, processor, mock_client):
        mock_client.get_api_json.side_effect = self._api_side_effect
        processor.vlm_lookup = {"TSPARMCD": []}
        processor.studyDesignData["encounters"] = [{"contactModes": [{"code": "C123"}]}]
        processor.update_datasets_dict()
        assert "SVCNTMOD" in processor.datasets_dict["SV"]
        terms = processor.datasets_dict["SV"]["SVCNTMOD"]["codelist"]["C171445"]["terms"]
        assert "On-site" in terms

    def test_armcd_codelist_created_from_arms(self, processor, mock_client):
        mock_client.get_api_json.side_effect = self._api_side_effect
        processor.vlm_lookup = {"TSPARMCD": []}
        processor.studyDesignData["arms"] = [{"name": "Placebo"}, {"name": "Drug 5mg"}]
        processor.update_datasets_dict()
        assert "ARMCD" in processor.code_lists_map
        coded_values = [i["codedValue"] for i in processor.code_lists_map["ARMCD"]["codeListItems"]]
        assert "Placebo" in coded_values and "Drug 5mg" in coded_values

    def test_ietestcd_codelist_created_from_eligibility_criteria(self, processor, mock_client):
        mock_client.get_api_json.side_effect = self._api_side_effect
        processor.vlm_lookup = {"TSPARMCD": []}
        processor.studyDesignData["eligibilityCriteria"] = [
            {"name": "IN01", "label": "Age >= 18"},
            {"name": "EX01", "label": "Prior cancer"},
        ]
        processor.update_datasets_dict()
        assert "IETESTCD" in processor.code_lists_map
        coded_values = [i["codedValue"] for i in processor.code_lists_map["IETESTCD"]["codeListItems"]]
        assert "IN01" in coded_values and "EX01" in coded_values

    def test_epoch_codelist_created_from_epochs(self, processor, mock_client):
        mock_client.get_api_json.side_effect = self._api_side_effect
        processor.vlm_lookup = {"TSPARMCD": []}
        processor.studyDesignData["epochs"] = [
            {"name": "Screening", "type": {"code": "C99076"}},
            {"name": "Treatment"},
        ]
        processor.update_datasets_dict()
        assert "EPOCH" in processor.code_lists_map
        coded_values = [i["codedValue"] for i in processor.code_lists_map["EPOCH"]["codeListItems"]]
        assert "Screening" in coded_values and "Treatment" in coded_values

    def test_etcd_codelist_created_from_elements(self, processor, mock_client):
        mock_client.get_api_json.side_effect = self._api_side_effect
        processor.vlm_lookup = {"TSPARMCD": []}
        processor.studyDesignData["elements"] = [
            {"name": "SCRN", "label": "Screening Element"},
        ]
        processor.update_datasets_dict()
        assert "ETCD" in processor.code_lists_map


# ── process_datasets ──────────────────────────────────────────────────────────

class TestProcessDatasets:
    """process_datasets() fetches metadata and calls _process_standard_dataset."""

    def test_builds_item_group_for_each_dataset(self, processor, mock_client):
        processor.datasets_dict = {"VS": {}}
        processor.global_codelist_terms = {}
        mock_client.get_api_json.return_value = MOCK_VS_DATASET
        processor.process_datasets()
        assert len(processor.item_groups) == 1
        assert processor.item_groups[0]["name"] == "VS"

    def test_api_exception_handled_gracefully(self, processor, mock_client):
        processor.datasets_dict = {"UNKNOWN": {}}
        processor.global_codelist_terms = {}
        mock_client.get_api_json.side_effect = Exception("404 Not Found")
        # Should not raise; prints a warning instead
        processor.process_datasets()
        assert processor.item_groups == []
