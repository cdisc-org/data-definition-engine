"""USDM Biomedical Concept helpers shared by the DDE loaders.

Extracted from ``create_define_json._usdm_dataset_specialization_ids`` so the CRF loader
resolves specializations the same way the Define loader does. The USDM ``usdmVersion``
field does not distinguish the producing tool — both known producers declare 4.0 — so
these helpers branch on the *shape* of the data, never on the version.
"""
from __future__ import annotations

from typing import Any

SDTM_SPECIALIZATION_EXT_URL = "http://www.cdisc.org/usdm/extensions/specializations/sdtm"
CRF_SPECIALIZATION_EXT_URL = "http://www.cdisc.org/usdm/extensions/specializations/crf"

_EXT_URL = {"sdtm": SDTM_SPECIALIZATION_EXT_URL, "crf": CRF_SPECIALIZATION_EXT_URL}


def usdm_specialization_ids(bc: dict[str, Any], kind: str = "sdtm") -> list[str]:
    """Return the specialization ids a Biomedical Concept references.

    Reads the ``extensionAttributes`` entry first (SoA Workbench) and falls back to
    ``reference`` (CDISC USDM E2J, package-dated) for ``kind="sdtm"``. The package date
    in the reference path is deliberately ignored.

    :param bc: a USDM BiomedicalConcept dict
    :param kind: ``"sdtm"`` or ``"crf"``
    :return: specialization ids, e.g. ``["SYSBP_DENORMALIZED"]``
    """
    url = _EXT_URL[kind]
    ids: list[str] = []
    for ext in bc.get("extensionAttributes") or []:
        if ext.get("url") == url and ext.get("valueString"):
            ids.append(ext["valueString"].rstrip("/").rsplit("/", 1)[-1])
    if not ids and kind == "sdtm":
        reference = bc.get("reference") or ""
        if "/datasetspecializations/" in reference:
            ids.append(reference.rstrip("/").rsplit("/", 1)[-1])
    return ids


def usdm_bc_code(bc: dict[str, Any]) -> str | None:
    """Return the NCI C-code a Biomedical Concept resolves to.

    The code is the last path segment of ``reference``
    (``/mdr/bc/biomedicalconcepts/C25298`` -> ``C25298``). Returns ``None`` when the BC
    carries no C-coded reference — 2 of the 84 BCs in NCT01797120 are in that state.
    """
    reference = bc.get("reference") or ""
    if "/biomedicalconcepts/" not in reference:
        return None
    code = reference.rstrip("/").rsplit("/", 1)[-1]
    return code or None


def usdm_biomedical_concepts(usdm: dict[str, Any], studyversion: int = 0) -> list[dict[str, Any]]:
    """Return the Biomedical Concepts for a study version.

    SoA Workbench puts them on the study *version*; look there first, then fall back to
    the study design, so both producer layouts resolve.
    """
    versions = (usdm.get("study") or {}).get("versions") or []
    if studyversion >= len(versions):
        return []
    version = versions[studyversion]
    bcs = version.get("biomedicalConcepts") or []
    if bcs:
        return bcs
    for design in version.get("studyDesigns") or []:
        if design.get("biomedicalConcepts"):
            return design["biomedicalConcepts"]
    return []
