"""
Integration tests for the Define-XML generator.
"""
import json
import pytest
import xml.etree.ElementTree as ET


class TestDefineGeneratorImports:
    """Test that all required modules can be imported."""

    def test_import_define_generator(self):
        import define_generator
        assert hasattr(define_generator, 'DefineGenerator')
        assert hasattr(define_generator, 'main')

    def test_import_define_object(self):
        import define_object
        assert hasattr(define_object, 'DefineObject')

    def test_import_loader_modules(self):
        import itemGroups  # noqa: F401
        import items  # noqa: F401
        import itemRefs  # noqa: F401
        import codeLists  # noqa: F401
        import conditions  # noqa: F401
        import whereClauses  # noqa: F401
        import study  # noqa: F401
        import standards  # noqa: F401
        import methods  # noqa: F401
        import comments  # noqa: F401
        import documents  # noqa: F401
        import dictionaries  # noqa: F401
        import valueLevel  # noqa: F401


class TestDefineGeneratorBasic:
    """Basic tests for DefineGenerator initialization."""

    def test_generator_init_with_valid_file(self, sample_dds_file, temp_output_xml):
        from define_generator import DefineGenerator

        dg = DefineGenerator(
            dds_file=str(sample_dds_file),
            define_file=str(temp_output_xml),
            log_level="WARNING",
        )
        assert dg.dds_file == str(sample_dds_file)
        assert dg.define_file == str(temp_output_xml)

    def test_generator_init_with_missing_file(self, temp_output_xml):
        from define_generator import DefineGenerator

        with pytest.raises(ValueError, match="cannot be found"):
            DefineGenerator(
                dds_file="/nonexistent/path/to/file.json",
                define_file=str(temp_output_xml),
                log_level="WARNING",
            )


class TestDefineGeneratorIntegration:
    """Integration tests that run the full generator pipeline."""

    def _run(self, sample_dds_file, temp_output_xml):
        from define_generator import DefineGenerator

        dg = DefineGenerator(
            dds_file=str(sample_dds_file),
            define_file=str(temp_output_xml),
            log_level="WARNING",
        )
        dg.create()
        return dg

    def test_generate_xml_from_main_sample(self, sample_dds_file, temp_output_xml):
        self._run(sample_dds_file, temp_output_xml)
        assert temp_output_xml.exists()
        assert temp_output_xml.stat().st_size > 0
        tree = ET.parse(temp_output_xml)
        assert tree.getroot() is not None

    def test_output_contains_odm_root(self, sample_dds_file, temp_output_xml):
        self._run(sample_dds_file, temp_output_xml)
        tree = ET.parse(temp_output_xml)
        assert 'ODM' in tree.getroot().tag

    def test_output_contains_study(self, sample_dds_file, temp_output_xml):
        self._run(sample_dds_file, temp_output_xml)
        tree = ET.parse(temp_output_xml)
        studies = [e for e in tree.getroot().iter() if 'Study' in e.tag]
        assert studies

    def test_output_contains_itemgroupdef(self, sample_dds_file, temp_output_xml):
        self._run(sample_dds_file, temp_output_xml)
        tree = ET.parse(temp_output_xml)
        groups = [e for e in tree.getroot().iter() if e.tag.endswith('}ItemGroupDef') or e.tag == 'ItemGroupDef']
        assert groups

    def test_output_contains_itemdef(self, sample_dds_file, temp_output_xml):
        self._run(sample_dds_file, temp_output_xml)
        tree = ET.parse(temp_output_xml)
        items = [e for e in tree.getroot().iter() if e.tag.endswith('}ItemDef') or e.tag == 'ItemDef']
        assert items


class TestInputValidation:
    """Tests for input validation and error handling."""

    def test_malformed_json_error(self, temp_output_dir):
        from define_generator import DefineGenerator

        bad_json_file = temp_output_dir / "bad.json"
        bad_json_file.write_text('{"invalid json": }')

        dg = DefineGenerator(
            dds_file=str(bad_json_file),
            define_file=str(temp_output_dir / "output.xml"),
            log_level="WARNING",
        )
        with pytest.raises(SystemExit) as exc_info:
            dg.create()
        assert exc_info.value.code == 1

    def test_require_key_helper(self):
        from define_object import DefineObject

        class TestObject(DefineObject):
            pass

        obj = TestObject()
        d = {"name": "test", "value": 123}
        assert obj.require_key(d, "name") == "test"

        with pytest.raises(ValueError) as exc_info:
            obj.require_key(d, "missing_key", "ItemDef TEST")
        assert "Required field 'missing_key' missing in ItemDef TEST" in str(exc_info.value)

    def test_missing_itemgroup_name_error(self, temp_output_dir):
        from define_generator import DefineGenerator

        bad_data = {
            "studyOID": "TEST.STUDY",
            "studyName": "Test Study",
            "studyDescription": "Test",
            "protocolName": "TEST",
            "defineVersion": "2.1.0",
            "itemGroups": [
                {"description": "Test dataset", "items": []}
            ],
            "conditions": [],
            "whereClauses": [],
            "codeLists": [],
            "methods": [],
            "standards": [],
        }

        bad_json_file = temp_output_dir / "missing_name.json"
        with open(bad_json_file, 'w') as f:
            json.dump(bad_data, f)

        dg = DefineGenerator(
            dds_file=str(bad_json_file),
            define_file=str(temp_output_dir / "output.xml"),
            log_level="WARNING",
        )
        with pytest.raises(ValueError) as exc_info:
            dg.create()
        assert "name" in str(exc_info.value).lower()
        assert "missing" in str(exc_info.value).lower()
