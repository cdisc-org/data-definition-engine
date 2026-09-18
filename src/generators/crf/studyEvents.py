"""Emit StudyEventDefs and the Protocol that reaches them.

ODM 2.0 removed ``Protocol/StudyEventRef``, so events are only reachable through
``Protocol/StudyEventGroupRef -> StudyEventGroupDef -> StudyEventRef``. The target owns
that difference; this loader just hands it the events and the standards.
"""
from __future__ import annotations

from typing import Any

from generators.crf.crf_object import CrfObject


class StudyEvents(CrfObject):
    """Create StudyEventDef elements and the Protocol."""

    def create_crf_objects(self, template: list[dict[str, Any]],
                           crf_objects: dict[str, Any], target: Any, lang: str) -> None:
        self.lang = lang
        known_forms = crf_objects.get("_form_filter")
        events = []
        for event in template:
            self.require_key(event, "OID", "StudyEvent")
            if known_forms:
                event = dict(event)
                event["itemGroups"] = [f for f in event.get("itemGroups") or []
                                       if f in known_forms]
            events.append(event)
            crf_objects.setdefault("StudyEventDef", []).append(
                target.study_event(event, lang))

        unbound = [e["OID"] for e in events if not e.get("itemGroups")]
        if unbound:
            self.logger.warning(
                "%d StudyEventDef(s) reference no form: %s%s",
                len(unbound), ", ".join(unbound[:5]),
                " ..." if len(unbound) > 5 else "")

        crf_objects["Protocol"] = target.protocol(
            events, crf_objects.get("_standards") or [], crf_objects)
