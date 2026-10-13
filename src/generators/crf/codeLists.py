"""Emit CodeList elements, optionally pruning the ones no CRF item references."""
from __future__ import annotations

from typing import Any

from generators.crf.crf_object import CrfObject


class CodeLists(CrfObject):
    """Create CodeList elements from the DDS ``codeLists`` section."""

    def create_crf_objects(self, template: list[dict[str, Any]],
                           crf_objects: dict[str, Any], target: Any, lang: str) -> None:
        self.lang = lang
        for codelist in template:
            oid = self.require_key(codelist, "OID", "CodeList")
            if self.find_object(crf_objects["CodeList"], oid) is not None:
                continue
            crf_objects["CodeList"].append(target.codelist(codelist, lang))
