"""Shared helpers for the CRF generator's loader classes.

Mirrors ``src/generators/define/define_object.DefineObject``. The two are deliberately
separate copies rather than a shared base: the Define generator uses flat top-level
imports and only resolves when its own directory is the working directory, so importing
across the two would force a layout change there. The duplication is ~40 lines and is
recorded as debt in this package's README.
"""
from __future__ import annotations

import logging
from abc import ABC
from typing import Any

from generators.crf.constants import DEFAULT_LANGUAGE


class CrfObject(ABC):
    """Abstract base class for the CRF generator's loader classes."""

    def __init__(self) -> None:
        self.lang: str = DEFAULT_LANGUAGE
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)

    def require_key(self, obj: dict[str, Any], key: str, context: str = "") -> Any:
        """Get a required key, raising a ValueError that names where it was missing.

        :param obj: dictionary to read from
        :param key: key name to retrieve
        :param context: what was being built, for the error message
        :raises ValueError: when the key is absent
        """
        if key not in obj:
            context_str = f" in {context}" if context else ""
            raise ValueError(f"Required field '{key}' missing{context_str}")
        return obj[key]

    def generate_oid(self, descriptors: list[str]) -> str:
        """Join descriptors into an OID, uppercased with spaces as hyphens."""
        parts = [str(d) for d in descriptors if d not in (None, "")]
        if len(parts) > 1 and parts[1].startswith(parts[0] + "."):
            oid = ".".join(parts[1:])
        else:
            oid = ".".join(parts)
        return oid.upper().replace(" ", "-")

    def find_object(self, objects: list[Any], oid: str) -> Any | None:
        """Find an object in a list by its ``OID`` attribute."""
        for obj in objects:
            if getattr(obj, "OID", None) == oid:
                return obj
        return None

    def create_crf_objects(self, template: Any, crf_objects: dict[str, Any],
                           target: Any, lang: str) -> None:
        """The loader contract: build odmlib objects into ``crf_objects`` in place.

        :param template: the DDS section this loader owns
        :param crf_objects: shared dict of lists, mutated in place
        :param target: the :class:`OdmTarget` for the requested ODM version
        :param lang: xml:lang for TranslatedText
        """
        raise NotImplementedError
