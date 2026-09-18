"""Cross-cutting passes over the finished odmlib objects.

Runs after every loader, before the document is assembled: prunes CodeLists nothing
references, and reports the things a human should look at (placeholders that were never
filled in, visits with no forms).
"""
from __future__ import annotations

import logging
from typing import Any

from generators.crf.constants import PLACEHOLDER

logger = logging.getLogger(__name__)


def peek(obj: Any, name: str, default: Any = None) -> Any:
    """Read an odmlib child without creating it.

    ``getattr`` on an unset list-valued element materializes an empty list *at the end*
    of the object's ``__dict__``, and odmlib derives element order from that dict — so an
    innocent ``getattr(event, "ItemGroupRef", None)`` in a read-only inspection pass makes
    the document fail ``validate()`` with an element-order error. Reading ``vars()``
    directly cannot mutate anything.
    """
    return vars(obj).get(name, default)


class PostProcessing:
    """Post-processing over the built CRF objects."""

    def __init__(self, crf_objects: dict[str, Any], template: dict[str, Any],
                 target: Any, prune_codelists: bool = True) -> None:
        self.crf_objects = crf_objects
        self.template = template
        self.target = target
        self.prune_codelists = prune_codelists
        self.warnings: list[str] = []

    def process(self) -> None:
        if self.prune_codelists:
            self._prune_unreferenced_codelists()
        self._report_placeholders()
        self._report_unbound_events()

    def _prune_unreferenced_codelists(self) -> None:
        """Drop CodeLists no emitted ItemDef refers to.

        A combined DDS carries the Define-side lists too; emitting all of them into a CRF
        would leave dangling definitions that bloat the file without being reachable.
        """
        referenced = {
            peek(item, "CodeListRef").CodeListOID
            for item in self.crf_objects.get("ItemDef", [])
            if peek(item, "CodeListRef") is not None
        }
        # Keep any list a kept list derives from, so subsetOf aliases still resolve.
        kept = [cl for cl in self.crf_objects.get("CodeList", []) if cl.OID in referenced]
        derived_from = set()
        for codelist in kept:
            for alias in peek(codelist, "Alias") or []:
                if peek(alias, "Context") == "subsetOf":
                    derived_from.add(alias.Name)
        keep_oids = referenced | derived_from

        before = len(self.crf_objects.get("CodeList", []))
        self.crf_objects["CodeList"] = [
            cl for cl in self.crf_objects.get("CodeList", []) if cl.OID in keep_oids
        ]
        pruned = before - len(self.crf_objects["CodeList"])
        if pruned:
            logger.info("pruned %d CodeList(s) no CRF item references", pruned)

    def _report_placeholders(self) -> None:
        """Warn once per element still carrying the __PLACEHOLDER__ sentinel."""
        found: list[str] = []
        for key in ("ItemDef", "ItemGroupDef", "FormDef"):
            for obj in self.crf_objects.get(key, []):
                if _has_placeholder(obj):
                    found.append(peek(obj, "OID", "?"))
        if found:
            self.warnings.append(
                f"{len(found)} element(s) still contain {PLACEHOLDER}: "
                + ", ".join(found[:10]) + (" ..." if len(found) > 10 else "")
            )
            logger.warning(self.warnings[-1])

    def _report_unbound_events(self) -> None:
        unbound = []
        for event in self.crf_objects.get("StudyEventDef", []):
            refs = (peek(event, "FormRef") or []) + (peek(event, "ItemGroupRef") or [])
            if not refs:
                unbound.append(event.OID)
        if unbound:
            self.warnings.append(
                f"{len(unbound)} StudyEventDef(s) collect no form: "
                + ", ".join(unbound[:10]) + (" ..." if len(unbound) > 10 else "")
            )
            logger.warning(self.warnings[-1])


def _has_placeholder(obj: Any, depth: int = 0) -> bool:
    """True when the sentinel appears anywhere in an odmlib object's content."""
    if depth > 4:
        return False
    for value in vars(obj).values():
        if isinstance(value, str) and PLACEHOLDER in value:
            return True
        if isinstance(value, list):
            if any(_has_placeholder(v, depth + 1) for v in value if hasattr(v, "__dict__")):
                return True
        elif hasattr(value, "__dict__") and _has_placeholder(value, depth + 1):
            return True
    return False
