"""``define-patch.yaml`` read, applied, collected and written outside the Define loader.

Stage A (``create_define_json.py``) applies this file. In the pipeline, stage F (the defaults
loader) rewrites it once the defaults are filled, so it lists only what is still open plus every
value a person already answered. The format is Stage A's, so Stage A's ``--apply_patch`` reads the
rewritten file unchanged:

* ``itemGroups`` — OID -> name, description, domain, purpose, structure, standard, keySequence;
* ``items`` — OID -> name, description, role, dataType, length, significantDigits, and origin
  (a list of ``{type, source}``);
* ``codeLists`` — OID -> codeListItems (``{codedValue, decode}``).

The collection rules follow ``create_define_json``'s ``_collect_itemgroup_placeholders`` and
``_collect_item_placeholders``, with two deliberate differences: ``length`` is listed only for
text, integer and float items (the types the Define generator gives a Length), and ``standard``
is not listed when the group has a ``standardOID`` (the key the DDS uses).
"""
from __future__ import annotations

import copy
from datetime import date
from pathlib import Path
from typing import Any

from . import dds_io
from .patch import PLACEHOLDER, is_placeholder, load_patch, write_patch_file, yaml_list, yaml_scalar

SECTIONS = ("itemGroups", "items", "codeLists")
GROUP_FIELDS = ("name", "description", "domain", "purpose", "structure", "standard")
ITEM_TEXT_FIELDS = ("name", "description", "role", "dataType")
LENGTH_TYPES = ("text", "integer", "float")

Answers = dict[str, dict[str, dict[str, Any]]]


def empty() -> Answers:
    return {section: {} for section in SECTIONS}


def tabulation_groups(dds: dict[str, Any]) -> list[dict[str, Any]]:
    return [g for g in dds.get("itemGroups") or [] if g.get("type") not in dds_io.CRF_GROUP_TYPES]


def origin_open(origins: Any) -> bool:
    """Whether an origin list has an entry whose type or source is still a placeholder.
    A missing origin is not open: the pagerefs loader removes a value-list parent's origin."""
    return isinstance(origins, list) and any(
        isinstance(o, dict) and (is_placeholder(o.get("type")) or is_placeholder(o.get("source")))
        for o in origins)


def key_sequence_open(value: Any) -> bool:
    return not isinstance(value, list) or not value or any(is_placeholder(v) for v in value)


def resolved_origin(value: Any) -> list[dict[str, Any]]:
    """The fully answered entries of a patch origin (a dict is read as a one-entry list)."""
    entries = [value] if isinstance(value, dict) else value if isinstance(value, list) else []
    return [{"type": e["type"], "source": e["source"]} for e in entries if isinstance(e, dict)
            and not is_placeholder(e.get("type")) and not is_placeholder(e.get("source"))]


# -- reading -------------------------------------------------------------------
def read_answers(path: str | Path | None) -> Answers:
    """The answered values of a define patch, by section and OID (empty when the file is absent)."""
    answers = empty()
    if not path or not Path(path).exists():
        return answers
    content = load_patch(path) or {}
    for oid, fields in (content.get("itemGroups") or {}).items():
        if not isinstance(fields, dict):
            continue
        got = {f: fields[f] for f in GROUP_FIELDS if f in fields and not is_placeholder(fields[f])}
        if "keySequence" in fields and not key_sequence_open(fields["keySequence"]):
            got["keySequence"] = list(fields["keySequence"])
        if got:
            answers["itemGroups"][str(oid)] = got
    for oid, fields in (content.get("items") or {}).items():
        if not isinstance(fields, dict):
            continue
        got = {f: fields[f] for f in ITEM_TEXT_FIELDS + ("length", "significantDigits")
               if f in fields and not is_placeholder(fields[f])}
        origin = resolved_origin(fields.get("origin"))
        if origin:
            got["origin"] = origin
        if got:
            answers["items"][str(oid)] = got
    for oid, fields in (content.get("codeLists") or {}).items():
        terms = [{"codedValue": t["codedValue"], "decode": t.get("decode", "")}
                 for t in (fields or {}).get("codeListItems") or []
                 if isinstance(t, dict) and not is_placeholder(t.get("codedValue"))]
        if terms:
            answers["codeLists"][str(oid)] = {"codeListItems": terms}
    return answers


# -- applying ------------------------------------------------------------------
def apply_answers(dds: dict[str, Any], answers: Answers) -> dict[str, list[str]]:
    """Apply answers to values that are still unfilled, in place; filled values are kept.

    :return: OID -> names of the fields an answer filled
    """
    applied: dict[str, list[str]] = {}

    def note(oid: str, field: str) -> None:
        applied.setdefault(oid, []).append(field)

    for group in tabulation_groups(dds):
        answer = answers["itemGroups"].get(group.get("OID"))
        if not answer:
            continue
        for field in GROUP_FIELDS[:-1]:          # not standard: the DDS key is standardOID
            if field in answer and is_placeholder(group.get(field)):
                group[field] = answer[field]
                note(group["OID"], field)
        if "keySequence" in answer and key_sequence_open(group.get("keySequence")):
            group["keySequence"] = list(answer["keySequence"])
            note(group["OID"], "keySequence")

    for oid, (_, _, item, _) in dds_io.define_items(dds).items():
        answer = answers["items"].get(oid)
        if not answer:
            continue
        for field in ITEM_TEXT_FIELDS:
            if field in answer and field in item and is_placeholder(item[field]):
                item[field] = answer[field]
                note(oid, field)
        for field in ("length", "significantDigits"):
            if field in answer and is_placeholder(item.get(field)):
                item[field] = answer[field]
                note(oid, field)
        if "origin" in answer and origin_open(item.get("origin")):
            item["origin"] = copy.deepcopy(answer["origin"])
            note(oid, "origin")

    for codelist in dds.get("codeLists") or []:
        answer = answers["codeLists"].get(codelist.get("OID"))
        terms = codelist.get("codeListItems") or []
        if not answer or not any(is_placeholder(t.get("codedValue")) for t in terms):
            continue
        kept = [t for t in terms if not is_placeholder(t.get("codedValue"))]
        codes = {t.get("codedValue") for t in kept}
        for term in answer["codeListItems"]:
            if term["codedValue"] not in codes:
                kept.append(dict(term))
                codes.add(term["codedValue"])
        codelist["codeListItems"] = kept
        note(codelist["OID"], "codeListItems")
    return applied


# -- collecting ----------------------------------------------------------------
def collect_remaining(dds: dict[str, Any]) -> Answers:
    """Every value still open in the DDS's Define content, in the define patch layout."""
    remaining = empty()
    for group in tabulation_groups(dds):
        fields: dict[str, Any] = {}
        for field in GROUP_FIELDS:
            if field == "standard" and (group.get("standardOID") or group.get("standard")):
                continue
            if is_placeholder(group.get(field)):
                fields[field] = group.get(field) or None
        key_sequence = group.get("keySequence")
        if isinstance(key_sequence, list) and any(is_placeholder(v) for v in key_sequence):
            fields["keySequence"] = key_sequence
        if fields:
            remaining["itemGroups"][group["OID"]] = fields

    for oid, (_, _, item, _) in dds_io.define_items(dds).items():
        fields = {}
        for field in ITEM_TEXT_FIELDS:
            if field in item and is_placeholder(item[field]):
                fields[field] = item[field] or None
        data_type = item.get("dataType")
        if is_placeholder(item.get("length")) and (data_type in LENGTH_TYPES or is_placeholder(data_type)):
            fields["length"] = None
        if "significantDigits" in item and item["significantDigits"] is None:
            fields["significantDigits"] = None
        if origin_open(item.get("origin")):
            fields["origin"] = [{"type": o.get("type") or PLACEHOLDER, "source": o.get("source") or PLACEHOLDER}
                                for o in item["origin"] if isinstance(o, dict)]
        if fields:
            remaining["items"][oid] = fields

    for codelist in dds.get("codeLists") or []:
        count = sum(1 for t in codelist.get("codeListItems") or [] if is_placeholder(t.get("codedValue")))
        if count:
            remaining["codeLists"][codelist["OID"]] = {"name": codelist.get("name", ""), "count": count}
    return remaining


def count_open(remaining: Answers) -> int:
    """How many values a person still has to fill, counted as the pipeline counts the written file:
    each ``__PLACEHOLDER__`` or null, so an origin's type and source and a term's codedValue and
    decode count separately."""
    def walk(value: Any) -> int:
        if isinstance(value, dict):
            return sum(walk(v) for v in value.values())
        if isinstance(value, list):
            return sum(walk(v) for v in value)
        return 1 if is_placeholder(value) else 0

    groups_and_items = walk(remaining["itemGroups"]) + walk(remaining["items"])
    return groups_and_items + sum(2 * entry["count"] for entry in remaining["codeLists"].values())


# -- writing -------------------------------------------------------------------
BANNER = [
    "=" * 68,
    "Define-JSON Placeholder Patch File",
    "Study    : {study}",
    "Generated: {today}",
    "Written by loaders/defaults (pipeline stage F): what is still open once the",
    "defaults are filled, plus every value already answered.",
    "",
    "Instructions:",
    "  1. Replace every __PLACEHOLDER__ with a valid value",
    "  2. Fill every null with an appropriate number",
    "  3. Re-run the pipeline: stage A and stage F apply the answers (--from F is enough)",
    "",
    "Valid values for origin[].type:",
    "  Assigned | Collected | Derived | Not Available | Other | Predecessor | Protocol",
    "Valid values for origin[].source:",
    "  Investigator | Sponsor | Subject | Vendor",
    "=" * 68,
]


def write(path: str | Path, dds: dict[str, Any], remaining: Answers, answers: Answers) -> None:
    """Write the define patch: each open value, with every answered value carried over.
    Answers for OIDs the DDS no longer has are dropped."""
    def comment(*parts: Any) -> str:
        return " - ".join(str(p) for p in parts if p).replace("\n", " ")

    groups: list[str] = []
    for group in tabulation_groups(dds):
        fields = {**remaining["itemGroups"].get(group.get("OID"), {}),
                  **answers["itemGroups"].get(group.get("OID"), {})}
        if not fields:
            continue
        groups.append(f"  {yaml_scalar(group['OID'])}:  # {comment(group.get('name'), group.get('description'))}")
        for field, value in fields.items():
            rendered = yaml_list(value) if field == "keySequence" else yaml_scalar(value)
            groups.append(f"    {field}: {rendered}")

    items: list[str] = []
    for oid, (_, _, item, _) in dds_io.define_items(dds).items():
        fields = {**remaining["items"].get(oid, {}), **answers["items"].get(oid, {})}
        if not fields:
            continue
        items.append(f"  {yaml_scalar(oid)}:  # {comment(item.get('name'), item.get('description'))}")
        for field, value in fields.items():
            if field == "origin":
                items.append("    origin:")
                for entry in value:
                    items.append(f"      - type: {yaml_scalar(entry.get('type'))}")
                    items.append(f"        source: {yaml_scalar(entry.get('source'))}")
            else:
                items.append(f"    {field}: {yaml_scalar(value)}")

    codelists: list[str] = []
    for codelist in dds.get("codeLists") or []:
        oid = codelist.get("OID")
        answered = answers["codeLists"].get(oid, {}).get("codeListItems") or []
        count = remaining["codeLists"].get(oid, {}).get("count", 0)
        if not answered and not count:
            continue
        codelists += [f"  {yaml_scalar(oid)}:  # {comment(codelist.get('name'))}", "    codeListItems:"]
        for term in answered + [{"codedValue": PLACEHOLDER, "decode": PLACEHOLDER}] * count:
            codelists.append(f"      - codedValue: {yaml_scalar(term['codedValue'])}")
            codelists.append(f"        decode: {yaml_scalar(term.get('decode', ''))}")

    if groups:
        groups = ["  # keySequence: ordered list of variable names that form the sort / primary key",
                  "  # Example:  keySequence: [STUDYID, USUBJID, DSSEQ]"] + groups
    if items:
        items = ["  # Applies to both standard items and VLM slice items",
                 "  # length: integer (characters or digits); significantDigits: integer for float variables",
                 "  # origin: one or more entries, each with a type and a source"] + items
    if codelists:
        codelists = ["  # codeListItems: one entry per term; codedValue is the submission value"] + codelists

    banner = [line.format(study=dds.get("studyName") or "N/A", today=date.today().isoformat())
              for line in BANNER]
    write_patch_file(path, banner, [("itemGroups", groups), ("items", items), ("codeLists", codelists)])
