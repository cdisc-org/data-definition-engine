"""CDASHIG field metadata from the CDISC Library.

The CRF specialization file carries question text and prompts but leaves definitions,
completion instructions, implementation notes and mapping instructions mostly empty.
CDASHIG fills those in. Fields are fetched once per domain and indexed by variable name;
class-level fields (whose names carry a ``--`` domain placeholder) are the fallback.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

FIELD_KEYS = ("definition", "questionText", "prompt", "completionInstructions",
              "implementationNotes", "mappingInstructions", "label", "simpleDatatype",
              "core", "codelist")


class CdashigSource:
    """Index of CDASHIG fields by domain, scenario and class."""

    def __init__(self, client: Any, version: str = "2.3") -> None:
        """
        :param client: a CDISC Library client (optionally cache-wrapped)
        :param version: CDASHIG version, e.g. ``"2.3"``
        """
        self.client = client
        self.version = version
        self.version_path = version.replace(".", "-")
        self._domains: dict[str, dict[str, dict[str, Any]]] = {}
        self._scenarios: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
        self._scenario_links: dict[str, list[dict[str, Any]]] = {}
        self.missing_domains: set[str] = set()

    def domain_fields(self, domain: str) -> dict[str, dict[str, Any]]:
        """Fields for a CDASHIG domain, indexed by field name.

        Note the endpoint: ``/domains/{D}`` embeds each field's full content, whereas
        ``/domains/{D}/fields`` returns only ``_links`` href stubs and would need one
        request per field.
        """
        domain = (domain or "").upper()
        if not domain:
            return {}
        if domain not in self._domains:
            path = f"/mdr/cdashig/{self.version_path}/domains/{domain}"
            self._domains[domain] = self._fetch(path, f"domain {domain}")
        return self._domains[domain]

    def scenario_fields(self, domain: str, scenario: str) -> dict[str, dict[str, Any]]:
        """Fields for a CDASHIG scenario, indexed by field name.

        Scenario paths are not derivable from the scenario name — they are published as
        ``/scenarios/<DOMAIN>.<Name>`` with the spaces removed and inconsistent casing —
        so the domain's ``_links.scenarios`` are read and matched instead of guessed.
        """
        domain = (domain or "").upper()
        if not domain or not scenario:
            return {}
        key = (domain, scenario)
        if key in self._scenarios:
            return self._scenarios[key]

        href = self._scenario_href(domain, scenario)
        if not href:
            logger.info("CDASHIG domain %s publishes no scenario matching %r", domain, scenario)
            self._scenarios[key] = {}
        else:
            self._scenarios[key] = self._fetch(href, f"scenario {domain}/{scenario}")
        return self._scenarios[key]

    def _scenario_href(self, domain: str, scenario: str) -> str | None:
        """Match a CRF specialization scenario name to a published scenario href."""
        if domain not in self._scenario_links:
            path = f"/mdr/cdashig/{self.version_path}/domains/{domain}"
            try:
                payload = self.client.get_api_json(path) or {}
            except Exception:  # noqa: BLE001 - a missing domain is a soft miss
                payload = {}
            self._scenario_links[domain] = (payload.get("_links") or {}).get("scenarios") or []

        wanted = _normalize(scenario)
        for link in self._scenario_links[domain]:
            href = link.get("href") or ""
            suffix = href.rsplit("/", 1)[-1]
            # "VS.HorizontalGeneric" -> compare against "HorizontalGeneric" and the title
            name = suffix.split(".", 1)[-1]
            if wanted in (_normalize(name), _normalize(link.get("title") or ""),
                          _normalize(suffix)):
                return href
        return None

    def lookup(self, domain: str, variable_name: str,
               scenario: str = "") -> dict[str, Any]:
        """Find one CDASHIG field.

        Tries the scenario fields first when the group names a scenario, then the domain
        fields, then the class-level ``--``-prefixed generic form of the variable
        (``VSORRES`` -> ``--ORRES``). Returns ``{}`` when nothing matches.
        """
        if not variable_name:
            return {}
        if scenario:
            hit = self.scenario_fields(domain, scenario).get(variable_name)
            if hit:
                return hit
        fields = self.domain_fields(domain)
        hit = fields.get(variable_name)
        if hit:
            return hit
        # Class-level fields are published with a -- domain placeholder.
        domain_upper = (domain or "").upper()
        if domain_upper and variable_name.upper().startswith(domain_upper):
            generic = "--" + variable_name[len(domain_upper):]
            hit = fields.get(generic)
            if hit:
                return hit
        return {}

    def _fetch(self, path: str, label: str) -> dict[str, dict[str, Any]]:
        try:
            payload = self.client.get_api_json(path)
        except Exception as exc:  # noqa: BLE001 - any Library failure is a soft miss
            logger.warning("CDASHIG %s not available (%s): %s", label, path, exc)
            self.missing_domains.add(label)
            return {}
        fields = (payload or {}).get("fields") or []
        index = {f.get("name"): f for f in fields if f.get("name")}
        logger.info("CDASHIG %s: %d field(s)", label, len(index))
        return index


def _normalize(text: str) -> str:
    """Casefold and strip separators so scenario names compare reliably."""
    return "".join(c for c in (text or "").lower() if c.isalnum())
