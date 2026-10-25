"""
A combined DDS (the Define loader's output enriched by the CRF loader) must run through the
Define generator: it carries Biomedical Concepts in ``concepts``/``conceptProperties`` (the DDS
schema's ReifiedConcept and ConceptProperty) and the CRF's CDASHIG standard, none of which has a
Define-XML 2.1 element (FIXES.md 2.2).
"""
import json


def _combined(tmp_path):
    with open("tests/fixtures/define-360i.json") as f:
        dds = json.load(f)
    dds["concepts"] = [{"OID": "CONC.BiomedicalConcept_1", "name": "Informed Consent",
                        "properties": [{"OID": "CONCPROP.1", "name": "DSDECOD"}]}]
    dds["conceptProperties"] = [{"OID": "CONCPROP.1", "name": "DSDECOD",
                                 "coding": [{"code": "C82977", "codeSystem": "http://www.cdisc.org"}]}]
    dds["standards"] = list(dds.get("standards") or []) + [
        {"OID": "STD.CDASHIG", "name": "CDASHIG", "type": "IG", "version": "2.3", "status": "FINAL"},
        {"OID": "STD.CDASHCT", "name": "CDISC/NCI", "type": "CT", "version": "2026-03-27",
         "status": "FINAL", "publishingSet": "CDASH"}]
    path = tmp_path / "combined.json"
    path.write_text(json.dumps(dds))
    return path


def test_a_combined_dds_generates_without_crf_only_content(tmp_path):
    import define_generator
    out = tmp_path / "define.xml"
    define_generator.DefineGenerator(str(_combined(tmp_path)), str(out)).create()
    xml = out.read_text()
    assert 'OID="STD.CDASHIG"' not in xml          # no Define-XML 2.1 Standard/@Name for it
    assert 'OID="STD.CDASHCT"' in xml              # CDISC/NCI with PublishingSet CDASH is allowed
    assert "CONC.BiomedicalConcept_1" not in xml and "CONCPROP.1" not in xml


def test_a_legacy_dictionary_shaped_concept_still_becomes_an_external_codelist():
    import concepts
    from odmlib.define_2_1 import model as DEFINE  # noqa: F401 - the loader builds odmlib objects
    objects = {"CodeList": []}
    concepts.Concepts().create_define_objects(
        [{"shortName": "MEDDRA", "name": "MedDRA", "dataType": "text", "dictionary": "MEDDRA", "version": "27.0"}],
        objects, "en", "LF.acrf")
    assert [cl.OID for cl in objects["CodeList"]] == ["CL.MEDDRA"]
