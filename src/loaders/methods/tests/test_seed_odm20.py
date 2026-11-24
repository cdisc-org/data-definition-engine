"""Every seed method, and the expression format, is a valid ODM v2.0 MethodDef (methods plan M1).

Each library method is built as an odmlib ``odm_2_0`` MethodDef inside a minimal ODM v2.0 metadata
document and validated against the vendored ``schemas/odm/2.0/ODM.xsd``. odmlib's namespace registry is
process-global and the last imported model wins, so the ODM v2.0 namespace is re-registered before
serializing, as ``generators/crf/targets/base.py`` does.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from loaders.methods.library import SEED_FILE, Library

ODM_XSD = Path(__file__).resolve().parents[4] / "schemas" / "odm" / "2.0" / "ODM.xsd"
ODM_NS = "http://www.cdisc.org/ns/odm/v2.0"


def _odm20_method(method: dict):
    """An odmlib ODM v2.0 MethodDef for a DDS method in the PR-DDS-3 shape."""
    from odmlib.odm_2_0 import model as ODM

    description = method["description"]
    texts = ([(t["value"], t["language"]) for t in description["translations"]]
             if isinstance(description, dict) else [(description, "en")])
    md = ODM.MethodDef(OID=method["OID"], Name=method["name"], Type=method["type"])
    md.Description = ODM.Description()
    for text, lang in texts:
        md.Description.TranslatedText.append(ODM.TranslatedText(_content=text, lang=lang, Type="text"))
    signature = ODM.MethodSignature()
    for key, cls, target in (("parameters", ODM.Parameter, signature.Parameter),
                             ("returnValues", ODM.ReturnValue, signature.ReturnValue)):
        for entry in method.get("signature", {}).get(key) or []:
            attrs = {"Name": entry["name"], "DataType": entry["dataType"]}
            if entry.get("description"):
                attrs["Definition"] = entry["description"]
            if entry.get("orderNumber"):
                attrs["OrderNumber"] = entry["orderNumber"]
            target.append(cls(**attrs))
    md.MethodSignature = signature
    for expr in method.get("expressions") or []:
        fe = ODM.FormalExpression(Context=expr["context"])
        if "expression" in expr:
            fe.Code = ODM.Code(_content=expr["expression"])
        else:
            lib = expr["externalCodeLib"]
            attrs = {"Library": lib["library"]}
            attrs.update({odm: lib[dds] for dds, odm in
                          (("method", "Method"), ("version", "Version"), ("ref", "ref"), ("href", "href"))
                          if dds in lib})
            fe.ExternalCodeLib = ODM.ExternalCodeLib(**attrs)
        md.FormalExpression.append(fe)
    return md


def _odm20_document(method_defs: list) -> str:
    from odmlib.odm_2_0 import model as ODM
    import odmlib.ns_registry as NS

    odm = ODM.ODM(FileOID="ODM.METHODS.TEST", FileType="Snapshot", Granularity="Metadata",
                  CreationDateTime="2026-11-19T00:00:00+00:00", ODMVersion="2.0", Context="Exchange")
    study = ODM.Study(OID="ODM.STUDY", StudyName="METHODS", ProtocolName="METHODS")
    mdv = ODM.MetaDataVersion(OID="MDV.METHODS", Name="Methods")
    for md in method_defs:
        mdv.MethodDef.append(md)
    study.MetaDataVersion.append(mdv)
    odm.Study.append(study)
    NS.NamespaceRegistry(prefix="odm", uri=ODM_NS, is_default=True, is_reset=True)
    NS.bind_document_namespaces(odm, recursive=True)
    return odm.to_xml_string(xml_declaration=True)


@pytest.fixture(scope="module")
def odm_schema():
    import xmlschema
    return xmlschema.XMLSchema(str(ODM_XSD))


def _assert_valid(schema, xml: str) -> None:
    errors = list(schema.iter_errors(xml))
    assert not errors, "\n".join(str(e.reason) for e in errors[:5])


def test_every_seed_method_is_a_valid_odm_v2_methoddef(odm_schema):
    seed = Library.load([SEED_FILE])
    xml = _odm20_document([_odm20_method(seed.dds_method(oid)) for oid in sorted(seed.methods)])
    assert f'xmlns="{ODM_NS}"' in xml
    assert xml.count("<MethodDef ") == 22 and xml.count("<MethodSignature") == 22
    _assert_valid(odm_schema, xml)


def test_inline_and_external_expressions_are_valid_odm_v2(odm_schema, write, library):
    library["methods"][0]["expressions"] = [
        {"context": "SAS 9.4", "expression": "SEQ = SEQ + 1;"},
        {"context": "R (sdtm.oak 0.2.0)",
         "externalCodeLib": {"library": "sdtm.oak", "method": "derive_seq", "version": "0.2.0",
                             "href": "https://pharmaverse.github.io/sdtm.oak/reference/derive_seq.html"}},
    ]
    lib = Library.load(write(library))
    xml = _odm20_document([_odm20_method(lib.dds_method("MT.SEQ"))])
    assert "<Code>SEQ = SEQ + 1;</Code>" in xml and 'Library="sdtm.oak"' in xml
    _assert_valid(odm_schema, xml)


def test_a_placeholder_with_an_empty_signature_is_valid_odm_v2(odm_schema, write, library):
    del library["methods"][0]["signature"]
    lib = Library.load(write(library))
    _assert_valid(odm_schema, _odm20_document([_odm20_method(lib.dds_method("MT.SEQ"))]))
