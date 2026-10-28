"""Stage F: fill what no other loader supplied from a dictionary of well-known defaults.

An enrichment loader, like ``loaders/crf`` and ``loaders/pagerefs``: DDS in, DDS out. It runs
after the pagerefs loader and before the Define generator, so every other source has had its
turn, and it fills only values that are still unfilled. Content another loader wrote is never
changed.

The define.xml at this stage is a specification built from the study design before any data
exist, so the defaults are specification values: a length is an estimate, to be set from the
data at submission. The dictionary belongs to the sponsor (see ``data/defaults/README.md``).

For each object, in order:

1. an answer in ``define-patch.yaml`` for its OID (the answers Stage A applied are already in
   the DDS; this catches the ones given since);
2. the dictionary entries that apply to it, best first (``dictionary.py``): each field takes
   its value from the best entry that sets it.

Unfilled means missing, null, ``""`` or ``__PLACEHOLDER__``. An origin is unfilled only when an
entry's type or source is ``__PLACEHOLDER__``: a missing origin is left alone, because the
pagerefs loader removes the origin of a value-list parent on purpose. A ``length`` goes only on
text, integer and float items, ``significantDigits`` only on float ones, and an entry whose
dataType differs from the item's contributes no type-dependent field.

The loader then rewrites ``define-patch.yaml`` with what is still open plus every answered value,
and writes ``defaults-report.yaml``.
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
import sys
from pathlib import Path
from typing import Any, Iterator

import yaml

# Importable both as ``python defaults_loader.py`` from this directory and as
# ``python -m loaders.defaults`` from ``src/``.
_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from loaders.common import dds_io, define_patch  # noqa: E402
from loaders.common.patch import PLACEHOLDER, is_placeholder  # noqa: E402
from loaders.defaults.dictionary import Dictionary, DictionaryError, Entry  # noqa: E402
from loaders.defaults.report import Report, source  # noqa: E402

logger = logging.getLogger("defaults_loader")

DEFAULT_DICTIONARY = Path(__file__).resolve().parents[3] / "data" / "defaults" / "well_known_defaults.json"
LENGTH_TYPES = ("text", "integer", "float")
TYPE_DEPENDENT = ("dataType", "length", "significantDigits", "displayFormat")
COLLECTED_INVESTIGATOR = ("Collected", "Investigator")


class DefaultsError(Exception):
    """The inputs cannot be read, or a dictionary is not usable; nothing was written."""


class DefaultsLoader:
    """Fills one DDS from one or more defaults dictionaries (later files win)."""

    def __init__(self, dds_in: str, dds_out: str, defaults: list[str] | None = None,
                 patch_file: str | None = None) -> None:
        if Path(dds_in).resolve() == Path(dds_out).resolve():
            raise DefaultsError("--dds_out must differ from --dds_in: the loader always starts from "
                                "the pagerefs loader's DDS, so a re-run fills the same values again")
        self.dds_in, self.dds_out, self.patch_file = dds_in, dds_out, patch_file
        try:
            self.dds, self.wrapped = dds_io.load_dds(dds_in)
            self.answers = define_patch.read_answers(patch_file)
        except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
            raise DefaultsError(str(exc)) from exc
        try:
            self.dictionary = Dictionary.load(defaults or [DEFAULT_DICTIONARY])
        except DictionaryError as exc:
            raise DefaultsError(str(exc)) from exc
        self.normalized = dds_io.normalize_dds(self.dds)
        self.report = Report()
        self.remaining = define_patch.empty()

    # -- the fill ---------------------------------------------------------------
    def process(self) -> dict[str, Any]:
        for oid, fields in define_patch.apply_answers(self.dds, self.answers).items():
            for field in fields:
                self.report.fill(oid, field, "answer")
        for group in define_patch.tabulation_groups(self.dds):
            self._fill("itemGroups", group, group.get("domain") or group.get("name"))
        for _, (dataset, _, item, _) in dds_io.define_items(self.dds).items():
            self._fill("items", item, dataset)
        # A CRF item collected by several Concepts is one object in the CRF loader but one copy
        # per Concept once read from a file: every copy is filled, and the report counts it once.
        seen: set[int] = set()
        for form in self._forms():
            for section, obj in _crf_objects(form):
                if id(obj) not in seen:
                    seen.add(id(obj))
                    self._fill(section, obj, form.get("domain"))
        self.remaining = define_patch.collect_remaining(self.dds)
        return self.dds

    def _forms(self) -> list[dict[str, Any]]:
        return [g for g in self.dds.get("itemGroups") or [] if g.get("type") == "Form"]

    def _fill(self, section: str, obj: dict[str, Any], domain: str | None) -> None:
        candidates = self.dictionary.candidates(section, obj.get("name"), domain)
        oid = obj.get("OID") or obj.get("name")
        decided: set[str] = set()
        for entry in candidates:
            conflict = self._conflict(section, obj, entry, oid)
            for field, value in entry.values.items():
                if field in decided or (conflict and field in TYPE_DEPENDENT):
                    continue
                if self._apply(obj, field, value, entry, oid) is not None:
                    decided.add(field)

    def _conflict(self, section: str, obj: dict[str, Any], entry: Entry, oid: str) -> bool:
        if section not in ("items", "crfItems") or "dataType" not in entry.values:
            return False
        current = obj.get("dataType")
        if is_placeholder(current) or current == entry.values["dataType"]:
            return False
        self.report.conflict(oid, entry, current)
        return True

    def _apply(self, obj: dict[str, Any], field: str, value: Any, entry: Entry, oid: str) -> bool | None:
        """Fill one field from one entry: True when filled, False when the field is decided
        without it (already filled, or not applicable), None when the entry cannot supply it."""
        if field == "origin":
            return self._fill_origin(obj, value, entry, oid)
        if field == "keySequence":
            if not define_patch.key_sequence_open(obj.get("keySequence")):
                return False
            obj["keySequence"] = list(value)
            self.report.fill(oid, field, source(entry))
            return True
        if field == "length":
            if obj.get("dataType") not in LENGTH_TYPES:
                return False
            if isinstance(value, dict):
                value = self._computed_length(value)
                if value is None:
                    return None
        if field == "significantDigits" and obj.get("dataType") != "float":
            return False
        if not is_placeholder(obj.get(field)):
            return False
        obj[field] = value
        self.report.fill(oid, field, source(entry))
        return True

    def _computed_length(self, spec: dict[str, Any]) -> int | None:
        text = self.dds.get(spec["lengthOf"])
        if not isinstance(text, str) or is_placeholder(text):
            return None
        return len(text) + int(spec.get("plus", 0))

    def _fill_origin(self, obj: dict[str, Any], value: list[dict[str, Any]], entry: Entry, oid: str) -> bool:
        origins = obj.get("origin")
        if not define_patch.origin_open(origins):
            return False
        if any(not isinstance(o, dict) or is_placeholder(o.get("type")) for o in origins):
            obj["origin"] = copy.deepcopy(value)
        else:
            # real types with placeholder sources: take the source the default gives the same type
            changed = False
            for origin in origins:
                same = next((d for d in value if d["type"] == origin["type"]), None)
                if is_placeholder(origin.get("source")) and same:
                    origin["source"] = same["source"]
                    changed = True
            if not changed:
                return False
        self.report.fill(oid, "origin", source(entry))
        for origin in obj["origin"]:
            kind = (origin.get("type"), origin.get("source"))
            if kind == COLLECTED_INVESTIGATOR and not origin.get("documents"):
                self.report.no_pages[oid] = f"Collected/Investigator from {source(entry)}"
            if origin.get("type") == "Derived":
                self.report.derived.add(oid)
        return True

    # -- outputs ----------------------------------------------------------------
    def remaining_crf(self) -> dict[str, list[str]]:
        """CRF section and item fields still set to the placeholder, by OID."""
        found: dict[str, list[str]] = {}
        seen: set[int] = set()
        for form in self._forms():
            for _, obj in _crf_objects(form):
                if id(obj) in seen:
                    continue
                seen.add(id(obj))
                fields = [k for k, v in obj.items() if v == PLACEHOLDER]
                if fields:
                    found[obj.get("OID") or obj.get("name")] = fields
        return found

    def open_items(self) -> dict[str, int]:
        return {"define patch values": define_patch.count_open(self.remaining),
                "noPages": len(self.report.no_pages),
                "CRF placeholders": sum(len(v) for v in self.remaining_crf().values())}

    def save(self) -> None:
        dds_io.save_dds(self.dds, self.dds_out, self.wrapped)

    def write_patch(self, path: str) -> None:
        define_patch.write(path, self.dds, self.remaining, self.answers)

    def write_report(self, path: str) -> None:
        self.report.write(path, self.dictionary.unmatched(), self.remaining_crf())

    def summary(self) -> str:
        r, open_items = self.report, self.open_items()
        lines = ["", "Defaults loader summary", "-----------------------"]
        lines += [f"  filled {field:.<19} {count}" for field, count in sorted(r.filled.items())]
        lines += [
            f"  from define-patch answers  {r.answered}",
            f"  Derived origins filled ... {len(r.derived)} (each gets a MethodDef placeholder in define.xml)",
            f"  dataType conflicts ....... {sum(len(v) for v in r.conflicts.values())}",
            f"  unmatched entries ........ {len(self.dictionary.unmatched())}",
        ]
        lines += [f"  open {name:.<21} {count}" for name, count in open_items.items()]
        return "\n".join(lines)


def _crf_objects(node: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """The Sections and CRF items under a Form, at any depth."""
    for item in node.get("items") or []:
        yield "crfItems", item
    for slice_ in node.get("slices") or []:
        if slice_.get("type") == "Section":
            yield "crfSections", slice_
        yield from _crf_objects(slice_)


def set_cmd_line_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m loaders.defaults",
        description="Fill the values no other loader supplied from well-known defaults (stage F).")
    parser.add_argument("--dds_in", required=True, help="the DDS the pagerefs loader wrote")
    parser.add_argument("--dds_out", required=True, help="the DDS to write, with the defaults")
    parser.add_argument("--defaults", nargs="+", default=[str(DEFAULT_DICTIONARY)],
                        help="one or more defaults dictionaries; later files win "
                             "(default: data/defaults/well_known_defaults.json)")
    parser.add_argument("--patch_file",
                        help="the define-patch.yaml: its answers are applied, then it is rewritten "
                             "with what is still open plus every answered value")
    parser.add_argument("--report", help="the defaults-report.yaml to write")
    parser.add_argument("--validate", nargs="?", const="default", default=None,
                        help="validate the output against the CRF profile JSON Schema")
    parser.add_argument("-l", "--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = set_cmd_line_args()
    logging.basicConfig(level=getattr(logging, args.log_level),
                        format="%(levelname)s - %(name)s - %(message)s")
    try:
        loader = DefaultsLoader(args.dds_in, args.dds_out, args.defaults, args.patch_file)
        loader.process()
    except DefaultsError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    loader.save()
    print(f"✅ DDS with defaults written to {args.dds_out}")
    if args.patch_file:
        loader.write_patch(args.patch_file)
        print(f"✅ define patch (what is still open) written to {args.patch_file}")
    if args.report:
        loader.write_report(args.report)
        print(f"✅ defaults report written to {args.report}")
    print(loader.summary())
    if args.validate:
        from loaders.common.profiles import validate_against_profile
        schema = (Path(__file__).resolve().parents[3] / "schemas" / "dds" / "profiles" / "crf"
                  / "crf.schema.json") if args.validate == "default" else Path(args.validate)
        errors = validate_against_profile(loader.dds, str(schema))
        for error in errors[:20]:
            print(f"  ✗ {error}")
        if errors:
            print(f"❌ profile validation FAILED — {len(errors)} error(s)")
            sys.exit(1)
        print("✅ profile validation passed")


if __name__ == "__main__":
    main()
