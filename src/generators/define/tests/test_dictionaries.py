"""
Tests for dictionaries.Dictionaries.

Define-XML v2.1 represents an external dictionary (e.g. MedDRA, WHODrug, SNOMED)
as a CodeList element carrying an ExternalCodeList child rather than enumerated
CodeListItems. These tests exercise the dictionaries loader directly against the
DDS JSON `dictionaries` section shape it expects, and confirm the resulting
odmlib objects serialize to the expected Define-XML.
"""
import xml.etree.ElementTree as ET

import pytest


@pytest.fixture
def dictionaries_instance():
    import dictionaries
    return dictionaries.Dictionaries()


@pytest.fixture
def define_objects():
    """Minimal define_objects container with the CodeList list the loader writes to."""
    return {"CodeList": []}


def _load(loader, template, define_objects):
    loader.create_define_objects(template, define_objects, "en", None)
    return define_objects["CodeList"]


class TestExternalCodeListCreation:
    """A dictionary entry becomes a CodeList with an ExternalCodeList child."""

    def test_full_dictionary_entry(self, dictionaries_instance, define_objects):
        template = [{
            "OID": "CL.MEDDRA",
            "name": "MedDRA",
            "version": "26.0",
            "href": "https://www.meddra.org",
            "dataType": "text",
        }]
        codelists = _load(dictionaries_instance, template, define_objects)

        assert len(codelists) == 1
        cl = codelists[0]
        assert cl.OID == "CL.MEDDRA"
        assert cl.Name == "MedDRA"
        assert cl.DataType == "text"

        ecl = cl.ExternalCodeList
        assert ecl is not None
        assert ecl.Dictionary == "MedDRA"
        assert ecl.Version == "26.0"
        assert ecl.href == "https://www.meddra.org"

    def test_no_inline_items_emitted(self, dictionaries_instance, define_objects):
        """A dictionary CodeList must not carry enumerated/coded items."""
        template = [{"OID": "CL.MEDDRA", "name": "MedDRA", "version": "26.0"}]
        cl = _load(dictionaries_instance, template, define_objects)[0]
        assert cl.CodeListItem == []
        assert cl.EnumeratedItem == []

    def test_default_data_type_is_text(self, dictionaries_instance, define_objects):
        template = [{"OID": "CL.WHODRUG", "name": "WHODrug", "version": "GLOBALB3Mar23"}]
        cl = _load(dictionaries_instance, template, define_objects)[0]
        assert cl.DataType == "text"

    def test_explicit_data_type_preserved(self, dictionaries_instance, define_objects):
        template = [{"OID": "CL.X", "name": "X", "version": "1", "dataType": "integer"}]
        cl = _load(dictionaries_instance, template, define_objects)[0]
        assert cl.DataType == "integer"


class TestOptionalAttributes:
    """Version/href and the def: extension attributes are only set when present."""

    def test_missing_version_is_omitted_from_xml(self, dictionaries_instance, define_objects):
        template = [{"OID": "CL.WHODRUG", "name": "WHODrug"}]
        cl = _load(dictionaries_instance, template, define_objects)[0]
        # odmlib drops None attributes when serializing.
        assert cl.ExternalCodeList.Version is None
        xml = ET.tostring(cl.to_xml()).decode()
        assert "Version=" not in xml

    def test_missing_href_is_omitted_from_xml(self, dictionaries_instance, define_objects):
        template = [{"OID": "CL.WHODRUG", "name": "WHODrug", "version": "x"}]
        cl = _load(dictionaries_instance, template, define_objects)[0]
        assert cl.ExternalCodeList.href is None
        assert "href=" not in ET.tostring(cl.to_xml()).decode()

    def test_comment_oid_set(self, dictionaries_instance, define_objects):
        template = [{"OID": "CL.MEDDRA", "name": "MedDRA", "version": "26.0",
                     "comment": "COM.MEDDRA"}]
        cl = _load(dictionaries_instance, template, define_objects)[0]
        assert cl.CommentOID == "COM.MEDDRA"

    def test_standard_oid_set(self, dictionaries_instance, define_objects):
        template = [{"OID": "CL.MEDDRA", "name": "MedDRA", "version": "26.0",
                     "standard": "STD.MEDDRA"}]
        cl = _load(dictionaries_instance, template, define_objects)[0]
        assert cl.StandardOID == "STD.MEDDRA"

    def test_is_non_standard_set(self, dictionaries_instance, define_objects):
        template = [{"OID": "CL.X", "name": "X", "version": "1", "isNonStandard": True}]
        cl = _load(dictionaries_instance, template, define_objects)[0]
        assert cl.IsNonStandard == "Yes"


class TestDedupAndValidation:
    """OID dedup and required-field validation."""

    def test_duplicate_oid_is_deduped(self, dictionaries_instance, define_objects):
        template = [
            {"OID": "CL.MEDDRA", "name": "MedDRA", "version": "26.0"},
            {"OID": "CL.MEDDRA", "name": "MedDRA dup", "version": "27.0"},
        ]
        codelists = _load(dictionaries_instance, template, define_objects)
        assert len(codelists) == 1
        # first definition wins
        assert codelists[0].Name == "MedDRA"
        assert codelists[0].ExternalCodeList.Version == "26.0"

    def test_existing_codelist_oid_is_not_overwritten(self, dictionaries_instance, define_objects):
        """A dictionary OID already present (e.g. from the codeLists loader) is skipped."""
        from odmlib.define_2_1 import model as DEFINE
        define_objects["CodeList"].append(DEFINE.CodeList(OID="CL.MEDDRA", Name="pre", DataType="text"))
        template = [{"OID": "CL.MEDDRA", "name": "MedDRA", "version": "26.0"}]
        codelists = _load(dictionaries_instance, template, define_objects)
        assert len(codelists) == 1
        assert codelists[0].Name == "pre"

    def test_missing_oid_raises(self, dictionaries_instance, define_objects):
        template = [{"name": "MedDRA", "version": "26.0"}]
        with pytest.raises(ValueError, match="OID"):
            _load(dictionaries_instance, template, define_objects)

    def test_missing_name_raises(self, dictionaries_instance, define_objects):
        template = [{"OID": "CL.MEDDRA", "version": "26.0"}]
        with pytest.raises(ValueError, match="name"):
            _load(dictionaries_instance, template, define_objects)

    def test_empty_template_is_noop(self, dictionaries_instance, define_objects):
        assert _load(dictionaries_instance, [], define_objects) == []


class TestSerialization:
    """End-to-end XML shape for a typical multi-dictionary section."""

    def test_multiple_dictionaries_serialize(self, dictionaries_instance, define_objects):
        template = [
            {"OID": "CL.MEDDRA", "name": "MedDRA", "version": "26.0",
             "href": "https://www.meddra.org"},
            {"OID": "CL.WHODRUG", "name": "WHODrug", "version": "GLOBALB3Mar23"},
        ]
        codelists = _load(dictionaries_instance, template, define_objects)
        assert len(codelists) == 2

        meddra_xml = ET.tostring(codelists[0].to_xml()).decode()
        assert 'OID="CL.MEDDRA"' in meddra_xml
        assert 'Dictionary="MedDRA"' in meddra_xml
        assert 'Version="26.0"' in meddra_xml
        assert 'href="https://www.meddra.org"' in meddra_xml

        # Tag name should be ExternalCodeList regardless of namespace handling.
        ecl = codelists[0].to_xml().find("ExternalCodeList")
        assert ecl is not None