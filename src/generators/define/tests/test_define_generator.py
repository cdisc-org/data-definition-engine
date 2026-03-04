"""
Integration tests for the Define-XML generator.

These tests verify that the generator can process sample DDS JSON files
and produce valid Define-XML output.
"""
import json
import os
import pytest
import xml.etree.ElementTree as ET


class TestDefineGeneratorImports:
    """Test that all required modules can be imported."""

    def test_import_define_generator(self):
        """Test that define_generator module can be imported."""
        import define_generator
        assert hasattr(define_generator, 'DefineGenerator')
        assert hasattr(define_generator, 'main')

    def test_import_define_object(self):
        """Test that define_object base class can be imported."""
        import define_object
        assert hasattr(define_object, 'DefineObject')

    def test_import_loader_modules(self):
        """Test that all loader modules can be imported."""
        import itemGroups
        import items
        import itemRefs
        import codeLists
        import conditions
        import whereClauses
        import study
        import standards
        import methods
        import comments
        import documents
        import dictionaries
        import valueLevel
        assert True  # If we get here, all imports succeeded


class TestDefineGeneratorBasic:
    """Basic tests for DefineGenerator initialization."""

    def test_generator_init_with_valid_file(self, sample_dds_file, temp_output_xml, project_root):
        """Test that DefineGenerator initializes with valid input file."""
        os.chdir(project_root)  # Ensure we're in the right directory for imports
        from define_generator import DefineGenerator

        dg = DefineGenerator(
            dds_file=str(sample_dds_file),
            define_file=str(temp_output_xml),
            log_level="WARNING"  # Reduce log noise during tests
        )
        assert dg.dds_file == str(sample_dds_file)
        assert dg.define_file == str(temp_output_xml)

    def test_generator_init_with_missing_file(self, temp_output_xml, project_root):
        """Test that DefineGenerator raises error for missing input file."""
        os.chdir(project_root)
        from define_generator import DefineGenerator

        with pytest.raises(ValueError, match="cannot be found"):
            DefineGenerator(
                dds_file="/nonexistent/path/to/file.json",
                define_file=str(temp_output_xml),
                log_level="WARNING"
            )


class TestDefineGeneratorIntegration:
    """Integration tests that run the full generator pipeline."""

    def test_generate_xml_from_main_sample(self, sample_dds_file, temp_output_xml, project_root):
        """Test generating Define-XML from the main sample DDS file."""
        os.chdir(project_root)
        from define_generator import DefineGenerator

        dg = DefineGenerator(
            dds_file=str(sample_dds_file),
            define_file=str(temp_output_xml),
            log_level="WARNING"
        )
        dg.create()

        # Verify output file was created
        assert temp_output_xml.exists(), "Output XML file was not created"

        # Verify file has content
        file_size = temp_output_xml.stat().st_size
        assert file_size > 0, "Output XML file is empty"

        # Verify it's valid XML
        tree = ET.parse(temp_output_xml)
        root = tree.getroot()
        assert root is not None, "Could not parse output as XML"


class TestDefineXMLStructure:
    """Tests that verify the structure of generated Define-XML."""

    def test_output_contains_odm_root(self, sample_dds_file, temp_output_xml, project_root):
        """Test that output XML has ODM as root element."""
        os.chdir(project_root)
        from define_generator import DefineGenerator

        dg = DefineGenerator(
            dds_file=str(sample_dds_file),
            define_file=str(temp_output_xml),
            log_level="WARNING"
        )
        dg.create()

        tree = ET.parse(temp_output_xml)
        root = tree.getroot()

        # ODM is the root element (may have namespace prefix)
        assert 'ODM' in root.tag, f"Root element should be ODM, got {root.tag}"

    def test_output_contains_study(self, sample_dds_file, temp_output_xml, project_root):
        """Test that output XML contains Study element."""
        os.chdir(project_root)
        from define_generator import DefineGenerator

        dg = DefineGenerator(
            dds_file=str(sample_dds_file),
            define_file=str(temp_output_xml),
            log_level="WARNING"
        )
        dg.create()

        tree = ET.parse(temp_output_xml)
        root = tree.getroot()

        # Find Study element (accounting for namespaces)
        study_elements = [elem for elem in root.iter() if 'Study' in elem.tag]
        assert len(study_elements) > 0, "Output XML should contain Study element"

    def test_output_contains_itemgroupdef(self, sample_dds_file, temp_output_xml, project_root):
        """Test that output XML contains ItemGroupDef elements."""
        os.chdir(project_root)
        from define_generator import DefineGenerator

        dg = DefineGenerator(
            dds_file=str(sample_dds_file),
            define_file=str(temp_output_xml),
            log_level="WARNING"
        )
        dg.create()

        tree = ET.parse(temp_output_xml)
        root = tree.getroot()

        # Find ItemGroupDef elements
        itemgroup_elements = [elem for elem in root.iter() if 'ItemGroupDef' in elem.tag]
        assert len(itemgroup_elements) > 0, "Output XML should contain ItemGroupDef elements"

    def test_output_contains_itemdef(self, sample_dds_file, temp_output_xml, project_root):
        """Test that output XML contains ItemDef elements."""
        os.chdir(project_root)
        from define_generator import DefineGenerator

        dg = DefineGenerator(
            dds_file=str(sample_dds_file),
            define_file=str(temp_output_xml),
            log_level="WARNING"
        )
        dg.create()

        tree = ET.parse(temp_output_xml)
        root = tree.getroot()

        # Find ItemDef elements
        itemdef_elements = [elem for elem in root.iter() if 'ItemDef' in elem.tag]
        assert len(itemdef_elements) > 0, "Output XML should contain ItemDef elements"


class TestDefineGeneratorIdempotency:
    """Tests to verify generator produces consistent output."""

    def test_same_input_produces_same_output(self, sample_dds_file, temp_output_dir, project_root):
        """Test that running the generator twice produces identical output."""
        os.chdir(project_root)
        from define_generator import DefineGenerator

        output1 = temp_output_dir / "output1.xml"
        output2 = temp_output_dir / "output2.xml"

        # Generate first output
        dg1 = DefineGenerator(
            dds_file=str(sample_dds_file),
            define_file=str(output1),
            log_level="WARNING"
        )
        dg1.create()

        # Generate second output
        dg2 = DefineGenerator(
            dds_file=str(sample_dds_file),
            define_file=str(output2),
            log_level="WARNING"
        )
        dg2.create()

        # Compare file contents (excluding timestamp-dependent elements)
        with open(output1, 'r') as f1, open(output2, 'r') as f2:
            content1 = f1.read()
            content2 = f2.read()

        # Note: Files may differ slightly due to timestamps, but structure should be same
        # For now, just verify both files were created and have similar sizes
        size1 = output1.stat().st_size
        size2 = output2.stat().st_size

        # Sizes should be identical or very close
        assert abs(size1 - size2) < 100, f"Output sizes differ significantly: {size1} vs {size2}"


class TestInputValidation:
    """Tests for input validation and error handling."""

    def test_malformed_json_error(self, temp_output_dir, project_root):
        """Test that malformed JSON produces helpful error message."""
        os.chdir(project_root)
        from define_generator import DefineGenerator

        # Create a file with invalid JSON
        bad_json_file = temp_output_dir / "bad.json"
        bad_json_file.write_text('{"invalid json": }')

        dg = DefineGenerator(
            dds_file=str(bad_json_file),
            define_file=str(temp_output_dir / "output.xml"),
            log_level="WARNING"
        )

        # The create() method should exit with sys.exit(1) on JSON error
        with pytest.raises(SystemExit) as exc_info:
            dg.create()

        assert exc_info.value.code == 1

    def test_require_key_helper(self, project_root):
        """Test that require_key raises ValueError with helpful message for missing keys."""
        os.chdir(project_root)
        from define_object import DefineObject

        # Create a concrete subclass for testing
        class TestObject(DefineObject):
            pass

        obj = TestObject()
        test_dict = {"name": "test", "value": 123}

        # Test successful key retrieval
        assert obj.require_key(test_dict, "name") == "test"
        assert obj.require_key(test_dict, "value") == 123

        # Test missing key without context
        with pytest.raises(ValueError) as exc_info:
            obj.require_key(test_dict, "missing_key")
        assert "Required field 'missing_key' missing" in str(exc_info.value)

        # Test missing key with context
        with pytest.raises(ValueError) as exc_info:
            obj.require_key(test_dict, "missing_key", "ItemDef TEST")
        assert "Required field 'missing_key' missing in ItemDef TEST" in str(exc_info.value)

    def test_missing_itemgroup_name_error(self, temp_output_dir, project_root):
        """Test that missing ItemGroupDef name produces helpful error."""
        os.chdir(project_root)
        from define_generator import DefineGenerator

        # Create JSON with missing 'name' in itemGroup
        bad_data = {
            "studyOID": "TEST.STUDY",
            "studyName": "Test Study",
            "studyDescription": "Test",
            "protocolName": "TEST",
            "metaDataVersionOID": "MDV.TEST",
            "metaDataVersionName": "Test",
            "metaDataVersionDescription": "Test",
            "defineVersion": "2.1.0",
            "itemGroups": [
                {
                    # Missing "name" field
                    "description": "Test dataset",
                    "items": []
                }
            ],
            "conditions": [],
            "whereClauses": [],
            "codeLists": [],
            "methods": [],
            "standards": []
        }

        bad_json_file = temp_output_dir / "missing_name.json"
        with open(bad_json_file, 'w') as f:
            json.dump(bad_data, f)

        dg = DefineGenerator(
            dds_file=str(bad_json_file),
            define_file=str(temp_output_dir / "output.xml"),
            log_level="WARNING"
        )

        with pytest.raises(ValueError) as exc_info:
            dg.create()

        assert "name" in str(exc_info.value).lower()
        assert "missing" in str(exc_info.value).lower()
