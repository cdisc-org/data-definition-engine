"""
Regression tests for the fixes documented in GENERATE_DEFINE_FIXES.md.

Each test block is labeled with the finding ID from that report.
"""
import json
import xml.etree.ElementTree as ET

import pytest


# ---------- helpers ----------

DEFINE_NS = "{http://www.cdisc.org/ns/def/v2.1}"
ODM_NS = "{http://www.cdisc.org/ns/odm/v1.3}"
XLINK_NS = "{http://www.w3.org/1999/xlink}"


def _iter_tag(root, local_name):
    return [
        e for e in root.iter()
        if e.tag == f"{DEFINE_NS}{local_name}" or e.tag == f"{ODM_NS}{local_name}"
    ]


def _attr(elem, local_name):
    """Fetch an attribute by local name, tolerating either namespace prefix."""
    if local_name in elem.attrib:
        return elem.attrib[local_name]
    for key, value in elem.attrib.items():
        if key.endswith("}" + local_name):
            return value
    return None


def _generate(dds_json, temp_output_dir):
    """Write dds_json to a temp file, run the generator, and return the parsed tree."""
    from define_generator import DefineGenerator

    in_path = temp_output_dir / "in.json"
    out_path = temp_output_dir / "out.xml"
    with open(in_path, "w") as f:
        json.dump(dds_json, f)
    dg = DefineGenerator(str(in_path), str(out_path), log_level="WARNING")
    dg.create()
    return ET.parse(out_path).getroot(), out_path


def _minimal_template(**overrides):
    base = {
        "studyOID": "TEST.STUDY",
        "studyName": "Test",
        "studyDescription": "Test",
        "protocolName": "TEST",
        "defineVersion": "2.1.0",
        "itemGroups": [],
        "conditions": [],
        "whereClauses": [],
        "codeLists": [],
        "methods": [],
        "standards": [],
    }
    base.update(overrides)
    return base


# =============================================================================
# H1 — methods.py returns the MethodDef object, not the raw dict
# =============================================================================

class TestH1MethodsReturnsMethodDef:
    def test_non_empty_methods_section_does_not_crash(self, temp_output_dir):
        template = _minimal_template(
            methods=[{
                "OID": "MT.MY_METHOD",
                "name": "My Method",
                "type": "Computation",
                "description": "a derivation method",
            }],
        )
        root, _ = _generate(template, temp_output_dir)
        method_defs = _iter_tag(root, "MethodDef")
        # Post-processing may also add its own MethodDef — only require ours is present.
        assert any(m.get("OID") == "MT.MY_METHOD" for m in method_defs)

    def test_method_dedup_on_oid(self, temp_output_dir):
        template = _minimal_template(
            methods=[
                {"OID": "MT.X", "name": "X", "type": "Computation", "description": "d"},
                {"OID": "MT.X", "name": "X dupe", "type": "Computation", "description": "d"},
            ],
        )
        root, _ = _generate(template, temp_output_dir)
        method_defs = [m for m in _iter_tag(root, "MethodDef") if m.get("OID") == "MT.X"]
        assert len(method_defs) == 1


# =============================================================================
# H2 — No duplicate LF.acrf leaf
# =============================================================================

class TestH2DedupAcrfLeaf:
    def test_single_acrf_leaf_with_annotated_crf_loader(self, temp_output_dir):
        template = _minimal_template(
            annotatedCRF=[{"leafID": "LF.acrf", "href": "acrf.pdf", "title": "Annotated CRF"}],
        )
        root, _ = _generate(template, temp_output_dir)
        leaves = [e for e in _iter_tag(root, "leaf") if e.get("ID") == "LF.acrf"]
        assert len(leaves) == 1

    def test_single_acrf_leaf_without_annotated_crf_section(self, sample_dds_file, temp_output_xml):
        from define_generator import DefineGenerator

        dg = DefineGenerator(str(sample_dds_file), str(temp_output_xml), log_level="WARNING")
        dg.create()
        root = ET.parse(temp_output_xml).getroot()
        leaves = [e for e in _iter_tag(root, "leaf") if e.get("ID") == "LF.acrf"]
        assert len(leaves) == 1


# =============================================================================
# H5 — Missing standards section produces no KeyError
# =============================================================================

class TestH5MissingStandards:
    def test_generator_runs_when_standards_omitted(self, temp_output_dir):
        template = _minimal_template()
        del template["standards"]
        root, _ = _generate(template, temp_output_dir)
        assert root is not None


# =============================================================================
# H6 — validate_define_file renamed + reports True/False + main exits 1
# =============================================================================

class TestH6Validation:
    def test_function_renamed(self):
        import define_generator
        assert hasattr(define_generator, "validate_define_file")
        assert not hasattr(define_generator, "validate_defile_file")

    def test_validation_returns_false_for_invalid_file(self, temp_output_dir):
        from define_generator import validate_define_file

        bad = temp_output_dir / "not-xml.xml"
        bad.write_text("<ODM>not valid define</ODM>")
        assert validate_define_file(str(bad)) is False


# =============================================================================
# H7 — Slice ItemDefs are deduped by OID
# =============================================================================

class TestH7DedupSliceItemDefs:
    def test_slice_items_sharing_oid_appear_once(self, sample_dds_file, temp_output_xml):
        from define_generator import DefineGenerator

        dg = DefineGenerator(str(sample_dds_file), str(temp_output_xml), log_level="WARNING")
        dg.create()
        root = ET.parse(temp_output_xml).getroot()
        item_oids = [e.get("OID") for e in _iter_tag(root, "ItemDef")]
        assert len(item_oids) == len(set(item_oids)), "duplicate ItemDef OIDs in output"


# =============================================================================
# H8 — Loaders no longer clobber centrally initialized lists
# =============================================================================

class TestH8NoListClobbering:
    def test_itemgroups_does_not_reset_itemdef_list(self):
        import inspect
        import itemGroups

        source = inspect.getsource(itemGroups.ItemGroups.create_define_objects)
        assert 'define_objects["ItemDef"] = []' not in source
        assert "define_objects['ItemDef'] = []" not in source

    def test_methods_does_not_reset_methoddef_list(self):
        import inspect
        import methods

        source = inspect.getsource(methods.Methods.create_define_objects)
        assert 'define_objects["MethodDef"] = []' not in source


# =============================================================================
# H9 / M21 — Explicit dispatch order: conditions always run before whereClauses
# =============================================================================

class TestH9ExplicitDispatchOrder:
    def test_whereclause_built_with_reordered_json(self, temp_output_dir):
        # whereClauses comes BEFORE conditions in the JSON but still must work.
        template_reordered = {
            "studyOID": "T",
            "studyName": "T",
            "defineVersion": "2.1.0",
            "itemGroups": [],
            "whereClauses": [
                {"OID": "WC.X", "conditions": ["COND.X"]},
            ],
            "conditions": [
                {
                    "OID": "COND.X",
                    "rangeChecks": [
                        {
                            "comparator": "EQ",
                            "checkValues": ["Y"],
                            "item": "IT.X.Y",
                            "softHard": "Soft",
                        }
                    ],
                },
            ],
            "codeLists": [],
            "methods": [],
            "standards": [],
        }
        root, _ = _generate(template_reordered, temp_output_dir)
        wcs = _iter_tag(root, "WhereClauseDef")
        assert len(wcs) == 1
        range_checks = _iter_tag(wcs[0], "RangeCheck")
        assert len(range_checks) == 1
        assert _attr(range_checks[0], "ItemOID") == "IT.X.Y"

    def test_whereclause_unknown_condition_raises(self, temp_output_dir):
        template = {
            "studyOID": "T",
            "studyName": "T",
            "defineVersion": "2.1.0",
            "itemGroups": [],
            "conditions": [],
            "whereClauses": [{"OID": "WC.BAD", "conditions": ["COND.MISSING"]}],
            "codeLists": [],
            "methods": [],
            "standards": [],
        }
        with pytest.raises(ValueError, match="unknown condition"):
            _generate(template, temp_output_dir)


# =============================================================================
# H10 — LOADERS keys use lowercase names matching the JSON convention
# =============================================================================

class TestH10LoaderKeyCasing:
    def test_loader_keys_are_lowercase(self):
        import define_generator

        for key in ("comments", "documents", "dictionaries"):
            assert key in define_generator.LOADERS
        for key in ("Comments", "Documents", "Dictionaries"):
            assert key not in define_generator.LOADERS


# =============================================================================
# M9 — whereClauses raises a contextual ValueError on unknown condition
# (also covered above; kept here for explicit M9 tracking).
# =============================================================================


# =============================================================================
# M10 — SoftHard passes through from the DDS JSON
# =============================================================================

class TestM10SoftHardPassthrough:
    def test_softhard_hard_value_preserved(self, temp_output_dir):
        template = {
            "studyOID": "T",
            "studyName": "T",
            "defineVersion": "2.1.0",
            "itemGroups": [],
            "conditions": [
                {
                    "OID": "COND.H",
                    "rangeChecks": [
                        {
                            "comparator": "EQ",
                            "checkValues": ["Y"],
                            "item": "IT.X.Y",
                            "softHard": "Hard",
                        }
                    ],
                },
            ],
            "whereClauses": [{"OID": "WC.H", "conditions": ["COND.H"]}],
            "codeLists": [],
            "methods": [],
            "standards": [],
        }
        root, _ = _generate(template, temp_output_dir)
        rc = _iter_tag(root, "RangeCheck")
        assert rc
        assert rc[0].get("SoftHard") == "Hard"


# =============================================================================
# M15 — CodeList dedup across datasets
# =============================================================================

class TestM15CodeListDedup:
    def test_duplicate_codelist_oid_collapses(self, temp_output_dir):
        template = _minimal_template(
            codeLists=[
                {
                    "OID": "CL.YESNO",
                    "name": "YesNo",
                    "dataType": "text",
                    "codeListItems": [
                        {"codedValue": "Y", "decode": "Yes"},
                        {"codedValue": "N", "decode": "No"},
                    ],
                },
                {
                    "OID": "CL.YESNO",
                    "name": "YesNo duplicate",
                    "dataType": "text",
                    "codeListItems": [],
                },
            ],
        )
        root, _ = _generate(template, temp_output_dir)
        cls = [c for c in _iter_tag(root, "CodeList") if c.get("OID") == "CL.YESNO"]
        assert len(cls) == 1


# =============================================================================
# M18 — AnnotatedCRF from the loader is consumed into the output
# =============================================================================

class TestM18AnnotatedCRFConsumed:
    def test_loader_acrf_reaches_output(self, temp_output_dir):
        template = _minimal_template(
            annotatedCRF=[{"leafID": "LF.acrf", "href": "custom.pdf", "title": "Annotated CRF"}],
        )
        root, _ = _generate(template, temp_output_dir)
        leaves = [e for e in _iter_tag(root, "leaf") if e.get("ID") == "LF.acrf"]
        assert len(leaves) == 1
        assert _attr(leaves[0], "href") == "custom.pdf"


# =============================================================================
# M19 — create_supplementaldoc returns None when only acrf leaves present
# =============================================================================

class TestM19SupplementalDoc:
    def test_returns_none_for_empty_input(self):
        from supporting_docs import SupportingDocuments

        assert SupportingDocuments.create_supplementaldoc("LF.acrf", []) is None

    def test_returns_none_when_all_leaves_are_acrf(self):
        from odmlib.define_2_1 import model as DEFINE
        from supporting_docs import SupportingDocuments

        leaf = DEFINE.leaf(ID="LF.acrf", href="acrf.pdf")
        assert SupportingDocuments.create_supplementaldoc("LF.acrf", [leaf]) is None


# =============================================================================
# L6 — Purpose resolution is driven from the dataset definition
# =============================================================================

class TestL6PurposeResolution:
    def test_explicit_purpose_is_preserved(self):
        from itemGroups import ItemGroups

        assert ItemGroups._resolve_purpose({"purpose": "Analysis"}) == "Analysis"

    def test_adam_standard_drives_analysis(self):
        from itemGroups import ItemGroups

        assert ItemGroups._resolve_purpose({"standard": "ADAM-IG-1.1"}) == "Analysis"

    def test_adam_dataset_name_drives_analysis(self):
        from itemGroups import ItemGroups

        assert ItemGroups._resolve_purpose({"name": "ADAE"}) == "Analysis"

    def test_sdtm_default_is_tabulation(self):
        from itemGroups import ItemGroups

        assert ItemGroups._resolve_purpose({"name": "DM"}) == "Tabulation"


# =============================================================================
# L13 — ODM.create_root replaces the confusing create_define_objects name
# =============================================================================

class TestL13ODMCreateRoot:
    def test_create_root_returns_odm_instance(self):
        from odm import ODM as ODMClass

        odm = ODMClass().create_root()
        assert odm.__class__.__name__ == "ODM"


# =============================================================================
# L14 — FileOID is unique per run (not a hardcoded constant)
# =============================================================================

class TestL14FileOID:
    def test_two_runs_produce_different_fileoids(self, sample_dds_file, temp_output_dir):
        from define_generator import DefineGenerator

        out1 = temp_output_dir / "run1.xml"
        out2 = temp_output_dir / "run2.xml"
        DefineGenerator(str(sample_dds_file), str(out1), log_level="WARNING").create()
        DefineGenerator(str(sample_dds_file), str(out2), log_level="WARNING").create()

        def _file_oid(path):
            root = ET.parse(path).getroot()
            return root.get("FileOID")

        assert _file_oid(out1) != _file_oid(out2)
        assert _file_oid(out1) is not None
