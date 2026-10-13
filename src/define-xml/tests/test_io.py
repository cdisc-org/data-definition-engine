"""
Tests for file I/O methods:
  - save_output
  - save_debug_files
  - generate_patch_file
  - apply_patch
  - validate_against_schema (_basic_schema_validation path)
"""

import json
import yaml
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_patch_file(tmp_path, content):
    patch_path = tmp_path / "patch.yaml"
    patch_path.write_text(content)
    return str(patch_path)


def _minimal_item_group(oid="IG.VS", name="VS", key_sequence=None):
    return {
        "OID": oid,
        "name": name,
        "description": "Vital Signs",
        "items": [],
        "slices": [],
        "keySequence": key_sequence or ["__PLACEHOLDER__"],
    }


# ── save_output ───────────────────────────────────────────────────────────────

class TestSaveOutput:
    """save_output() assembles and writes the final Define-JSON file."""

    def test_creates_output_file(self, processor):
        processor.save_output()
        import os
        assert os.path.exists(processor.output_template)

    def test_output_is_valid_json(self, processor):
        processor.save_output()
        with open(processor.output_template) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_output_contains_required_top_level_keys(self, processor):
        processor.save_output()
        with open(processor.output_template) as f:
            data = json.load(f)
        for key in ["OID", "itemGroups", "whereClauses", "conditions", "codeLists"]:
            assert key in data

    def test_item_groups_from_instance_written_to_file(self, processor):
        processor.item_groups = [{"OID": "IG.VS", "name": "VS"}]
        processor.save_output()
        with open(processor.output_template) as f:
            data = json.load(f)
        assert len(data["itemGroups"]) == 1
        assert data["itemGroups"][0]["OID"] == "IG.VS"

    def test_code_lists_written_as_list(self, processor):
        processor.code_lists_map = {
            "VSTESTCD": {"OID": "CL.VSTESTCD", "name": "VS Test Code", "codeListItems": []}
        }
        processor.save_output()
        with open(processor.output_template) as f:
            data = json.load(f)
        assert isinstance(data["codeLists"], list)
        assert data["codeLists"][0]["OID"] == "CL.VSTESTCD"

    def test_where_clauses_written(self, processor):
        processor.where_clauses = [{"OID": "WC.VS.abc12345", "conditions": ["COND.VS.X"]}]
        processor.save_output()
        with open(processor.output_template) as f:
            data = json.load(f)
        assert data["whereClauses"][0]["OID"] == "WC.VS.abc12345"

    def test_conditions_written(self, processor):
        processor.conditions = [{"OID": "COND.VS.X", "rangeChecks": []}]
        processor.save_output()
        with open(processor.output_template) as f:
            data = json.load(f)
        assert data["conditions"][0]["OID"] == "COND.VS.X"


# ── save_debug_files ──────────────────────────────────────────────────────────

class TestSaveDebugFiles:
    """save_debug_files() writes intermediate dicts to JSON files."""

    def test_creates_debug_files_in_working_directory(self, processor, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        processor.all_dataset_data = []
        processor.save_debug_files(prefix="debug")
        expected_files = [
            "debug_dataset_data.json",
            "debug_datasets_dict.json",
            "debug_bc_dict.json",
            "debug_vlm_lookup.json",
            "debug_test_dict.json",
            "debug_condition_lookup.json",
            "debug_code_lists_map.json",
            "debug_vlm_items_by_variable.json",
        ]
        for fname in expected_files:
            assert (tmp_path / fname).exists(), f"Missing debug file: {fname}"

    def test_debug_files_are_valid_json(self, processor, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        processor.all_dataset_data = []
        processor.save_debug_files(prefix="debug")
        for p in tmp_path.glob("debug_*.json"):
            with open(p) as f:
                data = json.load(f)
            assert data is not None


# ── generate_patch_file ───────────────────────────────────────────────────────

class TestGeneratePatchFile:
    """generate_patch_file(patch_output_path) writes a YAML patch template."""

    def test_creates_patch_file(self, processor, tmp_path):
        processor.template["itemGroups"] = []
        processor.template["codeLists"] = []
        patch_path = tmp_path / "patch.yaml"
        processor.generate_patch_file(str(patch_path))
        assert patch_path.exists()

    def test_item_with_null_length_appears_in_patch(self, processor, tmp_path):
        processor.template["itemGroups"] = [{
            **_minimal_item_group(key_sequence=["STUDYID"]),
            "items": [{"OID": "IT.VS.VSORRES", "name": "VSORRES", "description": "Result", "length": None,
                       "origin": {"type": "Collected", "source": "Investigator"}}],
        }]
        processor.template["codeLists"] = []
        patch_path = tmp_path / "patch.yaml"
        processor.generate_patch_file(str(patch_path))
        content = patch_path.read_text()
        assert "IT.VS.VSORRES" in content
        assert "length" in content

    def test_item_with_placeholder_origin_appears_in_patch(self, processor, tmp_path):
        processor.template["itemGroups"] = [{
            **_minimal_item_group(key_sequence=["STUDYID"]),
            "items": [{"OID": "IT.VS.VSTESTCD", "name": "VSTESTCD", "description": "Test Code",
                       "origin": {"type": "__PLACEHOLDER__", "source": "__PLACEHOLDER__"}}],
        }]
        processor.template["codeLists"] = []
        patch_path = tmp_path / "patch.yaml"
        processor.generate_patch_file(str(patch_path))
        content = patch_path.read_text()
        assert "IT.VS.VSTESTCD" in content
        assert "originType" in content

    def test_item_group_with_placeholder_key_sequence_appears_in_patch(self, processor, tmp_path):
        processor.template["itemGroups"] = [_minimal_item_group()]
        processor.template["codeLists"] = []
        patch_path = tmp_path / "patch.yaml"
        processor.generate_patch_file(str(patch_path))
        content = patch_path.read_text()
        assert "IG.VS" in content
        assert "keySequence" in content

    def test_codelist_with_placeholder_term_appears_in_patch(self, processor, tmp_path):
        processor.template["itemGroups"] = []
        processor.template["codeLists"] = [{
            "OID": "CL.SOMETHING", "name": "Something",
            "codeListItems": [{"codedValue": "__PLACEHOLDER__", "decode": "__PLACEHOLDER__"}],
        }]
        patch_path = tmp_path / "patch.yaml"
        processor.generate_patch_file(str(patch_path))
        content = patch_path.read_text()
        assert "CL.SOMETHING" in content
        assert "codeListItems" in content

    def test_fully_populated_template_produces_minimal_patch(self, processor, tmp_path):
        processor.template["itemGroups"] = [{
            **_minimal_item_group(key_sequence=["STUDYID", "VSSEQ"]),
            "items": [{"OID": "IT.VS.VSTESTCD", "name": "VSTESTCD", "length": 8,
                       "origin": {"type": "Collected", "source": "Investigator"}}],
        }]
        processor.template["codeLists"] = [
            {"OID": "CL.VSTESTCD", "name": "VS Test Code",
             "codeListItems": [{"codedValue": "SYSBP", "decode": "Systolic Blood Pressure"}]}
        ]
        patch_path = tmp_path / "patch.yaml"
        processor.generate_patch_file(str(patch_path))
        content = patch_path.read_text()
        # Sections for fully-filled items/codeLists should not appear
        assert "itemGroups:" not in content
        assert "items:" not in content
        assert "codeLists:" not in content

    def test_slice_items_with_null_length_appear_in_patch(self, processor, tmp_path):
        processor.template["itemGroups"] = [{
            **_minimal_item_group(key_sequence=["STUDYID"]),
            "slices": [{"OID": "VL.VS.VSORRES", "items": [
                {"OID": "IT.VS.VSORRES.SYSBP", "name": "VSORRES", "length": None,
                 "origin": {"type": "Collected", "source": "Investigator"}}
            ]}],
        }]
        processor.template["codeLists"] = []
        patch_path = tmp_path / "patch.yaml"
        processor.generate_patch_file(str(patch_path))
        content = patch_path.read_text()
        assert "IT.VS.VSORRES.SYSBP" in content


# ── apply_patch ───────────────────────────────────────────────────────────────

class TestApplyPatch:
    """apply_patch(patch_file) reads YAML and updates the in-memory template.

    save_output() is called internally by apply_patch, which reassigns
    self.template['itemGroups'] = self.item_groups and
    self.template['codeLists'] = list(self.code_lists_map.values()).
    Tests must therefore set processor.item_groups / processor.code_lists_map
    AND point processor.template at those same objects so assertions hold
    after save_output runs.
    """

    def test_applies_complete_key_sequence(self, processor, tmp_path):
        ig = _minimal_item_group()
        processor.item_groups = [ig]
        processor.template["itemGroups"] = processor.item_groups
        processor.code_lists_map = {}
        patch_file = _make_patch_file(tmp_path, "itemGroups:\n  IG.VS:\n    keySequence: [STUDYID, USUBJID, VSSEQ]\n")
        processor.apply_patch(patch_file)
        assert processor.template["itemGroups"][0]["keySequence"] == ["STUDYID", "USUBJID", "VSSEQ"]

    def test_does_not_apply_key_sequence_still_containing_placeholder(self, processor, tmp_path):
        ig = _minimal_item_group()
        processor.item_groups = [ig]
        processor.template["itemGroups"] = processor.item_groups
        processor.code_lists_map = {}
        patch_file = _make_patch_file(tmp_path, "itemGroups:\n  IG.VS:\n    keySequence: [STUDYID, __PLACEHOLDER__]\n")
        processor.apply_patch(patch_file)
        assert processor.template["itemGroups"][0]["keySequence"] == ["__PLACEHOLDER__"]

    def test_applies_item_length(self, processor, tmp_path):
        ig = {
            **_minimal_item_group(key_sequence=["STUDYID"]),
            "items": [{"OID": "IT.VS.VSORRES", "name": "VSORRES", "length": None}],
        }
        processor.item_groups = [ig]
        processor.template["itemGroups"] = processor.item_groups
        processor.code_lists_map = {}
        patch_file = _make_patch_file(tmp_path, "items:\n  IT.VS.VSORRES:\n    length: 20\n")
        processor.apply_patch(patch_file)
        assert processor.template["itemGroups"][0]["items"][0]["length"] == 20

    def test_applies_origin_type_and_source(self, processor, tmp_path):
        ig = {
            **_minimal_item_group(key_sequence=["STUDYID"]),
            "items": [{"OID": "IT.VS.VSORRES", "name": "VSORRES",
                       "origin": {"type": "__PLACEHOLDER__", "source": "__PLACEHOLDER__"}}],
        }
        processor.item_groups = [ig]
        processor.template["itemGroups"] = processor.item_groups
        processor.code_lists_map = {}
        patch_file = _make_patch_file(
            tmp_path,
            'items:\n  IT.VS.VSORRES:\n    originType: "Collected"\n    originSource: "Investigator"\n',
        )
        processor.apply_patch(patch_file)
        item = processor.template["itemGroups"][0]["items"][0]
        assert item["origin"]["type"] == "Collected"
        assert item["origin"]["source"] == "Investigator"

    def test_placeholder_origin_in_patch_not_applied(self, processor, tmp_path):
        ig = {
            **_minimal_item_group(key_sequence=["STUDYID"]),
            "items": [{"OID": "IT.VS.VSORRES", "name": "VSORRES",
                       "origin": {"type": "__PLACEHOLDER__", "source": "__PLACEHOLDER__"}}],
        }
        processor.item_groups = [ig]
        processor.template["itemGroups"] = processor.item_groups
        processor.code_lists_map = {}
        patch_file = _make_patch_file(
            tmp_path,
            'items:\n  IT.VS.VSORRES:\n    originType: "__PLACEHOLDER__"\n    originSource: "__PLACEHOLDER__"\n',
        )
        processor.apply_patch(patch_file)
        item = processor.template["itemGroups"][0]["items"][0]
        assert item["origin"]["type"] == "__PLACEHOLDER__"

    def test_replaces_placeholder_codelist_items(self, processor, tmp_path):
        cl = {
            "OID": "CL.SOMETHING", "name": "Something",
            "codeListItems": [{"codedValue": "__PLACEHOLDER__", "decode": "__PLACEHOLDER__"}],
        }
        processor.item_groups = []
        processor.code_lists_map = {"CL.SOMETHING": cl}
        processor.template["itemGroups"] = processor.item_groups
        processor.template["codeLists"] = list(processor.code_lists_map.values())
        patch_file = _make_patch_file(
            tmp_path,
            "codeLists:\n  CL.SOMETHING:\n    codeListItems:\n      - codedValue: 'ACTIVE'\n        decode: 'Active'\n",
        )
        processor.apply_patch(patch_file)
        coded_values = [i["codedValue"] for i in processor.template["codeLists"][0]["codeListItems"]]
        assert "ACTIVE" in coded_values
        assert "__PLACEHOLDER__" not in coded_values

    def test_duplicate_patch_codelist_item_not_added_twice(self, processor, tmp_path):
        cl = {
            "OID": "CL.SOMETHING", "name": "Something",
            "codeListItems": [{"codedValue": "ACTIVE", "decode": "Active"}],
        }
        processor.item_groups = []
        processor.code_lists_map = {"CL.SOMETHING": cl}
        processor.template["itemGroups"] = processor.item_groups
        processor.template["codeLists"] = list(processor.code_lists_map.values())
        patch_file = _make_patch_file(
            tmp_path,
            "codeLists:\n  CL.SOMETHING:\n    codeListItems:\n      - codedValue: 'ACTIVE'\n        decode: 'Active'\n",
        )
        processor.apply_patch(patch_file)
        active_count = sum(1 for i in processor.template["codeLists"][0]["codeListItems"] if i["codedValue"] == "ACTIVE")
        assert active_count == 1

    def test_applies_patch_to_slice_items(self, processor, tmp_path):
        ig = {
            **_minimal_item_group(key_sequence=["STUDYID"]),
            "slices": [{"OID": "VL.VS.VSORRES", "items": [
                {"OID": "IT.VS.VSORRES.SYSBP", "name": "VSORRES", "length": None}
            ]}],
        }
        processor.item_groups = [ig]
        processor.template["itemGroups"] = processor.item_groups
        processor.code_lists_map = {}
        patch_file = _make_patch_file(tmp_path, "items:\n  IT.VS.VSORRES.SYSBP:\n    length: 15\n")
        processor.apply_patch(patch_file)
        slice_item = processor.template["itemGroups"][0]["slices"][0]["items"][0]
        assert slice_item["length"] == 15

    def test_empty_patch_file_leaves_template_unchanged(self, processor, tmp_path):
        processor.template["itemGroups"] = [_minimal_item_group()]
        processor.template["codeLists"] = []
        patch_file = _make_patch_file(tmp_path, "")
        processor.apply_patch(patch_file)
        assert processor.template["itemGroups"][0]["keySequence"] == ["__PLACEHOLDER__"]

    def test_unknown_oid_in_patch_silently_ignored(self, processor, tmp_path):
        processor.template["itemGroups"] = [_minimal_item_group(key_sequence=["STUDYID"])]
        processor.template["codeLists"] = []
        patch_file = _make_patch_file(tmp_path, "items:\n  IT.NONEXISTENT.VAR:\n    length: 10\n")
        processor.apply_patch(patch_file)  # should not raise


# ── _basic_schema_validation ──────────────────────────────────────────────────

class TestBasicSchemaValidation:
    """_basic_schema_validation(schema) performs structural checks on template."""

    def _minimal_schema(self):
        return {"classes": {"DefineModel": {"attributes": {}}}}

    def test_passes_when_template_has_required_fields(self, processor):
        processor.template["fileOID"] = "ODM.LZZT.Version1"
        processor.template["studyOID"] = "ODM.LZZT.V1"
        processor.template["itemGroups"] = [{"OID": "IG.VS", "name": "VS"}]
        processor.template["codeLists"] = []
        result = processor._basic_schema_validation(self._minimal_schema())
        assert result is True

    def test_returns_true_when_schema_has_no_classes(self, processor):
        processor.template["fileOID"] = "ODM.LZZT"
        processor.template["studyOID"] = "ODM.LZZT"
        result = processor._basic_schema_validation({})  # no 'classes' key
        assert result is True

    def test_fails_when_item_group_missing_oid(self, processor):
        processor.template["fileOID"] = "ODM.LZZT"
        processor.template["studyOID"] = "ODM.LZZT"
        processor.template["itemGroups"] = [{"name": "VS"}]  # no OID
        processor.template["codeLists"] = []
        result = processor._basic_schema_validation(self._minimal_schema())
        assert result is False

    def test_fails_when_codelist_missing_name(self, processor):
        processor.template["fileOID"] = "ODM.LZZT"
        processor.template["studyOID"] = "ODM.LZZT"
        processor.template["itemGroups"] = []
        processor.template["codeLists"] = [{"OID": "CL.VSTESTCD"}]  # no name
        result = processor._basic_schema_validation(self._minimal_schema())
        assert result is False
