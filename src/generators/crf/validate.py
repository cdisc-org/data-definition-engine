"""Validate a generated ODM document.

Two independent layers, both worth running:

* **odmlib** — element order, OID uniqueness and definition/reference integrity, and
  (for 1.3.2, which has a Cerberus conformance schema) required attributes and value sets
* **XSD** — the official ODM schema, which odmlib bundles

They catch different things: a schema pass says the markup is legal, and says nothing
about an ``ItemRef`` pointing at an ``ItemOID`` no ``ItemDef`` defines.
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def validate_odm(odm: Any, target: Any, xml: str | None = None,
                 xsd_file: str | Path | None = None) -> list[str]:
    """Validate a document with odmlib and against the ODM XSD.

    :param odm: the odmlib ODM root
    :param target: the :class:`OdmTarget` that built it
    :param xml: the serialized document; serialized from ``odm`` when omitted
    :param xsd_file: a custom XSD; odmlib's bundled schema is used when omitted
    :return: formatted error strings; empty means valid
    """
    errors: list[str] = []
    errors += _validate_model(odm, target)
    errors += _validate_schema(odm, target, xml, xsd_file)
    return errors


def _validate_model(odm: Any, target: Any) -> list[str]:
    from odmlib import create_oid_checker

    kwargs: dict[str, Any] = {
        "collect_errors": True,
        # A checker accumulates every OID it sees, so it must be fresh per document.
        "oid_checker": create_oid_checker(target.package),
    }
    if target.package == "odm_1_3_2":
        from odmlib.odm_1_3_2.rules.metadata_schema import MetadataSchema
        kwargs["conformance_checker"] = MetadataSchema()

    try:
        found = odm.validate(**kwargs) or []
    except Exception as exc:  # noqa: BLE001 - report, never crash the run
        return [f"odmlib validation raised {type(exc).__name__}: {exc}"]
    return [f"odmlib: {e}" for e in found]


def _validate_schema(odm: Any, target: Any, xml: str | None,
                     xsd_file: str | Path | None) -> list[str]:
    from odmlib.odm_parser import ODMSchemaValidator

    if xml is None:
        xml = target.to_xml_string(odm)

    try:
        ET.fromstring(xml)
    except ET.ParseError as exc:
        # iter_errors() raises rather than yields on malformed input, so check first.
        return [f"XSD: document is not well-formed XML: {exc}"]

    try:
        validator = (ODMSchemaValidator(xsd_file=str(xsd_file)) if xsd_file
                     else ODMSchemaValidator(standard="odm", version=target.version))
    except Exception as exc:  # noqa: BLE001
        return [f"XSD: could not load schema: {exc}"]

    errors = []
    for err in validator.xsd.iter_errors(xml):
        errors.append(f"XSD: {err.reason} at {err.path}")
    return errors
