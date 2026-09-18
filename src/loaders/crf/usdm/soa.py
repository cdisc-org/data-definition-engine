"""Read the USDM Schedule of Activities: activities, encounters, epochs and timings.

``create_define_json.py`` never traverses the SoA — the CRF loader is the first consumer,
because forms come from Activities and visits come from Encounters.

Ordering is by the ``previousId``/``nextId`` linked list USDM uses, falling back to list
order when the chain is broken or absent.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Encounter:
    """A USDM Encounter, resolved to the visit metadata the CRF loader needs."""

    id: str
    name: str
    label: str = ""
    description: str = ""
    type_code: str = ""
    type_decode: str = ""
    scheduled_at_id: str | None = None
    epoch_id: str | None = None
    epoch_name: str = ""
    timing: dict[str, Any] = field(default_factory=dict)
    instance_id: str | None = None


@dataclass
class Activity:
    """A USDM Activity, the default unit of form composition."""

    id: str
    name: str
    label: str = ""
    description: str = ""
    biomedical_concept_ids: list[str] = field(default_factory=list)


class SoA:
    """Ordered view over one USDM schedule timeline."""

    def __init__(self, study_design: dict[str, Any], timeline: str | None = None) -> None:
        """
        :param study_design: a USDM studyDesign dict
        :param timeline: timeline name to use; defaults to the one flagged ``mainTimeline``
        """
        self.study_design = study_design or {}
        self.timeline = self._select_timeline(timeline)
        self.epochs = {e["id"]: e for e in self.study_design.get("epochs") or [] if e.get("id")}
        self._timings = {t["id"]: t for t in (self.timeline.get("timings") or []) if t.get("id")}
        self.instances = self.timeline.get("instances") or []
        self.activities = self._ordered_activities()
        self.encounters = self._ordered_encounters()
        self._activity_to_encounters = self._build_activity_binding()

    # -- selection ------------------------------------------------------------
    def _select_timeline(self, timeline: str | None) -> dict[str, Any]:
        timelines = self.study_design.get("scheduleTimelines") or []
        if not timelines:
            logger.warning("USDM study design has no scheduleTimelines")
            return {}
        if timeline:
            for t in timelines:
                if t.get("name") == timeline or t.get("id") == timeline:
                    return t
            logger.warning("timeline %r not found; falling back to the main timeline", timeline)
        for t in timelines:
            if t.get("mainTimeline"):
                return t
        # SoA Workbench labels the main timeline study-specifically, so never match on
        # the literal string "Main Timeline" - fall back to the first one instead.
        logger.warning("no timeline flagged mainTimeline; using the first of %d", len(timelines))
        return timelines[0]

    # -- ordering -------------------------------------------------------------
    @staticmethod
    def _order_by_chain(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Order by the previousId/nextId chain, falling back to list order."""
        by_id = {o["id"]: o for o in objects if o.get("id")}
        if not by_id:
            return list(objects)
        heads = [o for o in objects if o.get("id") and not o.get("previousId")]
        if len(heads) != 1:
            return list(objects)
        ordered: list[dict[str, Any]] = []
        seen: set[str] = set()
        current: dict[str, Any] | None = heads[0]
        while current is not None and current["id"] not in seen:
            ordered.append(current)
            seen.add(current["id"])
            next_id = current.get("nextId")
            current = by_id.get(next_id) if next_id else None
        if len(ordered) != len(by_id):
            # A partial chain would silently drop activities, so prefer list order.
            logger.debug("previousId/nextId chain covered %d of %d; using list order",
                         len(ordered), len(by_id))
            return list(objects)
        return ordered

    def _ordered_activities(self) -> list[Activity]:
        raw = self._order_by_chain(self.study_design.get("activities") or [])
        return [
            Activity(
                id=a["id"],
                name=a.get("name") or a["id"],
                label=a.get("label") or "",
                description=a.get("description") or "",
                biomedical_concept_ids=list(a.get("biomedicalConceptIds") or []),
            )
            for a in raw if a.get("id")
        ]

    def _ordered_encounters(self) -> list[Encounter]:
        raw = self._order_by_chain(self.study_design.get("encounters") or [])
        instance_by_encounter = {
            i["encounterId"]: i for i in self.instances if i.get("encounterId")
        }
        encounters = []
        for e in raw:
            if not e.get("id"):
                continue
            instance = instance_by_encounter.get(e["id"]) or {}
            epoch_id = instance.get("epochId")
            code = e.get("type") or {}
            encounters.append(Encounter(
                id=e["id"],
                name=e.get("name") or e["id"],
                label=e.get("label") or "",
                description=e.get("description") or "",
                type_code=code.get("code") or "",
                type_decode=code.get("decode") or "",
                scheduled_at_id=e.get("scheduledAtId"),
                epoch_id=epoch_id,
                epoch_name=(self.epochs.get(epoch_id) or {}).get("name", "") if epoch_id else "",
                timing=self.encounter_timing(e.get("scheduledAtId")),
                instance_id=instance.get("id"),
            ))
        return encounters

    # -- bindings -------------------------------------------------------------
    def _build_activity_binding(self) -> dict[str, list[str]]:
        """Map activity id -> encounter ids, from ``instances[].activityIds``."""
        binding: dict[str, list[str]] = {}
        for instance in self.instances:
            encounter_id = instance.get("encounterId")
            if not encounter_id:
                continue
            for activity_id in instance.get("activityIds") or []:
                binding.setdefault(activity_id, []).append(encounter_id)
        return binding

    def activity_encounters(self, activity_id: str) -> list[str]:
        """Encounter ids an activity is performed at (empty when SoA has no binding)."""
        return self._activity_to_encounters.get(activity_id, [])

    @property
    def has_activity_binding(self) -> bool:
        """True when at least one instance names an activity.

        Every SoA Workbench 1.6 export seen so far leaves ``activityIds`` empty on every
        instance, which is why StudyEvents come out unbound and the refinement file gets
        a ``studyEvents`` section with candidates.
        """
        return bool(self._activity_to_encounters)

    # -- timing ---------------------------------------------------------------
    def encounter_timing(self, timing_id: str | None) -> dict[str, Any]:
        """Resolve a USDM Timing id to a DDS timing dict."""
        from ..constants import TIMING_TYPE_MAP

        if not timing_id:
            return {}
        timing = self._timings.get(timing_id)
        if not timing:
            return {}
        code = (timing.get("type") or {}).get("code") or ""
        resolved = {
            "type": TIMING_TYPE_MAP.get(code, "Fixed"),
            "value": timing.get("value") or "",
            "isNominal": True,
        }
        if timing.get("valueLabel"):
            resolved["label"] = timing["valueLabel"]
        relative_to = timing.get("relativeToScheduledInstanceId")
        if relative_to:
            resolved["relativeTo"] = relative_to
        return resolved

    def summary(self) -> dict[str, Any]:
        """Counts for the debug dump and the end-of-run report."""
        return {
            "timeline": self.timeline.get("name"),
            "activities": len(self.activities),
            "encounters": len(self.encounters),
            "epochs": len(self.epochs),
            "instances": len(self.instances),
            "has_activity_binding": self.has_activity_binding,
        }
