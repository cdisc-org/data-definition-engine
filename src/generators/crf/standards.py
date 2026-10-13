"""Emit the Standards element, where the ODM version has one.

ODM 2.0 closes ``Standard/@Name`` to a Define-XML-oriented enumeration that does not
include ``CDASHIG``, so a CDASHIG standard cannot be a native ``Standard`` element there;
the target emits it as ``Protocol/Alias Context=Standard`` instead. ODM 1.3.2 has no
``Standards`` element at all, so every standard takes that route.
"""
from __future__ import annotations

from typing import Any

from generators.crf.constants import ODM20_STANDARD_NAMES
from generators.crf.crf_object import CrfObject


class Standards(CrfObject):
    """Create the Standards container and stash the list for the Protocol."""

    def create_crf_objects(self, template: list[dict[str, Any]],
                           crf_objects: dict[str, Any], target: Any, lang: str) -> None:
        self.lang = lang
        # studyEvents runs later and needs these for the Protocol aliases.
        crf_objects["_standards"] = template
        crf_objects["Standards"] = target.standards(template, crf_objects)

        if target.version == "2.0":
            aliased = [s.get("name") for s in template
                       if s.get("name") not in ODM20_STANDARD_NAMES]
            if aliased:
                self.logger.info(
                    "ODM 2.0 Standard/@Name has no value for %s; emitting as "
                    "Protocol/Alias Context=Standard", ", ".join(map(str, aliased)))
