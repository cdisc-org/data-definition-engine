"""The CDASHIG and CDASH CT Standard entries the CRF metadata claims conformance to."""
from __future__ import annotations

from typing import Any

from .constants import STD_CDASHCT_OID, STD_CDASHIG_OID


def crf_standards(cdashig_version: str, cdashct_date: str) -> list[dict[str, Any]]:
    """Return the two DDS Standard entries a CRF DDS needs.

    ``STD.CDASHIG`` is the implementation guide the forms follow; ``STD.CDASHCT`` is the
    controlled-terminology package the codelists came from.

    Note for the generator: ODM 2.0 closes ``Standard/@Name`` to a Define-XML-oriented
    enumeration that has no ``CDASHIG`` value, so only the CT standard survives as a
    native ``Standard`` element there — CDASHIG is emitted as ``Protocol/Alias``.
    """
    return [
        {"OID": STD_CDASHIG_OID, "name": "CDASHIG", "type": "IG",
         "version": cdashig_version, "status": "FINAL"},
        {"OID": STD_CDASHCT_OID, "name": "CDISC/NCI", "type": "CT",
         "version": cdashct_date, "status": "FINAL", "publishingSet": "CDASH"},
    ]


def merge_standards(existing: list[dict[str, Any]],
                    additions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Append standards that are not already present, matching on OID."""
    known = {s.get("OID") for s in existing}
    return existing + [s for s in additions if s.get("OID") not in known]
