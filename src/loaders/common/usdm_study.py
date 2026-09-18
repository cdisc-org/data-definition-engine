"""Derive study-header identity (name, OIDs) from a USDM file.

Mirrors ``create_define_json.populate_study_elements`` so a DDS whose header was written
with a null ``studyName`` — which interpolates the literal string ``None`` into every
OID — can be repaired by the CRF loader without re-running the Define loader.
"""
from __future__ import annotations

from typing import Any

STUDY_ACRONYM_CODE = "C207646"
OFFICIAL_TITLE_CODE = "C207616"
FALLBACK_STUDY_NAME = "STUDY"


def _title_text(titles: list[dict[str, Any]], code: str) -> str | None:
    for title in titles or []:
        title_type = title.get("type") or {}
        if title_type.get("code") == code and title.get("text"):
            return title["text"]
    return None


def study_header(usdm: dict[str, Any], studyversion: int = 0, studydesign: int = 0) -> dict[str, Any]:
    """Return the DDS study-header fields derived from a USDM document.

    Falls back through Study Acronym title -> ``study.name`` -> first study identifier ->
    ``"STUDY"``. Absent that chain the literal string ``None`` ends up in every OID, which
    is the defect in the committed ``NCT01797120-dds-latest.json``.

    :return: dict with ``studyName``, ``studyDescription``, ``protocolName``, ``OID``,
        ``studyOID`` and ``fileOID``
    """
    study = usdm.get("study") or {}
    versions = study.get("versions") or []
    version = versions[studyversion] if studyversion < len(versions) else {}
    titles = version.get("titles") or []

    study_name = _title_text(titles, STUDY_ACRONYM_CODE)
    study_description = _title_text(titles, OFFICIAL_TITLE_CODE)

    if not study_name:
        study_name = study.get("name") or next(
            (i.get("text") for i in version.get("studyIdentifiers") or [] if i.get("text")),
            None,
        ) or FALLBACK_STUDY_NAME

    version_display = studyversion + 1
    design_display = studydesign + 1
    suffix = f"Version{version_display}.Design{design_display}"

    return {
        "studyName": study_name,
        "studyDescription": study_description or study_name,
        "protocolName": study_name,
        "OID": f"MDV.{study_name}.{suffix}",
        "studyOID": f"ODM.{study_name}.{suffix}",
        "fileOID": f"ODM.DEFINE-JSON.{study_name}.{suffix}",
    }


def study_design(usdm: dict[str, Any], studyversion: int = 0, studydesign: int = 0) -> dict[str, Any]:
    """Return the selected studyDesign dict, or an empty dict when out of range."""
    versions = (usdm.get("study") or {}).get("versions") or []
    if studyversion >= len(versions):
        return {}
    designs = versions[studyversion].get("studyDesigns") or []
    if studydesign >= len(designs):
        return {}
    return designs[studydesign]
