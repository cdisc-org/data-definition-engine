"""``methods-report.yaml``: which method each Derived item got, and what a person may want to check.

It is generated, not answered, so it goes in ``output_dir`` with the other generated files.
Sections:

* ``assigned`` — each library method the loader attached, with the assignment that chose it
  (``--SEQ (sdtm_methods.json)``) and the items it serves;
* ``placeholders`` — each method whose description is still ``__PLACEHOLDER__``, with the items it
  serves: a study-specific derivation for a person to write;
* ``answered`` — placeholder methods (and the leaves they reference) filled from define-patch
  answers, with the fields each answer filled;
* ``openLeaves`` — leaves a method answer references but ``resources`` does not define yet: the
  define patch lists them for a title and href, and the document waits until then;
* ``kept`` — Derived items that already named a method, left as they were;
* ``bothLevels`` — variables Derived both on the value-list parent and at value level: both get a
  method so rule 73 holds, but one level is usually enough;
* ``unmatched`` — library assignments no item used (a typo shows up here, and so does an
  assignment for content the study does not have, or one a later file outranks everywhere);
* ``unreferenced`` — methods already in the input DDS that no item names.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .library import Assignment

HEADER = [
    "# Methods report - written by loaders/methods (pipeline stage G).",
    "# Generated on every run; nothing here needs an answer.",
    "",
]


def source(assignment: Assignment) -> str:
    return f"{assignment.label} ({assignment.file})"


class Report:
    def __init__(self) -> None:
        self.assigned: dict[str, dict[str, Any]] = {}
        self.placeholders: dict[str, list[str]] = {}
        self.answered: dict[str, list[str]] = {}
        self.open_leaves: dict[str, dict[str, Any]] = {}
        self.kept: dict[str, str] = {}
        self.both_levels: dict[str, dict[str, Any]] = {}
        self.unreferenced: list[str] = []
        self.derived = 0

    def assign(self, item_oid: str, method_oid: str, assignment: Assignment) -> None:
        entry = self.assigned.setdefault(method_oid, {"assignments": [], "items": []})
        if source(assignment) not in entry["assignments"]:
            entry["assignments"].append(source(assignment))
        entry["items"].append(item_oid)

    @property
    def assigned_items(self) -> int:
        return sum(len(entry["items"]) for entry in self.assigned.values())

    @property
    def placeholder_items(self) -> int:
        return sum(len(items) for items in self.placeholders.values())

    def write(self, path: str | Path, unmatched: list[Assignment]) -> None:
        content = {
            "assigned": self.assigned,
            "placeholders": self.placeholders,
            "answered": self.answered,
            "openLeaves": sorted(self.open_leaves),
            "kept": self.kept,
            "bothLevels": self.both_levels,
            "unmatched": [source(a) + f" -> {a.method}" for a in unmatched],
            "unreferenced": self.unreferenced,
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(HEADER) + "\n")
            yaml.safe_dump(content, f, sort_keys=False, allow_unicode=True, width=110)
