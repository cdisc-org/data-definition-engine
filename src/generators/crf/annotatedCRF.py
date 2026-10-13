"""Emit the AnnotatedCRF reference and its Leaf, where the ODM version has them.

Only ODM 2.0 has ``AnnotatedCRF``/``Leaf``. In ODM 1.3.2 the target returns ``None`` and
nothing is emitted — the annotations themselves are still present as ``Alias`` elements
on every ItemDef, which is what makes the aCRF rendering possible in both versions.
"""
from __future__ import annotations

from typing import Any

from generators.crf.constants import ACRF_HREF, ACRF_LEAF_ID
from generators.crf.crf_object import CrfObject


class AnnotatedCRF(CrfObject):
    """Create the AnnotatedCRF element from the DDS ``annotatedCRFs`` section."""

    def create_crf_objects(self, template: list[dict[str, Any]],
                           crf_objects: dict[str, Any], target: Any, lang: str) -> None:
        self.lang = lang
        if not template or not hasattr(target, "annotated_crf"):
            return
        reference = template[0]
        acrf = target.annotated_crf(
            reference.get("leafID") or ACRF_LEAF_ID,
            reference.get("href") or ACRF_HREF,
            reference.get("title") or "Annotated CRF",
            crf_objects,
        )
        if acrf is not None:
            crf_objects["AnnotatedCRF"] = acrf
