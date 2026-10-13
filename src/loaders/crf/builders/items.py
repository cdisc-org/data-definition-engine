"""Build DDS Items for CRF fields.

Each CRF specialization row becomes one DDS Item under ``IT.CRF.<crf_item>``. CDASHIG
supplies the prose the specialization leaves blank (definition, completion instructions,
implementation and mapping notes); the specialization stays authoritative for anything it
does fill in.

Items are deduplicated by OID because a ``crf_item`` such as ``VSDAT`` is shared by every
concept on the form. A genuine conflict — same OID, different question or data type —
is reported rather than silently resolved.
"""
from __future__ import annotations

import logging
from typing import Any

from ..constants import (BC_SYSTEM, CDISC_ORG_SYSTEM, CRF_ITEM_OID_PREFIX, DATATYPE_MAP,
                         ORIGIN_ASSIGNED, ORIGIN_COLLECTED, ORIGIN_PROTOCOL, PLACEHOLDER,
                         YES_NO, generate_oid)
from ..sources.crf_specializations import CrfGroup, CrfItem

logger = logging.getLogger(__name__)

UNITS_SUFFIXES = ("ORRESU", "ORRESU_STD", "STRESU")
RESULT_SUFFIXES = ("ORRES", "STRESN", "STRESC")


class ItemBuilder:
    """Accumulates DDS Items across every CRF group processed."""

    def __init__(self, cdashig: Any, codelists: Any,
                 sdtm_item_oids: set[str] | None = None) -> None:
        """
        :param cdashig: a :class:`CdashigSource`
        :param codelists: a :class:`CodeListBuilder`
        :param sdtm_item_oids: OIDs of the Define-side items already in the DDS, used to
            resolve ``crfSdtmTarget.items`` references to real targets
        """
        self.cdashig = cdashig
        self.codelists = codelists
        self.sdtm_item_oids = sdtm_item_oids or set()
        self.items: dict[str, dict[str, Any]] = {}
        self.conflicts: list[str] = []
        self.placeholders: set[str] = set()
        #: OID -> the CRF group that first defined it, for conflict messages.
        self.first_group: dict[str, str] = {}
        #: OID -> whether the stored question came from the specialization ("spec") or
        #: was filled in from CDASHIG ("cdashig"). Two spec-authored questions that
        #: disagree are a real conflict; a spec one and a CDASHIG one are not.
        self.question_source: dict[str, str] = {}

    def build_group_items(self, group: CrfGroup,
                          property_by_dec: dict[str, str] | None = None
                          ) -> list[dict[str, Any]]:
        """Build every item of a CRF group, in order.

        ``ItemGroup.items`` is ``inlined_as_list`` in the DDS model, so the returned
        dicts are inlined into the Concept group. An item shared by several concepts
        therefore appears once per concept; the generator deduplicates ItemDefs by OID
        when it emits them, the same way the Define generator handles value-list slices.
        """
        property_by_dec = property_by_dec or {}
        built: list[dict[str, Any]] = []
        units_by_base = self._units_index(group)
        for spec_item in group.items:
            built.append(self._build(spec_item, group, units_by_base, property_by_dec))
        return built

    @staticmethod
    def _units_index(group: CrfGroup) -> dict[str, str]:
        """Map a result variable's base name to the sibling unit item's OID.

        ``SYSBP_VSORRES`` pairs with ``SYSBP_VSORRESU``: the unit item's name is the
        result item's name plus ``U``.
        """
        by_name = {i.crf_item: i for i in group.items}
        index: dict[str, str] = {}
        for item in group.items:
            if not any(item.crf_item.endswith(s) for s in RESULT_SUFFIXES):
                continue
            unit = by_name.get(item.crf_item + "U")
            if unit is not None:
                index[item.crf_item] = generate_oid([CRF_ITEM_OID_PREFIX, unit.crf_item])
        return index

    def _build(self, spec: CrfItem, group: CrfGroup, units_by_base: dict[str, str],
               property_by_dec: dict[str, str]) -> dict[str, Any]:
        oid = generate_oid([CRF_ITEM_OID_PREFIX, spec.crf_item])
        field = self.cdashig.lookup(group.domain, spec.variable_name, group.scenario)
        item = self._assemble(oid, spec, group, field, units_by_base, property_by_dec)

        source = "spec" if spec.question_text else "cdashig"

        existing = self.items.get(oid)
        if existing is None:
            self.items[oid] = item
            self.first_group[oid] = group.crf_group_id
            self.question_source[oid] = source
            # The same dict object is inlined into every concept that collects this
            # item, so a later merge is visible from all of them.
            return item

        # The same crf_item is reused across concepts of a domain (every Vital Signs
        # concept collects VSDAT). Most repeats differ only in that one row leaves a
        # field blank, so complementary definitions are merged into the shared item.
        if self._reconcilable(existing, item, oid, source):
            self._merge(existing, item)
            # A specialization-authored question outranks one filled in from CDASHIG.
            if source == "spec" and self.question_source.get(oid) == "cdashig":
                if item.get("question"):
                    existing["question"] = item["question"]
                    self.question_source[oid] = "spec"
            return existing

        # A genuine disagreement means these are different fields wearing the same CDASH
        # name. Give this one a concept-scoped OID rather than silently showing the wrong
        # question on the form, and record it in the run summary.
        scoped_oid = generate_oid([CRF_ITEM_OID_PREFIX, group.crf_group_id, spec.crf_item])
        self.conflicts.append(
            f"{oid}: {group.crf_group_id} disagrees with "
            f"{self.first_group.get(oid, '?')}; emitted separately as {scoped_oid}"
        )
        if scoped_oid not in self.items:
            item["OID"] = scoped_oid
            self.items[scoped_oid] = item
            self.first_group[scoped_oid] = group.crf_group_id
        return self.items[scoped_oid]

    def _reconcilable(self, existing: dict[str, Any], candidate: dict[str, Any],
                      oid: str, source: str) -> bool:
        """True when two definitions of one OID can be merged rather than split.

        They can when neither states a *different* non-empty value for the fields that
        change how the answer is stored. Two exceptions keep this from splitting fields
        that are plainly the same:

        * ``prompt`` is a short display label that sources word differently ("(Date)" vs
          "Date of Assessment") for one field, so it never triggers a split.
        * a ``question`` only counts as disagreeing when **both** wordings were authored
          in the specialization. One spec wording against a CDASHIG fallback is the same
          question phrased by two sources, not two questions.
        """
        for key in ("dataType", "codeList", "unitsItem"):
            left, right = existing.get(key), candidate.get(key)
            if left in (None, "", PLACEHOLDER) or right in (None, "", PLACEHOLDER):
                continue
            if left != right:
                return False

        left, right = existing.get("question"), candidate.get("question")
        if (left not in (None, "", PLACEHOLDER) and right not in (None, "", PLACEHOLDER)
                and left != right
                and source == "spec" and self.question_source.get(oid) == "spec"):
            return False
        return True

    def _merge(self, existing: dict[str, Any], candidate: dict[str, Any]) -> None:
        """Fill fields the existing definition leaves empty from the candidate."""
        for key, value in candidate.items():
            if key == "OID" or value in (None, "", [], {}):
                continue
            current = existing.get(key)
            if current in (None, "", [], {}, PLACEHOLDER):
                existing[key] = value
                if key == "question":
                    self.placeholders.discard(existing["OID"])

    def _assemble(self, oid: str, spec: CrfItem, group: CrfGroup, field: dict[str, Any],
                  units_by_base: dict[str, str],
                  property_by_dec: dict[str, str]) -> dict[str, Any]:
        derived = YES_NO.get(spec.derived_variable.upper(), False)
        hidden = YES_NO.get(spec.display_hidden.upper(), False)
        mandatory = YES_NO.get(spec.mandatory_variable.upper(), False)

        item: dict[str, Any] = {
            "OID": oid,
            "name": spec.crf_item,
            "mandatory": mandatory,
            "dataType": DATATYPE_MAP.get(spec.data_type.lower(), "text"),
        }

        label = field.get("label") or spec.prompt or spec.variable_name
        if label:
            item["description"] = label

        # Question and prompt are kept distinct even when only one is populated. Copying
        # a prompt into the question field would make two rows that merely fill different
        # columns of the same field look like two different fields.
        question = spec.question_text or field.get("questionText")
        prompt = spec.prompt or field.get("prompt")
        if question:
            item["question"] = question
        if prompt:
            item["prompt"] = prompt
        if not question and not prompt:
            item["question"] = PLACEHOLDER
            self.placeholders.add(oid)

        instructions = spec.completion_instructions or field.get("completionInstructions")
        if instructions:
            item["crfCompletionInstructions"] = instructions
        if field.get("definition"):
            item["definition"] = field["definition"]
        if field.get("implementationNotes"):
            item["implementationNotes"] = field["implementationNotes"]
        if field.get("mappingInstructions"):
            item["mappingInstructions"] = field["mappingInstructions"]
        if derived and spec.derivation_description:
            item["cdiscNotes"] = spec.derivation_description

        if spec.length:
            try:
                item["length"] = int(spec.length)
            except ValueError:
                pass
        if spec.significant_digits:
            try:
                item["significantDigits"] = int(spec.significant_digits)
            except ValueError:
                pass

        codelist_oid = self.codelists.codelist_for(spec, group)
        if codelist_oid:
            item["codeList"] = codelist_oid

        units_oid = units_by_base.get(spec.crf_item)
        if units_oid:
            item["unitsItem"] = units_oid

        if spec.prepopulated_term:
            item["preSpecifiedValue"] = spec.prepopulated_term
            if spec.prepopulated_code:
                item["crfPrepopulatedCoding"] = {
                    "code": spec.prepopulated_code,
                    "codeSystem": CDISC_ORG_SYSTEM,
                    "decode": spec.prepopulated_term,
                }

        item["origin"] = [self._origin(spec, derived)]

        if spec.dec_id:
            item["coding"] = [{"code": spec.dec_id, "codeSystem": CDISC_ORG_SYSTEM}]
            concept_property = property_by_dec.get(spec.dec_id)
            if concept_property:
                item["conceptProperty"] = concept_property

        if spec.variable_name:
            item["aliases"] = [{"context": "CDASH", "name": spec.variable_name}]

        sdtm_target = self._sdtm_target(spec, group)
        if sdtm_target:
            item["crfSdtmTarget"] = sdtm_target

        if spec.selection_type:
            item["crfSelectionType"] = spec.selection_type
        if hidden:
            item["crfDisplayHidden"] = True
        if derived:
            item["crfDerived"] = True

        return item

    @staticmethod
    def _origin(spec: CrfItem, derived: bool) -> dict[str, str]:
        if derived:
            return dict(ORIGIN_ASSIGNED)
        if spec.prepopulated_term:
            return dict(ORIGIN_PROTOCOL)
        return dict(ORIGIN_COLLECTED)

    def _sdtm_target(self, spec: CrfItem, group: CrfGroup) -> dict[str, Any] | None:
        if not spec.sdtm_annotation and not spec.sdtm_target_variable:
            return None
        target: dict[str, Any] = {}
        if spec.sdtm_annotation:
            target["annotation"] = spec.sdtm_annotation
        if spec.sdtm_target_variable:
            target["variables"] = list(spec.sdtm_target_variable)
            resolved = [
                oid for oid in
                (generate_oid(["IT", group.domain, v]) for v in spec.sdtm_target_variable)
                if oid in self.sdtm_item_oids
            ]
            if resolved:
                target["items"] = resolved
        return target or None

    def as_list(self) -> list[dict[str, Any]]:
        """Every distinct Item built."""
        return list(self.items.values())

    def by_oid(self, oid: str) -> dict[str, Any] | None:
        return self.items.get(oid)
