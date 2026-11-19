"""
MethodDef generation from the DDS Method shape (methods plan M0).

The DDS holds methods in ODM v2.0 style: a MethodSignature, and FormalExpressions that carry
inline code (`expression`) or an `externalCodeLib` reference. Define-XML 2.1 gets a downgraded
copy: the signature and external references are dropped and counted, inline code becomes a
FormalExpression, and integer document pages become PhysicalRef page references.
"""
import copy
import json
import logging

import pytest

from tests.test_fixes import _attr, _generate, _iter_tag, _minimal_template


DAYCALC = {
    "OID": "MT.DAYCALC",
    "name": "Algorithm to derive --DY",
    "type": "Computation",
    "description": "Study day relative to RFSTDTC.",
    "signature": {
        "parameters": [
            {"name": "DTC", "dataType": "datetime", "description": "Date of the observation", "orderNumber": 1},
            {"name": "RFSTDTC", "dataType": "datetime", "description": "Subject reference start", "orderNumber": 2},
        ],
        "returnValues": [{"name": "DY", "dataType": "integer", "description": "Study day", "orderNumber": 1}],
    },
    "expressions": [
        {"context": "SAS 9.4", "expression": "DY = DTC - RFSTDTC + (DTC >= RFSTDTC);"},
        {"context": "R (sdtm.oak 0.2.0)",
         "externalCodeLib": {"library": "sdtm.oak", "method": "derive_study_day", "version": "0.2.0"}},
    ],
}


def _method_def(root, oid):
    matches = [m for m in _iter_tag(root, "MethodDef") if m.get("OID") == oid]
    assert len(matches) == 1, f"expected one MethodDef {oid}, found {len(matches)}"
    return matches[0]


def _generator(template, temp_output_dir):
    """Run the generator and return (DefineGenerator, parsed root, output path)."""
    from define_generator import DefineGenerator
    import xml.etree.ElementTree as ET

    in_path = temp_output_dir / "in.json"
    out_path = temp_output_dir / "out.xml"
    in_path.write_text(json.dumps(template))
    dg = DefineGenerator(str(in_path), str(out_path), log_level="WARNING")
    dg.create()
    return dg, ET.parse(out_path).getroot(), out_path


def _methods_loader():
    import methods
    loader = methods.Methods()
    loader.lang = "en"
    return loader


# =============================================================================
# The DDS Method shape and the downgrade to Define-XML 2.1
# =============================================================================

class TestDdsMethodShape:
    def test_inline_expression_becomes_formal_expression(self, temp_output_dir):
        root, _ = _generate(_minimal_template(methods=[copy.deepcopy(DAYCALC)]), temp_output_dir)
        fes = _iter_tag(_method_def(root, "MT.DAYCALC"), "FormalExpression")
        assert len(fes) == 1
        assert fes[0].get("Context") == "SAS 9.4"
        assert fes[0].text == "DY = DTC - RFSTDTC + (DTC >= RFSTDTC);"

    def test_signature_and_external_code_lib_are_dropped_and_counted(self, temp_output_dir):
        dg, root, out = _generator(_minimal_template(methods=[copy.deepcopy(DAYCALC)]), temp_output_dir)
        xml = out.read_text()
        assert "MethodSignature" not in xml and "ExternalCodeLib" not in xml
        assert "derive_study_day" not in xml
        assert dg.method_summary["signaturesDropped"] == ["MT.DAYCALC"]
        assert dg.method_summary["externalCodeLibsDropped"] == ["MT.DAYCALC"]

    def test_empty_signature_is_not_counted_as_a_drop(self, temp_output_dir):
        placeholder = {"OID": "MT.AE.AESEQ", "name": "Algorithm to derive AESEQ", "type": "Computation",
                       "description": "__PLACEHOLDER__", "signature": {"parameters": [], "returnValues": []}}
        dg, _, _ = _generator(_minimal_template(methods=[placeholder]), temp_output_dir)
        assert dg.method_summary["signaturesDropped"] == []

    def test_expression_without_context_is_refused(self):
        method = {"OID": "MT.X", "name": "X", "type": "Computation", "description": "d",
                  "expressions": [{"expression": "x = 1;"}]}
        with pytest.raises(ValueError, match="context"):
            _methods_loader()._create_methoddef_object(method)

    def test_expression_with_neither_body_is_skipped(self, caplog):
        method = {"OID": "MT.X", "name": "X", "type": "Computation", "description": "d",
                  "expressions": [{"context": "SAS"}]}
        with caplog.at_level(logging.WARNING):
            md = _methods_loader()._create_methoddef_object(method)
        assert len(md.FormalExpression) == 0
        assert "no expression" in caplog.text

    def test_description_as_translated_text(self, temp_output_dir):
        method = {"OID": "MT.X", "name": "X", "type": "Computation",
                  "description": {"translations": [{"language": "en", "value": "English text"},
                                                   {"language": "fr", "value": "Texte"}]}}
        root, _ = _generate(_minimal_template(methods=[method]), temp_output_dir)
        tts = _iter_tag(_method_def(root, "MT.X"), "TranslatedText")
        assert [(t.text, _attr(t, "lang")) for t in tts] == [("English text", "en"), ("Texte", "fr")]


class TestMethodDocuments:
    def _refs(self, docs):
        method = {"OID": "MT.X", "name": "X", "type": "Computation", "description": "d", "documents": docs}
        return _methods_loader()._create_methoddef_object(method).DocumentRef

    def test_contiguous_pages_become_first_and_last_page(self):
        (dr,) = self._refs([{"leafID": "LF.METHODS", "pages": [5, 3, 4]}])
        assert dr.leafID == "LF.METHODS"
        pdf = dr.PDFPageRef[0]
        assert (pdf.Type, pdf.FirstPage, pdf.LastPage, pdf.PageRefs) == ("PhysicalRef", 3, 5, None)

    def test_scattered_pages_become_page_refs(self):
        (dr,) = self._refs([{"leafID": "LF.METHODS", "pages": [9, 2]}])
        pdf = dr.PDFPageRef[0]
        assert (pdf.Type, pdf.PageRefs) == ("PhysicalRef", "2 9")

    def test_document_without_pages_points_at_the_whole_document(self):
        (dr,) = self._refs([{"leafID": "LF.METHODS"}])
        assert dr.leafID == "LF.METHODS" and len(dr.PDFPageRef) == 0

    def test_document_without_leaf_is_skipped(self, caplog):
        with caplog.at_level(logging.WARNING):
            refs = self._refs([{"pages": [1]}])
        assert len(refs) == 0
        assert "leafID" in caplog.text


class TestLegacyFlatShape:
    def test_context_and_code_still_render(self, temp_output_dir):
        method = {"OID": "MT.X", "name": "X", "type": "Computation", "description": "d",
                  "context": "SAS", "code": "x = 1;"}
        root, _ = _generate(_minimal_template(methods=[method]), temp_output_dir)
        (fe,) = _iter_tag(_method_def(root, "MT.X"), "FormalExpression")
        assert (fe.get("Context"), fe.text) == ("SAS", "x = 1;")

    def test_named_destination_is_spelled_per_rule_45(self, temp_output_dir):
        method = {"OID": "MT.X", "name": "X", "type": "Computation", "description": "d",
                  "document": "LF.CSDRG", "pages": "DM AE"}
        root, out = _generate(_minimal_template(methods=[method]), temp_output_dir)
        (pdf,) = _iter_tag(_method_def(root, "MT.X"), "PDFPageRef")
        assert (pdf.get("Type"), pdf.get("PageRefs")) == ("NamedDestination", "DM AE")
        assert "namedDestination" not in out.read_text()

    def test_legacy_integer_pages_become_physical_refs(self):
        method = {"OID": "MT.X", "name": "X", "type": "Computation", "description": "d",
                  "document": "LF.CSDRG", "pages": [7, 8]}
        (dr,) = _methods_loader()._create_methoddef_object(method).DocumentRef
        pdf = dr.PDFPageRef[0]
        assert (pdf.Type, pdf.FirstPage, pdf.LastPage) == ("PhysicalRef", 7, 8)


class TestMethodType:
    @pytest.mark.parametrize("mtype", ["Computation", "Imputation"])
    def test_define_types_pass_through(self, mtype):
        method = {"OID": "MT.X", "name": "X", "type": mtype, "description": "d"}
        assert _methods_loader()._create_methoddef_object(method).Type == mtype

    def test_transformation_maps_to_computation_with_a_warning(self, caplog):
        method = {"OID": "MT.X", "name": "X", "type": "Transformation", "description": "d"}
        with caplog.at_level(logging.WARNING):
            md = _methods_loader()._create_methoddef_object(method)
        assert md.Type == "Computation"
        assert "rule 209" in caplog.text

    @pytest.mark.parametrize("mtype", ["Analysis", "Display", "Preload"])
    def test_types_define_xml_rejects_are_refused(self, mtype):
        method = {"OID": "MT.X", "name": "X", "type": mtype, "description": "d"}
        with pytest.raises(ValueError, match="rule 209"):
            _methods_loader()._create_methoddef_object(method)


# =============================================================================
# The shared DocumentRef helper and post-processing as a safety net
# =============================================================================

class TestSharedDocumentRef:
    def test_origins_and_methods_share_one_helper(self):
        import define_object
        import items
        import methods
        assert not hasattr(items.Items, "_document_ref")
        assert items.Items.document_ref is define_object.DefineObject.document_ref
        assert methods.Methods.document_ref is define_object.DefineObject.document_ref

    def test_origin_pages_fall_back_to_the_acrf_leaf(self):
        import items
        loader = items.Items()
        loader.lang, loader.acrf = "en", "LF.ACRF"
        dr = loader.document_ref({"pages": [2, 3]}, loader.acrf)
        assert dr.leafID == "LF.ACRF" and dr.PDFPageRef[0].FirstPage == 2


def _valid_360i(data_dir):
    """The canonical fixture with its Length placeholders filled, so the output passes the XSD."""
    dds = json.loads((data_dir / "define-360i.json").read_text())

    def fill(o):
        if isinstance(o, dict):
            if str(o.get("OID", "")).startswith("IT.") and o.get("dataType") in ("text", "integer", "float") \
                    and not o.get("length"):
                o["length"] = 8
            for v in o.values():
                fill(v)
        elif isinstance(o, list):
            for v in o:
                fill(v)

    fill(dds)
    return dds


def _set_method(dds, item_oid, method_oid):
    def walk(o):
        if isinstance(o, dict):
            if o.get("OID") == item_oid:
                o["method"] = method_oid
                return True
            return any(walk(v) for v in o.values())
        if isinstance(o, list):
            return any(walk(v) for v in o)
        return False
    assert walk(dds), f"{item_oid} not found"


class TestPostProcessingSafetyNet:
    def test_a_derived_item_without_a_method_gets_a_logged_placeholder(self, data_dir, temp_output_dir, caplog):
        with caplog.at_level(logging.INFO):
            dg, _, _ = _generator(_valid_360i(data_dir), temp_output_dir)
        assert dg.method_summary["placeholders"] == ["MT.VS.VSORRES.BMI"]
        assert "placeholder MethodDef MT.VS.VSORRES.BMI" in caplog.text

    def test_no_placeholders_when_every_derived_item_has_a_method(self, data_dir, temp_output_dir):
        dds = _valid_360i(data_dir)
        _set_method(dds, "IT.VS.VSORRES.BMI", "MT.BMI")
        dds["methods"] = [{"OID": "MT.BMI", "name": "Algorithm to derive BMI", "type": "Computation",
                           "description": "BMI = Weight (kg) / Height (m)^2."}]
        dg, root, _ = _generator(dds, temp_output_dir)
        assert dg.method_summary["placeholders"] == []
        refs = [r for r in _iter_tag(root, "ItemRef") if r.get("ItemOID") == "IT.VS.VSORRES.BMI"]
        assert [r.get("MethodOID") for r in refs] == ["MT.BMI"]
        assert [m.get("OID") for m in _iter_tag(root, "MethodDef")] == ["MT.BMI"]


class TestDowngradedOutputIsSchemaValid:
    def test_odm_v2_style_method_passes_the_define_xml_21_xsd(self, data_dir, temp_output_dir):
        from define_generator import validate_define_file

        dds = _valid_360i(data_dir)
        _set_method(dds, "IT.VS.VSORRES.BMI", "MT.DAYCALC")
        method = copy.deepcopy(DAYCALC)
        method["documents"] = [{"leafID": "LF.acrf", "pages": [3, 4, 5]}]
        dds["methods"] = [method]
        dg, root, out = _generator(dds, temp_output_dir)

        md = _method_def(root, "MT.DAYCALC")
        assert len(_iter_tag(md, "FormalExpression")) == 1
        assert len(_iter_tag(md, "DocumentRef")) == 1
        assert dg.method_summary["placeholders"] == []
        assert dg.method_summary["signaturesDropped"] == ["MT.DAYCALC"]
        assert validate_define_file(str(out)) is True
