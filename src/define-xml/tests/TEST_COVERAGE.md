# Test Suite Coverage — `create_define_json.py`

## Overview

| File | Tests | What it covers |
|---|---|---|
| `test_pure_functions.py` | 30 | `_validate_date_format`, `_convert_data_type`, `_create_condition_key`, `_generate_hex_oid` |
| `test_state_methods.py` | 68 | `__init__`, `_build_global_codelist_terms`, `_update_subset_codelist_names`, `_find_item_by_oid`, `_collect_item_placeholders`, `_apply_item_patch`, `add_standards`, `populate_study_elements`, condition/where-clause creation, `build_vlm_lookup` |
| `test_mocked_api.py` | 57 | `_process_variables`, `_build_where_clause`, `_process_variable_codelist`, `_process_vlm_codelist`, `_process_standard_dataset`, `_process_bc_type`, `_process_dss_type`, `process_biomedical_concepts`, `update_datasets_dict`, `process_datasets` |
| `test_io.py` | 32 | `save_output`, `save_debug_files`, `generate_patch_file`, `apply_patch`, `_basic_schema_validation` |
| **Total** | **187** | |

---

## How to Run

### Prerequisites

Install test dependencies (from the generator requirements as a guide — the loader
uses the same pytest):

```bash
pip install pytest
```

If you also want a coverage report:

```bash
pip install pytest-cov
```

### Running from the repo root

```bash
# Run all loader tests
pytest src/define-xml/tests/ -v

# Run with coverage report printed to terminal
pytest src/define-xml/tests/ -v --cov=src/define-xml --cov-report=term-missing

# Run with an HTML coverage report (opens in browser)
pytest src/define-xml/tests/ -v --cov=src/define-xml --cov-report=html
# then open: htmlcov/index.html

# Run a single test file
pytest src/define-xml/tests/test_pure_functions.py -v

# Run a single test class
pytest src/define-xml/tests/test_mocked_api.py::TestProcessVariableCodelist -v

# Run a single test by name
pytest src/define-xml/tests/test_state_methods.py::TestBuildVlmLookup::test_adapt_added_when_c98704_characteristic_present -v
```

### Running from inside the tests directory

```bash
cd src/define-xml
pytest tests/ -v
```

---

## How Tests Are Structured

### `conftest.py` — Shared Fixtures

The key challenge with `USDMDefineJSONProcessor` is that `__init__` opens a USDM
file from disk and instantiates `CDISCLibraryClient` (which requires a real API key).
Two fixtures handle this:

| Fixture | Scope | Purpose |
|---|---|---|
| `minimal_usdm_file` | function | Path to `fixtures/minimal_usdm.json` — a structurally complete but minimal USDM |
| `mock_client` | function | A `MagicMock` standing in for `CDISCLibraryClient` |
| `processor` | function | A fully initialised `USDMDefineJSONProcessor` where `proc.client IS mock_client` |

Because `proc.client IS mock_client`, tests that exercise API-dependent methods
configure the mock **before** calling the method:

```python
def test_something(self, processor, mock_client):
    mock_client.get_api_json.return_value = { ... }
    processor.some_method()
    assert ...
```

---

## Detailed Coverage by Method

### Pure Functions (no API, no I/O)

#### `_validate_date_format(date_string) -> bool`
| Test | Scenario |
|---|---|
| `test_valid_date_returns_true` | "2025-03-28" |
| `test_valid_leap_day_returns_true` | "2024-02-29" (real leap year) |
| `test_no_dashes_returns_false` | "20250328" |
| `test_slash_separated_returns_false` | "2025/03/28" |
| `test_month_13_returns_false` | "2025-13-01" |
| `test_day_32_returns_false` | "2025-01-32" |
| `test_feb_30_returns_false` | "2025-02-30" |
| `test_non_leap_feb_29_returns_false` | "2025-02-29" (non-leap year) |
| `test_empty_string_returns_false` | "" |
| `test_partial_date_returns_false` | "2025-03" |
| `test_datetime_string_returns_false` | "2025-03-28T12:00:00" |
| `test_single_digit_month_returns_false` | "2025-3-28" |

#### `_convert_data_type(var) -> str`
| Test | Scenario |
|---|---|
| `test_char_returns_text` | `simpleDatatype: "Char"` → `"text"` |
| `test_num_returns_integer` | `simpleDatatype: "Num"` → `"integer"` |
| `test_dtc_suffix_returns_datetime` | name ends in `DTC` → `"datetime"` |
| `test_dtc_suffix_overrides_num_mapping` | DTC check runs before type mapping |
| `test_dur_suffix_returns_duration_datetime` | name ends in `DUR` → `"durationDatetime"` |
| `test_dur_suffix_overrides_num_mapping` | DUR check overrides Num mapping |
| `test_unknown_datatype_returns_placeholder` | unknown type → `"????"` |
| `test_normal_char_variable_not_dtc_or_dur` | regular Char variable |
| `test_num_variable_not_dtc_or_dur` | regular Num variable |

#### `_create_condition_key(range_checks) -> str`
| Test | Scenario |
|---|---|
| `test_key_contains_item_comparator_and_value` | Basic single check |
| `test_values_are_sorted_so_order_does_not_matter` | `["BMI","HEIGHT","WEIGHT"]` == `["WEIGHT","HEIGHT","BMI"]` |
| `test_multiple_checks_sorted_by_item_name` | Checks re-ordered → same key |
| `test_spaces_stripped_from_concatenated_values` | "GLUCOSE FASTING" → "GLUCOSEFASTING" in key |
| `test_empty_check_values_produces_stable_key` | Empty values list handled |
| `test_returns_string` | Return type |
| `test_different_values_produce_different_keys` | SYSBP vs DIABP → different keys |

#### `_generate_hex_oid(content, prefix) -> str`
| Test | Scenario |
|---|---|
| `test_result_starts_with_prefix` | "COND.xxxxxxxx" format |
| `test_hash_portion_is_exactly_8_characters` | 8-char MD5 prefix |
| `test_hash_portion_is_lowercase_hex` | Only `0-9a-f` characters |
| `test_deterministic_for_identical_content` | Same input → same output |
| `test_different_content_produces_different_hash` | Collision avoidance |
| `test_known_md5_hash` | Exact MD5 value verified |
| `test_empty_prefix_produces_dot_prefixed_hash` | Degenerate case |

---

### State Methods (preset instance state, no API)

#### `__init__` / Initialisation
| Test | Scenario |
|---|---|
| `test_invalid_sdtmct_format_raises_value_error` | "20250328" raises `ValueError` |
| `test_none_sdtmct_skips_date_validation` | `sdtmct=None` is valid |
| `test_template_has_required_top_level_keys` | OID, itemGroups, codeLists, etc. present |
| `test_study_version_data_extracted_from_usdm` | jmespath extraction ran |
| `test_study_design_data_extracted_from_usdm` | studyDesignData set |
| `test_internal_collections_initialised_empty` | datasets_dict, bc_dict, etc. start empty |

#### `_build_global_codelist_terms()`
| Test | Scenario |
|---|---|
| `test_empty_datasets_dict_gives_empty_result` | No data → empty result |
| `test_single_dataset_with_terms_indexed` | Terms correctly indexed by concept ID |
| `test_multiple_datasets_same_codelist_id_are_unioned` | SYSBP from VS ∪ GLUCOSE from LB |
| `test_empty_terms_list_stores_empty_set` | Empty terms → empty set (not absent) |
| `test_entry_without_codelist_concept_id_is_skipped` | Missing key gracefully skipped |
| `test_variable_without_codelist_key_is_skipped` | Variable with no codelist gracefully skipped |
| `test_result_values_are_sets` | Return type is `set` |

#### `_update_subset_codelist_names()`
| Test | Scenario |
|---|---|
| `test_key_without_underscore_left_unchanged` | "UNIT" → "Unit" |
| `test_key_with_underscore_appends_subset_qualifier` | "UNIT_BMI" → "Unit (Subset BMI)" |
| `test_calling_twice_is_idempotent` | Double call does not double-append |
| `test_multiple_underscores_splits_only_on_first` | "UNIT_WEIGHT_KG" → "(Subset WEIGHT_KG)" |
| `test_only_subset_keys_are_modified` | Mixed keys: only underscore keys updated |

#### `_find_item_by_oid(oid)`
| Test | Scenario |
|---|---|
| `test_finds_item_in_items_list` | Standard items list |
| `test_finds_item_inside_a_slice` | VLM slice items |
| `test_returns_none_when_oid_not_found` | Missing OID → None |
| `test_returns_none_for_empty_item_groups` | Empty template |
| `test_returns_first_match_across_item_groups` | Multiple itemGroups with same OID |

#### `_collect_item_placeholders(item, item_section)`
| Test | Scenario |
|---|---|
| `test_null_length_is_collected` | `length: null` added to patch section |
| `test_placeholder_origin_type_is_collected` | `type: "__PLACEHOLDER__"` collected |
| `test_placeholder_origin_source_is_collected` | `source: "__PLACEHOLDER__"` collected |
| `test_fully_valid_item_produces_no_entry` | Valid item → nothing collected |
| `test_missing_length_key_treated_same_as_null` | Missing `length` key also collected |
| `test_only_length_placeholder_not_origin_when_origin_valid` | Partial placeholder isolation |

#### `_apply_item_patch(item, item_patches)`
| Test | Scenario |
|---|---|
| `test_applies_integer_length` | Fills null length with patch value |
| `test_null_length_in_patch_leaves_item_unchanged` | Null in patch → no change |
| `test_applies_origin_type_and_source` | Both origin fields filled |
| `test_placeholder_origin_type_in_patch_leaves_item_unchanged` | Placeholder in patch → no change |
| `test_creates_origin_dict_if_not_present` | Creates `origin` dict if absent |
| `test_oid_absent_from_patches_leaves_item_unchanged` | Non-matching OID silently ignored |

#### `add_standards()`
| Test | Scenario |
|---|---|
| `test_exactly_two_standards_added` | Exactly 2 entries |
| `test_sdtmig_oid_present` | `STD.SDTMIG` present |
| `test_sdtmig_version_matches_init_param` | Version matches `sdtmig="3.4"` |
| `test_sdtmig_type_is_ig` | `type: "IG"` |
| `test_sdtmct_oid_present` | `STD.SDTMCT` present |
| `test_sdtmct_version_matches_init_param` | Version matches `sdtmct="2025-03-28"` |
| `test_sdtmct_publishing_set_is_sdtm` | `publishingSet: "SDTM"` |

#### `populate_study_elements()`
| Test | Scenario |
|---|---|
| `test_study_name_from_acronym_title` | Study Acronym title → studyName |
| `test_study_description_from_official_title` | Official Study Title → studyDescription |
| `test_file_oid_contains_study_name` | studyName embedded in fileOID |
| `test_study_oid_contains_study_name` | studyName embedded in studyOID |
| `test_mdv_oid_contains_study_name` | studyName embedded in OID |
| `test_protocol_name_equals_study_name` | protocolName == studyName |
| `test_creation_datetime_is_populated` | creationDateTime non-empty |
| `test_study_version_zero_produces_version1_in_oid` | 0-indexed → 1-indexed display |

#### Condition / WhereClause creation
| Test | Scenario |
|---|---|
| `test_creates_one_condition` | Single where clause → one condition |
| `test_condition_oid_starts_with_cond_dataset` | `COND.VS.` prefix |
| `test_condition_contains_range_checks` | rangeChecks populated |
| `test_identical_where_clauses_deduplicated` | Same clause → same OID, no duplicate |
| `test_different_values_create_separate_conditions` | SYSBP vs DIABP → 2 conditions |
| `test_create_where_clause_returns_wc_oid` | `WC.VS.` prefix |
| `test_create_where_clause_appended_to_list` | Added to `self.where_clauses` |
| `test_where_clause_oid_deterministic_for_same_inputs` | Stable hash |

#### `build_vlm_lookup()` — TSPARMCD entries
| Test | TSPARMCD value triggered |
|---|---|
| `test_adapt_added_when_c98704_characteristic_present` | ADAPT |
| `test_adapt_not_added_when_c98704_absent` | ADAPT absent |
| `test_narms_added_when_arms_present` | NARMS |
| `test_narms_not_added_when_no_arms` | NARMS absent |
| `test_stype_added_when_study_type_decode_populated` | STYPE |
| `test_stype_not_added_when_decode_is_empty` | STYPE absent |
| `test_objprim_added_when_primary_objective_present` | OBJPRIM (code C85826) |
| `test_objsec_added_when_secondary_objective_present` | OBJSEC (code C85827) |
| `test_tblind_added_when_blinding_schema_decode_set` | TBLIND |
| `test_tphase_added_when_study_phase_decode_set` | TPHASE |
| `test_hltsubji_added_when_population_includes_healthy_subjects` | HLTSUBJI |
| `test_rdind_added_when_indication_is_rare_disease` | RDIND |
| `test_therarea_added_when_therapeutic_area_decode_set` | THERAREA |
| `test_plansub_added_when_planned_enrollment_number_set` | PLANSUB |

#### `build_vlm_lookup()` — IEORRES entries
| Test | Scenario |
|---|---|
| `test_ieorres_entry_added_per_eligibility_criterion` | 2 criteria → 2 IEORRES entries |
| `test_ieorres_where_clause_uses_criterion_name_as_value` | criterion name in where clause Values |

---

### Mocked API Methods

#### `_process_variables(variables, dataset_name, bc)`
| Test | Scenario |
|---|---|
| `test_creates_dataset_and_variable_entry` | Basic population of datasets_dict |
| `test_variable_without_data_element_concept_id_is_skipped` | Missing DEC ID → skipped |
| `test_existing_variable_entry_not_overwritten` | Existing entry preserved |
| `test_optional_fields_stored_when_present` | role, length, etc. captured |
| `test_codelist_populated_when_response_codes_match` | Matched response codes → terms |
| `test_vlm_target_variables_skipped_for_response_code_lookup` | vlmTarget=True → no API call |
| `test_terms_merged_across_multiple_bc_calls_for_same_variable` | SYSBP + DIABP from two BCs |

#### `_build_where_clause(bc, bc_data, dss_response, dataset_name)`
| Test | Scenario |
|---|---|
| `test_empty_list_when_no_variable_has_comparator` | No comparators → [] |
| `test_builds_clause_item_with_response_code_values` | Response codes → Values |
| `test_falls_back_to_assigned_term_when_no_response_codes_match` | assignedTerm fallback |
| `test_falls_back_to_value_list_when_no_assigned_term` | valueList fallback |
| `test_multiple_comparator_variables_combined_into_single_where_clause` | Implicit AND |

#### `_process_variable_codelist(var, dataset, restriction_codes=None)`
| Test | Scenario |
|---|---|
| `test_returns_none_when_var_has_no_codelist_link` | No `_links.codelist` |
| `test_returns_none_when_href_is_null` | `href: null` → None, no API call |
| `test_returns_codelist_oid` | Returns `CL.VSTESTCD` |
| `test_codelist_added_to_code_lists_map` | Registered in code_lists_map |
| `test_restriction_filters_to_specified_terms` | Only SYSBP, not DIABP |
| `test_empty_restriction_list_falls_back_to_global_terms` | Global terms used |
| `test_empty_restriction_and_no_global_terms_produces_placeholder` | `__PLACEHOLDER__` inserted |
| `test_no_restriction_and_no_global_terms_produces_placeholder` | No restriction path |
| `test_subsequent_calls_do_not_duplicate_terms` | Idempotent codelist building |

#### `_process_vlm_codelist(vlm_codelist)`
| Test | Scenario |
|---|---|
| `test_returns_none_for_empty_dict` | {} → None |
| `test_returns_none_when_entry_has_no_codelist_concept_id` | Missing ID → None |
| `test_returns_correct_oid` | Returns `CL.VSTESTCD` |
| `test_uses_subset_codelist_name_as_short_name` | subsetCodelist used as key |
| `test_restriction_list_filters_terms` | Only SYSBP |

#### `_process_standard_dataset(dataset, dataset_data)`
| Test | Scenario |
|---|---|
| `test_item_group_appended_to_item_groups_list` | IG.VS created and appended |
| `test_item_group_carries_correct_metadata` | name, description, purpose, standard |
| `test_req_variables_always_included` | STUDYID, USUBJID, VSSEQ always present |
| `test_exp_variables_always_included` | VSORRES (Exp) always present |
| `test_mandatory_true_for_req_variable` | STUDYID mandatory=True |
| `test_mandatory_false_for_exp_variable` | VSORRES mandatory=False |
| `test_is_reference_data_false_when_usubjid_present` | VS → isReferenceData=False |
| `test_is_reference_data_true_for_trial_design_class` | TA → isReferenceData=True |
| `test_observation_class_from_parent_class_title` | "FINDINGS" uppercased |
| `test_placeholder_origin_when_var_not_in_datasets_dict` | Origin defaults to `__PLACEHOLDER__` |
| `test_origin_from_datasets_dict_when_present` | Origin from datasets_dict used |
| `test_dtc_variable_gets_datetime_type` | AESTDTC → dataType=datetime |
| `test_vlm_slices_created_for_variable_in_vlm_lookup` | VL.VS.VSTESTCD slice created |
| `test_codelist_removed_from_parent_when_slice_has_codelist` | Parent codeList removed |
| `test_origin_removed_from_parent_when_slice_has_origin` | Parent origin removed |

#### BC/DSS Type Dispatching
| Test | Scenario |
|---|---|
| `test_bc_type_calls_dataset_specialization_api` | get_biomedicalconcept_latest_datasetspecializations called |
| `test_bc_type_processes_variables_for_each_dataset_link` | Resulting variables populate datasets_dict |
| `test_dss_type_calls_dataset_specialization_api` | get_sdtm_latest_sdtm_datasetspecialization called |
| `test_dss_type_populates_datasets_dict` | Domain added to datasets_dict |
| `test_empty_biomedical_concepts_is_a_no_op` | Empty list → no change |
| `test_dispatches_to_bc_type_handler` | "Biomedical Concept" type → bc handler |
| `test_dispatches_to_dss_type_handler` | "SDTM Dataset Specialization" type → dss handler |

#### `update_datasets_dict()` — Domain seeding
| Test | Domain / Scenario |
|---|---|
| `test_ts_added_when_vlm_lookup_has_tsparmcd_entries` | TS seeded |
| `test_tsparmcd_codelist_restricted_to_vlm_values` | TSPARMCD terms filtered |
| `test_ta_added_when_arms_present` | TA seeded |
| `test_ta_not_added_when_no_arms` | TA absent |
| `test_epoch_codelist_added_to_ta_when_epochs_present` | TA EPOCH codelist built |
| `test_ie_and_tv_added_when_eligibility_criteria_present` | IE, TI, TV seeded |
| `test_sv_added_when_encounters_present` | SV seeded |
| `test_svcntmod_codelist_built_from_encounter_contact_modes` | SVCNTMOD terms from CT API |
| `test_armcd_codelist_created_from_arms` | ARMCD codelist in code_lists_map |
| `test_ietestcd_codelist_created_from_eligibility_criteria` | IETESTCD codelist |
| `test_epoch_codelist_created_from_epochs` | EPOCH codelist |
| `test_etcd_codelist_created_from_elements` | ETCD codelist |

#### `process_datasets()`
| Test | Scenario |
|---|---|
| `test_builds_item_group_for_each_dataset` | VS dataset → IG.VS created |
| `test_api_exception_handled_gracefully` | 404 → warning printed, no raise |

---

### I/O Methods

#### `save_output()`
| Test | Scenario |
|---|---|
| `test_creates_output_file` | File exists after call |
| `test_output_is_valid_json` | Parseable JSON |
| `test_output_contains_required_top_level_keys` | OID, itemGroups, etc. present |
| `test_item_groups_from_instance_written_to_file` | item_groups reflected in output |
| `test_code_lists_written_as_list` | code_lists_map values written as list |
| `test_where_clauses_written` | where_clauses reflected |
| `test_conditions_written` | conditions reflected |

#### `save_debug_files(prefix)`
| Test | Scenario |
|---|---|
| `test_creates_debug_files_in_working_directory` | All 8 debug files created |
| `test_debug_files_are_valid_json` | Each file is valid JSON |

#### `generate_patch_file(patch_output_path)`
| Test | Scenario |
|---|---|
| `test_creates_patch_file` | File created at given path |
| `test_item_with_null_length_appears_in_patch` | Null length → items section |
| `test_item_with_placeholder_origin_appears_in_patch` | Placeholder origin → items section |
| `test_item_group_with_placeholder_key_sequence_appears_in_patch` | Placeholder keySequence → itemGroups section |
| `test_codelist_with_placeholder_term_appears_in_patch` | Placeholder term → codeLists section |
| `test_fully_populated_template_produces_minimal_patch` | No placeholders → no sections |
| `test_slice_items_with_null_length_appear_in_patch` | VLM slice items also scanned |

#### `apply_patch(patch_file)`
| Test | Scenario |
|---|---|
| `test_applies_complete_key_sequence` | Full keySequence applied |
| `test_does_not_apply_key_sequence_still_containing_placeholder` | Partial fill → no change |
| `test_applies_item_length` | length filled from patch |
| `test_applies_origin_type_and_source` | Both origin fields filled |
| `test_placeholder_origin_in_patch_not_applied` | Placeholder in patch → no change |
| `test_replaces_placeholder_codelist_items` | `__PLACEHOLDER__` replaced with real terms |
| `test_duplicate_patch_codelist_item_not_added_twice` | Idempotent codelist item addition |
| `test_applies_patch_to_slice_items` | VLM slice items patched |
| `test_empty_patch_file_leaves_template_unchanged` | Empty YAML → no change |
| `test_unknown_oid_in_patch_silently_ignored` | Stale OIDs not an error |

#### `_basic_schema_validation(schema)`
| Test | Scenario |
|---|---|
| `test_passes_when_template_has_required_fields` | Valid template → True |
| `test_returns_true_when_schema_has_no_classes` | No `classes` key → True |
| `test_fails_when_item_group_missing_oid` | Missing OID → False |
| `test_fails_when_codelist_missing_name` | Missing name → False |

---

## Methods Not Covered

The following methods were intentionally excluded or have limited coverage:

| Method | Reason |
|---|---|
| `process()` | Orchestration only — individual stages are each tested |
| `validate_against_schema()` | Requires linkml installed; the `_basic_schema_validation` fallback path is tested |
| `_write_validation_excel()` | Requires pandas/openpyxl; formatting-only logic |
| `_process_vlm_target_variables()` | Called indirectly via `_process_dss_type` tests |
| `main()` | CLI entry point — tested via argument parser behaviour |
