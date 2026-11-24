"""DDS root ``resources`` (DDS_FOR_METHODS.md D9): a DocumentReference with a leafID, such as a method's
supporting PDF, becomes a def:leaf that a MethodDef's def:DocumentRef can point to."""
from __future__ import annotations

import pytest

from tests.test_fixes import _attr, _iter_tag, _minimal_template
from tests.test_methods import DAYCALC, _generator, _method_def, _set_method, _valid_360i

RECIST = {"OID": "LF.RECIST", "leafID": "LF.RECIST", "title": "RECIST 1.1 derivations", "href": "recist.pdf"}


def _leaves(root):
    return {_attr(leaf, "ID"): leaf for leaf in _iter_tag(root, "leaf")}


class TestResources:
    def test_a_document_reference_becomes_a_leaf_and_a_resource_is_skipped(self, temp_output_dir):
        template = _minimal_template(resources=[RECIST, {"OID": "RES.FHIR", "name": "FHIR",
                                                         "resourceType": "HL7-FHIR"}])
        _, root, _ = _generator(template, temp_output_dir)
        leaves = _leaves(root)
        assert "LF.RECIST" in leaves and "RES.FHIR" not in leaves
        assert _attr(leaves["LF.RECIST"], "href") == "recist.pdf"
        assert [t.text for t in _iter_tag(leaves["LF.RECIST"], "title")] == ["RECIST 1.1 derivations"]

    def test_a_leaf_already_written_is_written_once(self, temp_output_dir):
        acrf = {"OID": "LF.acrf", "leafID": "LF.acrf", "title": "Annotated CRF", "href": "acrf.pdf"}
        template = _minimal_template(annotatedCRFs=[{"leafID": "LF.acrf", "href": "acrf.pdf",
                                                     "title": "Annotated CRF"}],
                                     documents=[{"ID": "LF.RECIST", "title": "RECIST", "href": "recist.pdf"}],
                                     resources=[acrf, RECIST])
        _, root, _ = _generator(template, temp_output_dir)
        assert sorted(_attr(leaf, "ID") for leaf in _iter_tag(root, "leaf")) == ["LF.RECIST", "LF.acrf"]

    def test_a_document_reference_without_a_title_is_refused(self, temp_output_dir):
        with pytest.raises(ValueError, match="'title' missing in resources LF.RECIST"):
            _generator(_minimal_template(resources=[{"leafID": "LF.RECIST", "href": "recist.pdf"}]),
                       temp_output_dir)

    def test_a_method_pointing_at_a_resource_leaf_passes_the_xsd(self, data_dir, temp_output_dir):
        from define_generator import validate_define_file

        dds = _valid_360i(data_dir)
        _set_method(dds, "IT.VS.VSORRES.BMI", "MT.DAYCALC")
        dds["methods"] = [{**DAYCALC, "documents": [{"leafID": "LF.RECIST", "pages": [3, 4]}]}]
        dds["resources"] = [RECIST]
        _, root, out = _generator(dds, temp_output_dir)

        refs = _iter_tag(_method_def(root, "MT.DAYCALC"), "DocumentRef")
        assert [_attr(r, "leafID") for r in refs] == ["LF.RECIST"]
        page = _iter_tag(refs[0], "PDFPageRef")[0]
        assert (_attr(page, "Type"), _attr(page, "FirstPage"), _attr(page, "LastPage")) == ("PhysicalRef", "3", "4")
        assert "LF.RECIST" in _leaves(root)
        assert validate_define_file(str(out)) is True
