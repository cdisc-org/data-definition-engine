"""``define-patch.yaml`` read, applied, collected and written outside the Define loader.

Stage A (``create_define_json.py``) applies this file and stage F (the defaults loader) applies it
again. In the pipeline, stage G (the methods loader) rewrites it once the defaults are filled and
the methods attached, so it lists only what is still open plus every value a person already
answered; a standalone defaults run rewrites it too. The format is Stage A's, so Stage A's
``--apply_patch`` reads the rewritten file unchanged:

* ``itemGroups`` — OID -> name, description, domain, purpose, structure, standard, keySequence;
* ``items`` — OID -> name, description, role, dataType, length, significantDigits, and origin
  (a list of ``{type, source}``);
* ``codeLists`` — OID -> codeListItems (``{codedValue, decode}``);
* ``methods`` — OID -> name, type, description and documents (``{leafID, pages}``, physical pages
  only): the placeholder methods the methods loader wrote, for a person to write;
* ``resources`` — leafID -> title and href: the supporting PDFs those methods reference, each
  defined once (it becomes a DDS root ``resources`` DocumentReference and a ``def:leaf``).

Stage A applies only the first three sections and ignores the other two; the methods loader applies
those two (``apply_method_answers``). The defaults loader carries their answers over when it rewrites
the file, so a standalone defaults run never drops a method someone wrote.

The collection rules follow ``create_define_json``'s ``_collect_itemgroup_placeholders`` and
``_collect_item_placeholders``, with two deliberate differences: ``length`` is listed only for
text, integer and float items (the types the Define generator gives a Length), and ``standard``
is not listed when the group has a ``standardOID`` (the key the DDS uses).
"""
from __future__ import annotations

import copy
from datetime import date
from pathlib import Path
from typing import Any, NamedTuple

from . import dds_io
from .patch import PLACEHOLDER, is_placeholder, load_patch, write_patch_file, yaml_list, yaml_scalar

CORE_SECTIONS = ("itemGroups", "items", "codeLists")
METHOD_SECTIONS = ("methods", "resources")
SECTIONS = CORE_SECTIONS + METHOD_SECTIONS
GROUP_FIELDS = ("name", "description", "domain", "purpose", "structure", "standard")
ITEM_TEXT_FIELDS = ("name", "description", "role", "dataType")
LENGTH_TYPES = ("text", "integer", "float")
METHOD_FIELDS = ("name", "type", "description")
RESOURCE_FIELDS = ("title", "href")
ACRF_LEAF = "LF.acrf"            # the leaf the Define generator gives an annotated CRF without a leafID

Answers = dict[str, dict[str, dict[str, Any]]]


class PatchError(ValueError):
    """An answer in the define patch cannot be used as written."""


class MethodAnswers(NamedTuple):
    """What ``apply_method_answers`` did."""
    applied: dict[str, list[str]]           # method OID or leafID -> fields an answer filled
    open_leaves: dict[str, dict[str, Any]]  # leafID -> {title, href}, for a referenced leaf not yet defined
    ignored: list[str]                      # answered methods that already had a description


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


def is_derived(item: dict[str, Any]) -> bool:
    """Whether any of the item's origins has type Derived (aCRF pages or not)."""
    origins = item.get("origin")
    if isinstance(origins, dict):
        origins = [origins]
    return any(isinstance(o, dict) and o.get("type") == "Derived" for o in origins or [])


def placeholder_oid(item_oid: str) -> str:
    """``IT.AE.AESEQ`` -> ``MT.AE.AESEQ``: the OID the Define generator gives the placeholder it makes
    (``post_processing._generate_method_oid``), so a placeholder keeps its OID when it moves into the DDS."""
    parts = item_oid.split(".")
    if parts[0] == "IT":
        parts.pop(0)
    return ".".join(["MT"] + parts).upper().replace(" ", "-")


def leaf_ids(dds: dict[str, Any]) -> set[str]:
    """Every leaf the Define generator writes for a DDS: root ``resources`` entries with a leafID,
    legacy ``documents``, and the annotated CRFs."""
    ids = {r["leafID"] for r in dds.get("resources") or [] if isinstance(r, dict) and r.get("leafID")}
    ids |= {d.get("ID") or d.get("id") or d.get("leafID") for d in dds.get("documents") or []
            if isinstance(d, dict)}
    for key in ("annotatedCRFs", "annotatedCRF"):
        ids |= {a.get("leafID") or ACRF_LEAF for a in dds.get(key) or [] if isinstance(a, dict)}
    ids.discard(None)
    return ids


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
    for oid, fields in (content.get("methods") or {}).items():
        if not isinstance(fields, dict):
            continue
        got = {f: fields[f] for f in METHOD_FIELDS if f in fields and not is_placeholder(fields[f])}
        documents = _documents(str(oid), fields.get("documents"))
        if documents:
            got["documents"] = documents
        if got:
            answers["methods"][str(oid)] = got
    for leaf, fields in (content.get("resources") or {}).items():
        if not isinstance(fields, dict):
            continue
        got = {f: str(fields[f]) for f in RESOURCE_FIELDS if f in fields and not is_placeholder(fields[f])}
        if got:
            answers["resources"][str(leaf)] = got
    return answers


def _documents(oid: str, value: Any) -> list[dict[str, Any]]:
    """A method answer's documents, checked: each names a leafID, and pages are physical page numbers.
    Raises PatchError rather than drop what a person wrote."""
    if value is None or value == [] or is_placeholder(value):
        return []
    if not isinstance(value, list):
        raise PatchError(f"methods {oid}: documents must be a list of {{leafID, pages}}")
    documents = []
    for n, entry in enumerate(value, start=1):
        if not isinstance(entry, dict) or is_placeholder(entry.get("leafID")):
            raise PatchError(f"methods {oid}: document {n} has no leafID")
        document: dict[str, Any] = {"leafID": str(entry["leafID"])}
        pages = entry.get("pages")
        if isinstance(pages, int) and not isinstance(pages, bool):
            pages = [pages]
        if pages not in (None, []):
            if not isinstance(pages, list) or not all(
                    isinstance(p, int) and not isinstance(p, bool) and p >= 1 for p in pages):
                raise PatchError(f"methods {oid}: document {n} pages must be page numbers (integers from 1); "
                                 f"named destinations are not supported yet")
            document["pages"] = list(pages)
        documents.append(document)
    return documents


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


def apply_method_answers(dds: dict[str, Any], answers: Answers) -> MethodAnswers:
    """Apply the ``methods`` and ``resources`` answers, in place (the methods loader calls this once it
    has written its placeholders; the defaults loader does not).

    A method whose description is still ``__PLACEHOLDER__`` takes every answered field that differs
    from its own (the rewritten patch repeats a placeholder's name and type). A document
    whose leaf is not defined is left out, and the leaf is returned as open; an answered leaf that a
    method references becomes a root ``resources`` DocumentReference. A leaf or a method that is
    already filled is never changed.
    """
    applied: dict[str, list[str]] = {}
    methods = {m.get("OID"): m for m in dds.get("methods") or [] if isinstance(m, dict) and m.get("OID")}
    targets = {oid: answer for oid, answer in answers["methods"].items()
               if oid in methods and is_placeholder(methods[oid].get("description"))}
    ignored = [oid for oid in answers["methods"] if oid in methods and oid not in targets]

    defined = leaf_ids(dds)
    open_leaves: dict[str, dict[str, Any]] = {}
    for answer in targets.values():
        for document in answer.get("documents") or []:
            leaf = document["leafID"]
            if leaf in defined:
                continue
            given = answers["resources"].get(leaf, {})
            if all(given.get(f) for f in RESOURCE_FIELDS):
                if not isinstance(dds.get("resources"), list):
                    dds["resources"] = []
                dds["resources"].append({"OID": leaf, "leafID": leaf, "title": given["title"], "href": given["href"]})
                defined.add(leaf)
                applied[leaf] = list(RESOURCE_FIELDS)
            else:
                open_leaves[leaf] = {f: given.get(f) or PLACEHOLDER for f in RESOURCE_FIELDS}

    for oid, answer in targets.items():
        method = methods[oid]
        # the rewritten patch repeats a placeholder's own name and type: only a change counts as an answer
        for field in METHOD_FIELDS:
            if field in answer and answer[field] != method.get(field):
                method[field] = answer[field]
                applied.setdefault(oid, []).append(field)
        documents = [copy.deepcopy(d) for d in answer.get("documents") or [] if d["leafID"] in defined]
        if documents and documents != method.get("documents"):
            method["documents"] = documents
            applied.setdefault(oid, []).append("documents")
    return MethodAnswers(applied, open_leaves, ignored)


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

    for method in dds.get("methods") or []:
        if isinstance(method, dict) and method.get("OID") and is_placeholder(method.get("description")):
            remaining["methods"][method["OID"]] = {"name": method.get("name") or PLACEHOLDER,
                                                   "type": method.get("type") or PLACEHOLDER,
                                                   "description": PLACEHOLDER}
    return remaining


def count_open(remaining: Answers, sections: tuple[str, ...] = SECTIONS) -> int:
    """How many values a person still has to fill, counted as the pipeline counts the written file:
    each ``__PLACEHOLDER__`` or null, so an origin's type and source and a term's codedValue and
    decode count separately. ``sections`` limits the count (the methods loader reports
    ``METHOD_SECTIONS`` apart from the rest, as the pipeline does)."""
    def walk(value: Any) -> int:
        if isinstance(value, dict):
            return sum(walk(v) for v in value.values())
        if isinstance(value, list):
            return sum(walk(v) for v in value)
        return 1 if is_placeholder(value) else 0

    total = sum(walk(remaining.get(section) or {}) for section in sections if section != "codeLists")
    if "codeLists" in sections:
        total += sum(2 * entry["count"] for entry in remaining["codeLists"].values())
    return total


# -- writing -------------------------------------------------------------------
WRITERS = {
    "defaults": ["Written by loaders/defaults, run on its own: what is still open once the",
                 "defaults are filled, plus every value already answered."],
    "methods": ["Written by loaders/methods (pipeline stage G): what is still open once the",
                "defaults are filled and the methods attached, plus every value already answered."],
}
RERUN = [
    "  3. Re-run the pipeline: --from F after answering any value, or --from G",
    "     when only methods and resources were answered",
]
BANNER = [
    "=" * 68,
    "Define-JSON Placeholder Patch File",
    "Study    : {study}",
    "Generated: {today}",
    "{writer}",
    "",
    "Instructions:",
    "  1. Replace every __PLACEHOLDER__ with a valid value",
    "  2. Fill every null with an appropriate number",
    "{rerun}",
    "",
    "Valid values for origin[].type:",
    "  Assigned | Collected | Derived | Not Available | Other | Predecessor | Protocol",
    "Valid values for origin[].source:",
    "  Investigator | Sponsor | Subject | Vendor",
    "Valid values for methods type:",
    "  Computation | Imputation",
    "=" * 68,
]


def banner(dds: dict[str, Any], writer: str) -> list[str]:
    lines: list[str] = []
    for line in BANNER:
        if line == "{writer}":
            lines += WRITERS[writer]
        elif line == "{rerun}":
            lines += RERUN
        else:
            lines.append(line.format(study=dds.get("studyName") or "N/A", today=date.today().isoformat()))
    return lines


def method_users(dds: dict[str, Any]) -> dict[str, list[str]]:
    """Method OID -> the define items it serves. A Derived item without a method counts under its
    placeholder OID, so an answer for it survives a rewrite made before the methods loader runs."""
    users: dict[str, list[str]] = {}
    for oid, (_, _, item, _) in dds_io.define_items(dds).items():
        method = item.get("method")
        if method and not is_placeholder(method):
            users.setdefault(method, []).append(oid)
        elif is_derived(item):
            users.setdefault(placeholder_oid(oid), []).append(oid)
    return users


def write(path: str | Path, dds: dict[str, Any], remaining: Answers, answers: Answers,
          writer: str = "defaults") -> None:
    """Write the define patch: each open value, with every answered value carried over.
    Answers for OIDs the DDS no longer has are dropped: a method answer is kept while the DDS has the
    method or a Derived item that would get it as a placeholder, and a leaf while the DDS has it or a
    kept method references it."""
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

    users = method_users(dds)
    in_dds = [m["OID"] for m in dds.get("methods") or [] if isinstance(m, dict) and m.get("OID")]
    kept = in_dds + [oid for oid in answers["methods"] if oid not in in_dds and oid in users]
    methods: list[str] = []
    references: dict[str, list[str]] = {}
    for oid in kept:
        fields = {**remaining["methods"].get(oid, {}), **answers["methods"].get(oid, {})}
        if oid not in in_dds:
            # written before the methods loader made the placeholder (a defaults rewrite): still open
            fields.setdefault("description", PLACEHOLDER)
        dds_method = next((m for m in dds.get("methods") or [] if isinstance(m, dict) and m.get("OID") == oid), {})
        for document in fields.get("documents") or dds_method.get("documents") or []:
            if isinstance(document, dict) and document.get("leafID"):
                references.setdefault(document["leafID"], []).append(oid)
        if not fields:
            continue
        methods.append(f"  {yaml_scalar(oid)}:  # used by {' '.join(users.get(oid, [])) or 'no item'}")
        for field in METHOD_FIELDS:
            if field in fields:
                methods.append(f"    {field}: {yaml_scalar(fields[field])}")
        if fields.get("documents"):
            methods.append("    documents:")
            for document in fields["documents"]:
                methods.append(f"      - leafID: {yaml_scalar(document['leafID'])}")
                if document.get("pages"):
                    methods.append(f"        pages: {yaml_list(document['pages'])}")

    in_resources = {r["leafID"] for r in dds.get("resources") or [] if isinstance(r, dict) and r.get("leafID")}
    resources: list[str] = []
    for leaf in list(answers["resources"]) + [l for l in remaining["resources"] if l not in answers["resources"]]:
        if leaf not in remaining["resources"] and leaf not in references and leaf not in in_resources:
            continue
        fields = {**remaining["resources"].get(leaf, {}), **answers["resources"].get(leaf, {})}
        resources.append(f"  {yaml_scalar(leaf)}:  # used by {' '.join(references.get(leaf, [])) or 'no method'}")
        for field in RESOURCE_FIELDS:
            if field in fields:
                resources.append(f"    {field}: {yaml_scalar(fields[field])}")

    if groups:
        groups = ["  # keySequence: ordered list of variable names that form the sort / primary key",
                  "  # Example:  keySequence: [STUDYID, USUBJID, DSSEQ]"] + groups
    if items:
        items = ["  # Applies to both standard items and VLM slice items",
                 "  # length: integer (characters or digits); significantDigits: integer for float variables",
                 "  # origin: one or more entries, each with a type and a source"] + items
    if codelists:
        codelists = ["  # codeListItems: one entry per term; codedValue is the submission value"] + codelists

    sections = [("itemGroups", groups), ("items", items), ("codeLists", codelists)]
    if methods or resources:
        methods = ["  # The placeholder methods for a person to write, plus every answered one",
                   "  # type: Computation | Imputation; documents (optional): a list of {leafID, pages}, where",
                   "  # pages are physical page numbers in that PDF and the leafID is defined under resources",
                   ] + methods
        resources = (["  # The supporting PDFs (beside define.xml) that methods reference: leafID -> title, href"]
                     + resources) if resources else []
        sections += [("methods", methods), ("resources", resources)]
    write_patch_file(path, banner(dds, writer), sections)
