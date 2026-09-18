"""Build DDS CodeLists for CRF items from CDASH CT and the specialization value lists.

CRF codelists live in their own ``CL.CDASH.*`` / ``CL.CRF.*`` namespace rather than
reusing the Define loader's lists: Define's subset OIDs are hashed against an SDTM
value-level context that means nothing on a CRF, and a CRF list is often a different
subset of the same NCI codelist.

Three shapes come out of this module:

``CL.CDASH.<C>``
    the whole NCI codelist, when the item restricts nothing
``CL.CDASH.<C>.<crf_group_id>``
    a subset, when the specialization's ``value_list`` restricts the codelist; carries
    ``wasDerivedFrom`` pointing at the full list
``CL.CRF.<crf_group_id>.<var>``
    a value list with no NCI codelist behind it at all
"""
from __future__ import annotations

import logging
from typing import Any

from ..constants import (CDASH_CODELIST_OID_PREFIX, CDISC_ORG_SYSTEM,
                         CRF_CODELIST_OID_PREFIX, generate_oid)
from ..sources.crf_specializations import CrfGroup, CrfItem

logger = logging.getLogger(__name__)


class CodeListBuilder:
    """Accumulates the CodeLists referenced by the CRF items it is shown."""

    def __init__(self, cdash_ct: Any, ct_version: str = "") -> None:
        """
        :param cdash_ct: a :class:`CdashCtSource`
        :param ct_version: CT package date recorded as ``codeSystemVersion``
        """
        self.cdash_ct = cdash_ct
        self.ct_version = ct_version
        self.code_lists: dict[str, dict[str, Any]] = {}

    def codelist_for(self, item: CrfItem, group: CrfGroup) -> str | None:
        """Ensure a CodeList exists for an item and return its OID (or ``None``)."""
        if item.codelist:
            return self._nci_codelist(item, group)
        if item.value_list:
            return self._value_list_only(item, group)
        return None

    # -- NCI-backed lists -----------------------------------------------------
    def _nci_codelist(self, item: CrfItem, group: CrfGroup) -> str:
        c_code = item.codelist
        full_oid = generate_oid([CDASH_CODELIST_OID_PREFIX, c_code])
        payload = self.cdash_ct.codelist(c_code)
        name = (payload.get("preferredTerm") or payload.get("submissionValue")
                or item.codelist_submission_value or c_code)
        terms = payload.get("terms") or []

        if full_oid not in self.code_lists:
            self.code_lists[full_oid] = self._make(
                full_oid, name, c_code,
                [self._term(t.get("submissionValue"), t.get("preferredTerm"), t.get("conceptId"))
                 for t in terms if t.get("submissionValue")],
            )

        if not item.value_list:
            return full_oid

        # The specialization restricts the list, so emit a subset derived from the full one.
        subset_oid = generate_oid([CDASH_CODELIST_OID_PREFIX, c_code, group.crf_group_id])
        if subset_oid not in self.code_lists:
            decodes = self.cdash_ct.decode_map(c_code)
            codes = self.cdash_ct.code_map(c_code)
            display = dict(zip(item.value_list, item.value_display_list))
            subset = self._make(
                subset_oid,
                f"{name} ({group.crf_group_id} subset)",
                c_code,
                [self._term(v, display.get(v) or decodes.get(v), codes.get(v))
                 for v in item.value_list],
            )
            subset["wasDerivedFrom"] = full_oid
            self.code_lists[subset_oid] = subset
        return subset_oid

    # -- value-list-only lists ------------------------------------------------
    def _value_list_only(self, item: CrfItem, group: CrfGroup) -> str:
        oid = generate_oid([CRF_CODELIST_OID_PREFIX, group.crf_group_id,
                            item.variable_name or item.crf_item])
        if oid not in self.code_lists:
            display = dict(zip(item.value_list, item.value_display_list))
            self.code_lists[oid] = self._make(
                oid,
                f"{item.variable_name or item.crf_item} values",
                None,
                [self._term(v, display.get(v), None) for v in item.value_list],
            )
        return oid

    # -- helpers --------------------------------------------------------------
    def _make(self, oid: str, name: str, c_code: str | None,
              terms: list[dict[str, Any]]) -> dict[str, Any]:
        codelist: dict[str, Any] = {"OID": oid, "name": name, "dataType": "text",
                                    "codeListItems": terms}
        if c_code:
            coding = {"code": c_code, "codeSystem": CDISC_ORG_SYSTEM}
            if self.ct_version:
                coding["codeSystemVersion"] = self.ct_version
            codelist["coding"] = [coding]
        return codelist

    @staticmethod
    def _term(coded_value: str | None, decode: str | None,
              concept_id: str | None) -> dict[str, Any]:
        term: dict[str, Any] = {"codedValue": coded_value,
                                "decode": decode or coded_value}
        if concept_id:
            term["coding"] = [{"code": concept_id, "codeSystem": CDISC_ORG_SYSTEM}]
        return term

    def as_list(self) -> list[dict[str, Any]]:
        """Every CodeList built, in insertion order."""
        return list(self.code_lists.values())
