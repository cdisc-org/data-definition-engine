"""Read a value-level item's where clause, and decide whether it admits a value.

Shared by the CRF loader's SDTM links (``loaders/crf/builders/sdtm_links.py``), the pagerefs loader
and the methods loader. A value-level item's ``applicableWhen`` names where clauses; a where clause
names conditions; a condition holds range checks on items. The DDE writes one where clause per
value-level item, so only the first is read.
"""
from __future__ import annotations

from typing import Any

#: variable -> (comparator, values), e.g. {"VSTESTCD": ("EQ", ("BMI",))}
Where = dict[str, tuple[str, tuple[str, ...]]]


def admits(comparator: str, values: tuple, value: str) -> bool:
    """Whether a where-clause condition admits one value: EQ equals it, IN lists it, NE differs."""
    if comparator == "EQ":
        return value in values[:1]
    if comparator == "IN":
        return value in values
    if comparator == "NE":
        return value not in values
    return False


def item_where(wc_oids: list[str] | None, where_clauses: dict[str, list[str]],
               conditions: dict[str, dict[str, Any]]) -> Where:
    """A value-level item's where clause as variable -> (comparator, values)."""
    out: Where = {}
    for wc_oid in (wc_oids or [])[:1]:   # the first where clause; DDE writes one per item
        for condition_oid in where_clauses.get(wc_oid) or []:
            for check in (conditions.get(condition_oid) or {}).get("rangeChecks") or []:
                variable = str(check.get("item") or "").rsplit(".", 1)[-1]
                if variable:
                    out[variable] = (str(check.get("comparator") or "EQ").upper(),
                                     tuple(str(v) for v in check.get("checkValues") or []))
    return out


class WhereIndex:
    """The where clauses and conditions of a DDS, to read any item's where clause."""

    def __init__(self, dds: dict[str, Any]) -> None:
        self.conditions = {c.get("OID"): c for c in dds.get("conditions") or []}
        self.where_clauses: dict[str, list[str]] = {}
        for wc in dds.get("whereClauses") or []:
            self.where_clauses.setdefault(wc.get("OID"), wc.get("conditions") or [])

    def of(self, item: dict[str, Any]) -> Where:
        """The item's where clause; empty for an item without ``applicableWhen``."""
        return item_where(item.get("applicableWhen"), self.where_clauses, self.conditions)
