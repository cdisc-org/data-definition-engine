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
                         SECTION_OID_PREFIX, STD_CDASHIG_OID, YES_NO, generate_oid)
from ..sources.crf_specializations import CrfGroup
from . import sdtm_links

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
        aliases = self._fixed_value_aliases(concept["OID"], group, items)
        if aliases:
            concept["aliases"] = aliases
        return concept

    def _fixed_value_aliases(self, concept_oid: str, group: CrfGroup,
                             items: list[dict[str, Any]]) -> list[dict[str, str]]:
        """The concept's fixed SDTM values as ``SDTM`` and ``SDTMItemOIDs`` aliases.

        A concept fixes values no field collects: its test codes and names, read from its
        items' when-clauses (``VSTESTCD = SYSBP; VSTEST = Systolic Blood Pressure``), and
        the values of its hidden prefilled items (``LBCAT = CHEMISTRY``), which the CRF
        generator does not render. Each gets its Define item link. A hidden item that is
        not prefilled has no value to state and goes to ``mappingReview``.
        """
        define = self.item_builder.define_index
        context = self.item_builder.group_context(group)
        segments: list[str] = []
        links: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        def add(variable: str, value: str) -> None:
            if (variable, value) in seen:
                return
            seen.add((variable, value))
            segments.append(f"{variable} = {value}")
            if define is None:
                return
            dataset = sdtm_links.target_dataset(sdtm_links.Target(variable), group.domain, define)
            own = {k: v for k, v in context.items() if k != variable}
            link = define.link(dataset or "", variable, (), own, group.vlm_group_id or None)
            if link.item:
                if link.as_dict() not in links:
                    links.append(link.as_dict())
            else:
                self._review(concept_oid, f"{variable} = {value}", f"{dataset}.{variable}",
                             link.basis)

        for spec in group.items:
            for target in sdtm_links.parse_annotation(spec.sdtm_annotation).targets:
                for condition in target.conditions:
                    name_variable = sdtm_links.paired_name_variable(condition.variable)
                    if condition.comparator != "EQ" or len(condition.values) != 1 \
                            or not name_variable:
                        continue
                    add(condition.variable, condition.values[0])
                    if define is not None:
                        dataset = sdtm_links.target_dataset(
                            sdtm_links.Target(condition.variable), group.domain, define)
                        name = define.decode(dataset or "", condition.variable,
                                             condition.values[0])
                        if name:
                            add(name_variable, name)

        for spec, item in zip(group.items, items):
            if not YES_NO.get(spec.display_hidden.upper(), False):
                continue
            annotation = (item.get("crfSdtmTarget") or {}).get("annotation") or ""
            origin = next(iter(item.get("origin") or []), {}).get("type")
            if not spec.prepopulated_term or origin != "Protocol":
                if annotation and not sdtm_links.parse_annotation(annotation).not_submitted:
                    self._review(concept_oid, annotation, "",
                                 f"hidden item {item['OID']} is not prefilled "
                                 f"(origin {origin}), so the CRF states no value for it")
                continue
            targets = sdtm_links.parse_annotation(annotation).targets
            direct = (len(targets) == 1 and not targets[0].conditions and not targets[0].qnam
                      and (targets[0].value is not None or targets[0].variable == spec.variable_name))
            if not direct:
                # MHONGO prefilled Y feeds MHENRF;MHENRTPT;MHENTPT through a derivation: the
                # prefilled value is the CDASH field's, not an SDTM value
                self._review(concept_oid, annotation, "",
                             f"hidden item {item['OID']} is prefilled {spec.prepopulated_term!r} but "
                             "does not map directly to one SDTM variable, so its SDTM value is not stated")
                continue
            add(targets[0].variable, targets[0].value or spec.prepopulated_term)

        aliases = []
        if segments:
            aliases.append({"context": "SDTM", "name": "; ".join(segments)})
        pairs = sdtm_links.oid_pairs(links)
        if pairs:
            aliases.append({"context": "SDTMItemOIDs", "name": pairs})
        return aliases

    def _review(self, oid: str, annotation: str, target: str, reason: str) -> None:
        entry = {"item": oid, "annotation": annotation, "target": target, "reason": reason}
        if entry not in self.item_builder.mapping_review:
            self.item_builder.mapping_review.append(entry)

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
