"""The SDTM methods library: load and validate one or more files, layered.

A library file has two sections. ``methods`` holds finished, shared method definitions, each a DDS
Method in the ODM v2.0 shape proposed as PR-DDS-3 (``DDS_FOR_METHODS.md``) plus the library-only
``basis``. ``assignments`` says which Derived items get each method, named the way defaults entries
are (an exact name, a ``--`` suffix, or ``*`` with ``domains``), optionally narrowed by ``domains``,
``excludeDomains`` and a value-level ``where``.

Files load in order and later files win: a file that defines an OID again replaces the earlier
entry as a whole, and its assignments outrank earlier ones at equal rank. An assignment may name a
method any loaded file defines. Every file is checked before anything is used:

- against ``schemas/methods/methods.schema.json`` (type Computation or Imputation, rule 209; a
  non-empty description, rule 56; each expression has a context, rule 221, and exactly one of
  ``expression`` or ``externalCodeLib``; data types from the DDS DataType enum);
- an OID appears once per file, and an assignment once per file;
- signature names are unique within a signature, and ``orderNumber`` values within each list;
- every assignment names a defined method.

The DDS copy of a method (``Library.dds_method``) drops ``basis`` and fills in an empty signature and the
OIDs the DDS model requires on signature entries and expressions (``element_oids``).
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_FILE = Path(__file__).resolve().parents[3] / "schemas" / "methods" / "methods.schema.json"
SEED_FILE = Path(__file__).resolve().parents[3] / "data" / "methods" / "sdtm_methods.json"
SUPPORTED_MAJOR = 1
#: Keys a library method carries that never reach the DDS.
LIBRARY_ONLY_KEYS = ("basis",)


class LibraryError(Exception):
    """A library cannot be read, does not validate, or is inconsistent."""


@dataclass(frozen=True)
class Assignment:
    name: str
    method: str
    domains: frozenset[str] | None = None
    exclude: frozenset[str] | None = None
    where: tuple[tuple[str, str], ...] | None = None
    file: str = ""
    order: int = 0          # index of the file in the load order
    position: int = 0       # index of the entry in its file

    @property
    def key(self) -> tuple:
        return self.name, self.domains, self.exclude, self.where

    @property
    def label(self) -> str:
        """The assignment as a report names it: ``VSORRES [VS] where VSTESTCD=BMI``."""
        text = self.name
        if self.domains:
            text += f" [{', '.join(sorted(self.domains))}]"
        if self.exclude:
            text += f" [not {', '.join(sorted(self.exclude))}]"
        if self.where:
            text += " where " + ", ".join(f"{var}={value}" for var, value in self.where)
        return text


class Library:
    def __init__(self, methods: dict[str, dict[str, Any]], method_files: dict[str, str],
                 assignments: list[Assignment], files: list[str]) -> None:
        self.methods = methods              # OID -> winning library entry (basis included)
        self.method_files = method_files    # OID -> file the winning entry came from
        self.assignments = assignments
        self.files = files

    @classmethod
    def load(cls, paths: list[str | Path]) -> "Library":
        import jsonschema

        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            validator = jsonschema.Draft202012Validator(json.load(f))
        methods: dict[str, dict[str, Any]] = {}
        method_files: dict[str, str] = {}
        assignments: list[Assignment] = []
        problems: list[str] = []
        for order, path in enumerate(paths):
            name = Path(path).name
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = json.load(f)
            except (OSError, json.JSONDecodeError) as exc:
                problems.append(f"{path}: {exc}")
                continue
            errors = sorted(validator.iter_errors(content), key=lambda e: list(e.absolute_path))
            if errors:
                problems += [f"{name}: {'/'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}"
                             for e in errors]
                continue
            major = int(str(content["schemaVersion"]).split(".")[0])
            if major != SUPPORTED_MAJOR:
                problems.append(f"{name}: schemaVersion {content['schemaVersion']} is not supported "
                                f"(this loader reads {SUPPORTED_MAJOR}.x)")
                continue

            seen_oids: set[str] = set()
            for raw in content.get("methods") or []:
                oid = raw["OID"]
                if oid in seen_oids:
                    problems.append(f"{name}: method {oid} is defined twice")
                seen_oids.add(oid)
                problems += [f"{name}: {oid}: {p}" for p in _signature_problems(raw.get("signature"))]
                methods[oid] = raw
                method_files[oid] = name

            seen_keys: set[tuple] = set()
            for position, raw in enumerate(content.get("assignments") or []):
                entry = Assignment(
                    name=raw["name"], method=raw["method"],
                    domains=frozenset(raw["domains"]) if "domains" in raw else None,
                    exclude=frozenset(raw["excludeDomains"]) if "excludeDomains" in raw else None,
                    where=tuple(sorted(raw["where"].items())) if "where" in raw else None,
                    file=name, order=order, position=position)
                if entry.key in seen_keys:
                    problems.append(f"{name}: two assignments for {entry.label}")
                seen_keys.add(entry.key)
                assignments.append(entry)

        if not problems:
            problems += [f"{a.file}: assignment {a.label} names {a.method}, which no library file defines"
                         for a in assignments if a.method not in methods]
        if problems:
            raise LibraryError("the methods library is not usable:\n  - " + "\n  - ".join(problems))
        return cls(methods, method_files, assignments, [str(p) for p in paths])

    def dds_method(self, oid: str) -> dict[str, Any]:
        """
        The method as the DDS holds it: the library entry without its library-only keys, with an
        empty signature when the entry has none (ODM v2.0 requires one on every MethodDef), and with
        an OID on every signature entry and expression that lacks one (see ``element_oids``).
        """
        method = {k: copy.deepcopy(v) for k, v in self.methods[oid].items() if k not in LIBRARY_ONLY_KEYS}
        method.setdefault("signature", {"parameters": [], "returnValues": []})
        method["signature"].setdefault("parameters", [])
        method["signature"].setdefault("returnValues", [])
        element_oids(method)
        return method


def element_oids(method: dict[str, Any]) -> None:
    """
    Give each Parameter, ReturnValue and FormalExpression of a DDS method an OID where it has none.

    The DDS makes these IdentifiableElements, so the JSON Schema generated from dds.yaml requires an
    OID on each; ODM v2.0 gives them none, and a library author should not have to invent them. The
    OIDs are stable and unique within the DDS: ``PA.<method>.<name>``, ``RV.<method>.<name>`` and
    ``FE.<method>.<n>``, where ``<method>`` is the method OID without its ``MT.`` prefix (signature
    names are unique within a method). An ODM v2.0 export drops them. Decided 2026-11-19.
    """
    base = method["OID"][3:] if method["OID"].startswith("MT.") else method["OID"]
    signature = method.get("signature") or {}
    for key, prefix in (("parameters", "PA"), ("returnValues", "RV")):
        for entry in signature.get(key) or []:
            entry.setdefault("OID", f"{prefix}.{base}.{re.sub(r'\s+', '-', entry['name'])}")
    for n, expr in enumerate(method.get("expressions") or [], start=1):
        expr.setdefault("OID", f"FE.{base}.{n}")


def _signature_problems(signature: dict[str, Any] | None) -> list[str]:
    """Names unique within the signature; orderNumber unique within each list."""
    if not signature:
        return []
    problems: list[str] = []
    names: set[str] = set()
    for key in ("parameters", "returnValues"):
        orders: set[int] = set()
        for entry in signature.get(key) or []:
            if entry["name"] in names:
                problems.append(f"signature name {entry['name']} is used twice")
            names.add(entry["name"])
            order = entry.get("orderNumber")
            if order is not None:
                if order in orders:
                    problems.append(f"{key} orderNumber {order} is used twice")
                orders.add(order)
    return problems
