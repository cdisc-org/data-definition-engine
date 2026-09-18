"""ODM version targets. Each knows how to build its own odmlib model objects."""
from __future__ import annotations

from generators.crf.targets.base import OdmTarget


def get_target(odm_version: str) -> OdmTarget:
    """Return the target for an ODM version string (``"1.3.2"`` or ``"2.0"``)."""
    if odm_version == "2.0":
        from generators.crf.targets.odm20 import Odm20Target
        return Odm20Target()
    if odm_version == "1.3.2":
        from generators.crf.targets.odm132 import Odm132Target
        return Odm132Target()
    raise ValueError(f"unsupported ODM version: {odm_version!r}; expected 1.3.2 or 2.0")
