"""Build DDS StudyEvents (visits) from USDM Encounters.

One StudyEvent per Encounter, ordered by the SoA. The epoch name becomes the event's
``category`` and the Encounter's ``scheduledAtId`` timing becomes its ``occurrence``.

``itemGroups`` — the forms collected at a visit — comes from
``ScheduledActivityInstance.activityIds``. Every SoA Workbench 1.6 export seen so far
leaves that empty on every instance, so events come out unbound and the refinement YAML
carries a ``studyEvents`` section listing candidate forms for a human to bind.
"""
from __future__ import annotations

import logging
from typing import Any

from ..constants import CDISC_ORG_SYSTEM, STUDY_EVENT_OID_PREFIX, generate_oid

logger = logging.getLogger(__name__)


class StudyEventBuilder:
    """Builds the DDS ``studyEvents`` list."""

    def __init__(self, soa: Any) -> None:
        """:param soa: a :class:`loaders.crf.usdm.soa.SoA`"""
        self.soa = soa
        self.unbound: list[str] = []

    def build(self, form_oid_by_activity: dict[str, str]) -> list[dict[str, Any]]:
        """Build one StudyEvent per encounter.

        :param form_oid_by_activity: USDM activity id -> Form ItemGroup OID
        :return: the DDS ``studyEvents`` list
        """
        events: list[dict[str, Any]] = []
        for encounter in self.soa.encounters:
            event = self._build_one(encounter, form_oid_by_activity)
            if not event["itemGroups"]:
                self.unbound.append(event["OID"])
            events.append(event)

        if self.unbound and not self.soa.has_activity_binding:
            logger.warning(
                "no activity-to-visit binding in this USDM export "
                "(every ScheduledActivityInstance.activityIds is empty); "
                "%d StudyEvent(s) are unbound until the refinement file supplies them",
                len(self.unbound),
            )
        return events

    def _build_one(self, encounter: Any,
                   form_oid_by_activity: dict[str, str]) -> dict[str, Any]:
        item_groups: list[str] = []
        for activity_id, form_oid in form_oid_by_activity.items():
            if encounter.id in self.soa.activity_encounters(activity_id):
                item_groups.append(form_oid)

        event: dict[str, Any] = {
            "OID": generate_oid([STUDY_EVENT_OID_PREFIX, encounter.name]),
            "name": encounter.name,
            "label": encounter.label or encounter.name,
            "type": "Scheduled",
            "repeating": False,
            "itemGroups": item_groups,
            "crfEncounterRef": encounter.id,
        }
        if encounter.description:
            event["description"] = encounter.description
        if encounter.epoch_name:
            event["category"] = encounter.epoch_name
        if encounter.timing:
            occurrence: dict[str, Any] = {"timing": encounter.timing}
            if encounter.instance_id:
                occurrence["event"] = encounter.instance_id
            event["occurrence"] = occurrence
        if encounter.type_code:
            event["coding"] = [{
                "code": encounter.type_code,
                "codeSystem": CDISC_ORG_SYSTEM,
                "decode": encounter.type_decode or "Visit",
            }]
        return event
