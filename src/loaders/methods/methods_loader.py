"""Stage G: attach a method to every Derived item, from a library of standard SDTM derivations.

An enrichment loader, like ``loaders/defaults``: DDS in, DDS out. It runs after the defaults loader,
so every source of origins has had its turn, and it never changes an origin: a method goes only on an
item another loader or a person already made Derived (Define-XML 2.1 rule 73 requires one there).

For each Define item (variable and value level) with a Derived origin, in order:

1. an item that already names a method keeps it;
2. otherwise the best library assignment for it (``library.py``: an exact name, then a longer
   ``--`` suffix, then ``*``; a matching value-level ``where`` outranks none; a domain filter
   outranks none; a later file outranks an earlier one) gives its method, and the method is copied
   into ``methods`` once, however many items share it;
3. otherwise the item gets a placeholder method ``MT.<DS>.<VAR>`` (the Define generator's own
   convention, so the OIDs stay stable) with description ``__PLACEHOLDER__`` and an empty
   signature, for a person to write.

A variable Derived both on its value-list parent and at value level gets a method at both levels and
is reported under ``bothLevels``. The conformance checks (``conformance.py``) then run on the result,
and a failure stops the loader before it writes. Outputs: the DDS and ``methods-report.yaml``.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Importable both as ``python methods_loader.py`` from this directory and as
# ``python -m loaders.methods`` from ``src/``.
_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from loaders.common import dds_io  # noqa: E402
from loaders.common.patch import PLACEHOLDER, is_placeholder  # noqa: E402
from loaders.common.where_clauses import WhereIndex  # noqa: E402
from loaders.methods import conformance  # noqa: E402
from loaders.methods.library import SEED_FILE, Library, LibraryError  # noqa: E402
from loaders.methods.report import Report  # noqa: E402

logger = logging.getLogger("methods_loader")

DEFAULT_LIBRARY = SEED_FILE


class MethodsError(Exception):
    """The inputs cannot be read, a library is not usable, or the result does not conform;
    nothing was written."""


def placeholder_oid(item_oid: str) -> str:
    """``IT.AE.AESEQ`` -> ``MT.AE.AESEQ``: the OID the Define generator gives the placeholder it makes
    (``post_processing._generate_method_oid``), so a placeholder keeps its OID when it moves into the DDS."""
    parts = item_oid.split(".")
    if parts[0] == "IT":
        parts.pop(0)
    return ".".join(["MT"] + parts).upper().replace(" ", "-")


def placeholder_method(oid: str, variable: str) -> dict[str, Any]:
    return {"OID": oid, "name": f"Algorithm to derive {variable}", "type": "Computation",
            "description": PLACEHOLDER, "signature": {"parameters": [], "returnValues": []}}


class MethodsLoader:
    """Attaches methods to the Derived items of one DDS from one or more libraries (later files win)."""

    def __init__(self, dds_in: str, dds_out: str, libraries: list[str] | None = None) -> None:
        if Path(dds_in).resolve() == Path(dds_out).resolve():
            raise MethodsError("--dds_out must differ from --dds_in: the loader always starts from the "
                               "defaults loader's DDS, so a re-run assigns the same methods again")
        self.dds_in, self.dds_out = dds_in, dds_out
        try:
            self.dds, self.wrapped = dds_io.load_dds(dds_in)
        except (OSError, json.JSONDecodeError) as exc:
            raise MethodsError(str(exc)) from exc
        try:
            self.library = Library.load(libraries or [DEFAULT_LIBRARY])
        except LibraryError as exc:
            raise MethodsError(str(exc)) from exc
        self.normalized = dds_io.normalize_dds(self.dds)
        self.report = Report()

    # -- the assignment ---------------------------------------------------------
    def process(self) -> dict[str, Any]:
        if not isinstance(self.dds.get("methods"), list):
            self.dds["methods"] = []
        methods: list[dict[str, Any]] = self.dds["methods"]
        defined = {m["OID"]: m for m in methods if isinstance(m, dict) and m.get("OID")}
        already = set(defined)
        where = WhereIndex(self.dds)
        items = dds_io.define_items(self.dds)

        for oid, (dataset, variable, item, value_list) in items.items():
            if not conformance.is_derived(item):
                continue
            self.report.derived += 1
            if conformance.has_method(item):
                self.report.kept[oid] = item["method"]
                continue
            assignment = self.library.best(variable, dataset, where.of(item) if value_list else {})
            if assignment is not None:
                method_oid = assignment.method
                if method_oid not in defined:
                    defined[method_oid] = self.library.dds_method(method_oid)
                    methods.append(defined[method_oid])
                self.report.assign(oid, method_oid, assignment)
            else:
                method_oid = placeholder_oid(oid)
                if method_oid not in defined:
                    defined[method_oid] = placeholder_method(method_oid, variable)
                    methods.append(defined[method_oid])
            item["method"] = method_oid

        self._report_levels(items)
        self._report_methods(items, already)
        problems = conformance.check(self.dds, items)
        if problems:
            raise MethodsError("the DDS does not conform; nothing was written:\n  - " + "\n  - ".join(problems))
        return self.dds

    def _report_levels(self, items: conformance.DefineItems) -> None:
        """Variables Derived both on the value-list parent and at value level."""
        parents = {(dataset, variable): (oid, item) for oid, (dataset, variable, item, value_list)
                   in items.items() if value_list is None}
        for oid, (dataset, variable, item, value_list) in items.items():
            if value_list is None or not conformance.is_derived(item):
                continue
            parent_oid, parent = parents.get((dataset, variable), (None, None))
            if parent is not None and conformance.is_derived(parent):
                entry = self.report.both_levels.setdefault(
                    f"{dataset}.{variable}", {"variable": parent_oid, "valueLevel": []})
                entry["valueLevel"].append(oid)

    def _report_methods(self, items: conformance.DefineItems, already: set[str]) -> None:
        """Placeholder methods with the items they serve, and input methods no item names."""
        users: dict[str, list[str]] = {}
        for oid, (_, _, item, _) in items.items():
            if conformance.has_method(item):
                users.setdefault(item["method"], []).append(oid)
        for method in self.dds["methods"]:
            oid = method.get("OID")
            if is_placeholder(method.get("description")):
                self.report.placeholders[oid] = users.get(oid, [])
            if oid in already and oid not in users:
                self.report.unreferenced.append(oid)

    # -- outputs ----------------------------------------------------------------
    def open_items(self) -> dict[str, int]:
        return {"placeholder methods": len(self.report.placeholders)}

    def save(self) -> None:
        dds_io.save_dds(self.dds, self.dds_out, self.wrapped)

    def write_report(self, path: str) -> None:
        self.report.write(path, self.library.unmatched())

    def summary(self) -> str:
        r = self.report
        lines = ["", "Methods loader summary", "----------------------",
                 f"  Derived items ............ {r.derived}",
                 f"  assigned from library .... {r.assigned_items} ({len(r.assigned)} methods)",
                 f"  placeholder methods ...... {len(r.placeholders)} ({r.placeholder_items} items)",
                 f"  kept (method already set)  {len(r.kept)}",
                 f"  Derived at both levels ... {len(r.both_levels)}",
                 f"  unmatched assignments .... {len(self.library.unmatched())}",
                 f"  unreferenced methods ..... {len(r.unreferenced)}"]
        lines += [f"  open {name:.<21} {count}" for name, count in self.open_items().items()]
        return "\n".join(lines)


def set_cmd_line_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m loaders.methods",
        description="Attach a method to every Derived item from a library of SDTM methods (stage G).")
    parser.add_argument("--dds_in", required=True, help="the DDS the defaults loader wrote")
    parser.add_argument("--dds_out", required=True, help="the DDS to write, with the methods")
    parser.add_argument("--methods", nargs="+", default=[str(DEFAULT_LIBRARY)],
                        help="one or more method libraries; later files win "
                             "(default: data/methods/sdtm_methods.json)")
    parser.add_argument("--report", help="the methods-report.yaml to write")
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
        loader = MethodsLoader(args.dds_in, args.dds_out, args.methods)
        loader.process()
    except MethodsError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    loader.save()
    print(f"✅ DDS with methods written to {args.dds_out}")
    if args.report:
        loader.write_report(args.report)
        print(f"✅ methods report written to {args.report}")
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
