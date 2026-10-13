"""Build the Form -> Section -> Concept ItemGroup tree.

The default composition is one Form per USDM Activity that has at least one covered
Biomedical Concept. Each Form gets a single default Section holding one Concept group per
resolved CRF specialization, in the Activity's ``biomedicalConceptIds`` order. Sponsors
refine that layout through the CRF refinement YAML rather than in code.

The nesting uses ``ItemGroup.slices``, the same recursive container the Define loader uses
for value-level metadata — a Form's slices are its Sections, a Section's slices are its
Concepts. ``type`` is what distinguishes them.
"""
from __future__ import annotations

import logging
from typing import Any

from ..constants import (BC_SYSTEM, CONCEPT_OID_PREFIX, CRF_PROFILE_URI, CRF_SPEC_SYSTEM,
                         FORM_OID_PREFIX, PLACEHOLDER, SDTM_DSS_SYSTEM,
                         SECTION_OID_PREFIX, STD_CDASHIG_OID, generate_oid)
from ..sources.crf_specializations import CrfGroup

logger = logging.getLogger(__name__)


class FormBuilder:
    """Builds Form/Section/Concept ItemGroups for the resolved activities."""

    def __init__(self, item_builder: Any, package_date: str = "") -> None:
        """
        :param item_builder: an :class:`ItemBuilder`
        :param package_date: CRF specialization package date, recorded on the Coding
        """
        self.item_builder = item_builder
        self.package_date = package_date
        self.forms: list[dict[str, Any]] = []

    def build_form(self, activity: Any, resolutions: list[dict[str, Any]],
                   property_by_dec: dict[str, str] | None = None) -> dict[str, Any]:
        """Build one Form for an activity.

        :param activity: a :class:`loaders.crf.usdm.soa.Activity`
        :param resolutions: ordered ``{"group": CrfGroup, "concept_oid": str|None,
            "bc_name": str}`` entries, one per covered Biomedical Concept
        :param property_by_dec: DEC C-code -> conceptProperty OID, for item traceability
        """
        form_oid = generate_oid([FORM_OID_PREFIX, activity.name])
        section_oid = generate_oid([SECTION_OID_PREFIX, activity.name, "1"])

        concepts = [
            self._build_concept(r, property_by_dec or {})
            for r in resolutions
        ]
        domains = sorted({r["group"].domain for r in resolutions if r["group"].domain})

        section: dict[str, Any] = {
            "OID": section_oid,
            "name": activity.label or activity.name.title(),
            "label": activity.label or activity.name.title(),
            "type": "Section",
            "repeating": "No",
            "mandatory": True,
            "crfSectionInstructions": PLACEHOLDER,
            "slices": concepts,
        }

        form: dict[str, Any] = {
            "OID": form_oid,
            "name": activity.name,
            "label": activity.label or activity.name.title(),
            "description": activity.description or activity.label or activity.name,
            "type": "Form",
            "repeating": "No",
            "mandatory": True,
            "standard": STD_CDASHIG_OID,
            "profile": [CRF_PROFILE_URI],
            "crfActivityRef": activity.id,
            "aliases": [{"context": "USDM", "name": activity.id}],
            "slices": [section],
        }
        if domains:
            form["aliases"].insert(0, {"context": "SDTM", "name": ", ".join(domains)})
        if len(domains) == 1:
            form["domain"] = domains[0]

        self.forms.append(form)
        return form

    def _build_concept(self, resolution: dict[str, Any],
                       property_by_dec: dict[str, str]) -> dict[str, Any]:
        group: CrfGroup = resolution["group"]
        items = self.item_builder.build_group_items(group, property_by_dec)

        concept: dict[str, Any] = {
            "OID": generate_oid([CONCEPT_OID_PREFIX, group.crf_group_id]),
            "name": group.short_name or group.crf_group_id,
            "label": group.short_name or group.crf_group_id,
            "type": "Concept",
            # A Normalized specialization collects one row per test, so the group repeats.
            "repeating": "Simple" if group.is_normalized else "No",
            "mandatory": True,
            "standard": STD_CDASHIG_OID,
            "items": items,
            "coding": self._coding(resolution, group),
            "crfSpecializationRef": f"/mdr/specializations/crf/specializations/{group.crf_group_id}",
        }
        if group.domain:
            concept["domain"] = group.domain
        if group.implementation_option:
            concept["crfImplementationOption"] = group.implementation_option
        if group.scenario:
            concept["crfScenario"] = group.scenario
        if resolution.get("concept_oid"):
            concept["implementsConcept"] = resolution["concept_oid"]
        return concept

    def _coding(self, resolution: dict[str, Any], group: CrfGroup) -> list[dict[str, Any]]:
        coding: list[dict[str, Any]] = []
        if group.bc_id:
            coding.append({"code": group.bc_id, "codeSystem": BC_SYSTEM,
                           "decode": resolution.get("bc_name") or group.short_name})
        if group.vlm_group_id:
            coding.append({"code": group.vlm_group_id, "codeSystem": SDTM_DSS_SYSTEM})
        entry = {"code": group.crf_group_id, "codeSystem": CRF_SPEC_SYSTEM}
        if group.package_date or self.package_date:
            entry["codeSystemVersion"] = group.package_date or self.package_date
        coding.append(entry)
        return coding
