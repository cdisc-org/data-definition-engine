"""CDASH controlled terminology from the CDISC Library, with an SDTM CT fallback.

CRF items name a codelist by NCI C-code. The terms come from the CDASH CT package; a
handful of lists are published only in SDTM CT, so the SDTM package for the same date is
the fallback rather than an error.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class CdashCtSource:
    """Codelist terms keyed by NCI C-code."""

    def __init__(self, client: Any, cdashct: str, sdtmct: str | None = None) -> None:
        """
        :param client: a CDISC Library client (optionally cache-wrapped)
        :param cdashct: CDASH CT package date, ``yyyy-mm-dd``
        :param sdtmct: SDTM CT package date used as fallback, ``yyyy-mm-dd``
        """
        self.client = client
        self.cdashct = cdashct
        self.sdtmct = sdtmct
        self._cache: dict[str, dict[str, Any]] = {}
        self.missing: set[str] = set()

    def codelist(self, c_code: str) -> dict[str, Any]:
        """Return the codelist payload for a C-code, or ``{}`` when not found.

        The payload is the Library's codelist JSON: ``submissionValue``, ``preferredTerm``
        and a ``terms`` list of ``{conceptId, submissionValue, preferredTerm, ...}``.
        """
        if not c_code:
            return {}
        if c_code in self._cache:
            return self._cache[c_code]

        payload = self._fetch(f"cdashct-{self.cdashct}", c_code)
        if not payload and self.sdtmct:
            payload = self._fetch(f"sdtmct-{self.sdtmct}", c_code)
            if payload:
                logger.info("codelist %s came from SDTM CT (not in CDASH CT)", c_code)
        if not payload:
            self.missing.add(c_code)
        self._cache[c_code] = payload
        return payload

    def terms(self, c_code: str) -> list[dict[str, Any]]:
        """Return just the terms of a codelist."""
        return (self.codelist(c_code) or {}).get("terms") or []

    def decode_map(self, c_code: str) -> dict[str, str]:
        """Map submission value -> preferred term for a codelist."""
        return {
            t.get("submissionValue"): t.get("preferredTerm") or t.get("submissionValue")
            for t in self.terms(c_code) if t.get("submissionValue")
        }

    def code_map(self, c_code: str) -> dict[str, str]:
        """Map submission value -> NCI concept id for a codelist."""
        return {
            t.get("submissionValue"): t.get("conceptId")
            for t in self.terms(c_code) if t.get("submissionValue") and t.get("conceptId")
        }

    def _fetch(self, package: str, c_code: str) -> dict[str, Any]:
        try:
            return self.client.get_api_json(f"/mdr/ct/packages/{package}/codelists/{c_code}") or {}
        except Exception as exc:  # noqa: BLE001 - a miss is expected for some lists
            logger.debug("codelist %s not in %s: %s", c_code, package, exc)
            return {}
