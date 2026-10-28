"""Read and write DDS JSON files, and normalize the defects seen in committed ones.

``create_define_json.py`` writes the DDS unwrapped (the MetaDataVersion fields sit at the
JSON root), because ``MetaDataVersion`` is ``tree_root: true`` in the LinkML schema. Some
hand-assembled files wrap it as ``{"metaDataVersion": {...}}``. :func:`load_dds` accepts
either and records which it saw so :func:`save_dds` can write the same shape back.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

WRAPPER_KEY = "metaDataVersion"
# itemGroup types the CRF loader adds; every other itemGroup is a tabulation dataset
CRF_GROUP_TYPES = ("Form", "Section", "Concept")


def load_dds(path: str | Path) -> tuple[dict[str, Any], bool]:
    """Load a DDS JSON file.

    :param path: path to the DDS JSON file
    :return: ``(metadata_version_dict, was_wrapped)``
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and WRAPPER_KEY in data and isinstance(data[WRAPPER_KEY], dict):
        return data[WRAPPER_KEY], True
    return data, False


def save_dds(dds: dict[str, Any], path: str | Path, wrapped: bool = False) -> None:
    """Write a DDS JSON file in the same shape it was read in."""
    payload = {WRAPPER_KEY: dds} if wrapped else dds
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def normalize_dds(dds: dict[str, Any]) -> list[str]:
    """Repair the known defects in committed DDS files, in place.

    Fixes, in order:

    1. ``origin`` written as a dict instead of a single-element list.
    2. ``length: null`` keys, which fail schema validation as a null integer.
    3. the ``annotatedCRF`` (singular) key, renamed to the schema's ``annotatedCRFs``.

    A null ``studyName`` is *reported* but not repaired here — repairing it means
    recomputing every OID, which :func:`loaders.common.usdm_study.study_header` does
    because it needs the USDM.

    :param dds: the DDS MetaDataVersion dict, modified in place
    :return: list of human-readable descriptions of what was changed
    """
    changes: list[str] = []

    for group in dds.get("itemGroups") or []:
        for item in all_items(group):
            if isinstance(item.get("origin"), dict):
                item["origin"] = [item["origin"]]
                changes.append(f"origin dict -> list on {item.get('OID')}")
            if "length" in item and item["length"] is None:
                del item["length"]
                changes.append(f"dropped null length on {item.get('OID')}")

    if "annotatedCRF" in dds and "annotatedCRFs" not in dds:
        dds["annotatedCRFs"] = dds.pop("annotatedCRF")
        changes.append("annotatedCRF -> annotatedCRFs")

    if not dds.get("studyName") or dds.get("studyName") == "None":
        changes.append("studyName is null/None; OIDs contain 'None' (recompute from USDM)")

    return changes


def all_items(group: dict[str, Any]) -> list[dict[str, Any]]:
    """Every item in an itemGroup, including those nested in its slices."""
    items = list(group.get("items") or [])
    for sl in group.get("slices") or []:
        items.extend(all_items(sl))
    return items


def define_items(dds: dict[str, Any]) -> dict[str, tuple[str, str, dict[str, Any], str | None]]:
    """OID -> (dataset, variable, item dict, ValueListDef OID or None) for every Define item.

    Define items are the ``items`` of tabulation itemGroups and of their ``ValueList`` slices;
    the CRF's Form/Section/Concept groups are skipped. The first item with an OID wins.
    """
    found: dict[str, tuple[str, str, dict[str, Any], str | None]] = {}
    for group in dds.get("itemGroups") or []:
        if group.get("type") in CRF_GROUP_TYPES:
            continue
        dataset = group.get("domain") or group.get("name")
        for item in group.get("items") or []:
            if item.get("OID"):
                found.setdefault(item["OID"], (dataset, item.get("name"), item, None))
        for slice_ in group.get("slices") or []:
            if slice_.get("type") != "ValueList":
                continue
            for item in slice_.get("items") or []:
                if item.get("OID"):
                    found.setdefault(item["OID"], (dataset, item.get("name"), item, slice_.get("OID")))
    return found


def find_by_oid(objects: list[dict[str, Any]], oid: str) -> dict[str, Any] | None:
    """Return the first object whose ``OID`` matches, or ``None``."""
    for obj in objects:
        if obj.get("OID") == oid:
            return obj
    return None
