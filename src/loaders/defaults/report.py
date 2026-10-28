"""``defaults-report.yaml``: what the defaults loader filled, and what a person may want to check.

It is generated, not answered, so it goes in ``output_dir`` with the other generated files.
Sections:

* ``applied`` — each OID with, for every field filled, its source: a dictionary entry
  (``items --SEQ (well_known_defaults.json)``) or ``answer`` (from ``define-patch.yaml``);
* ``conflicts`` — an entry whose dataType differs from the item's: its dataType, length,
  significantDigits and displayFormat were skipped;
* ``noPages`` — Collected/Investigator origins filled without aCRF pages (the Define generator
  writes ``PageRefs="__PLACEHOLDER__"`` for them);
* ``unmatched`` — entries that matched no object: a typo shows up here, but so does an entry
  for content the study does not have;
* ``remainingCrf`` — CRF placeholders still open, by OID (``crf-refinement.yaml`` belongs to
  stage B, so they are reported here instead).
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from .dictionary import Entry

HEADER = [
    "# Defaults report - written by loaders/defaults (pipeline stage F).",
    "# Generated on every run; nothing here needs an answer. Open values are in define-patch.yaml.",
    "",
]


def source(entry: Entry) -> str:
    return f"{entry.section} {entry.label} ({entry.file})"


class Report:
    def __init__(self) -> None:
        self.applied: dict[str, dict[str, str]] = {}
        self.conflicts: dict[str, list[dict[str, Any]]] = {}
        self.no_pages: dict[str, str] = {}
        self.filled: Counter[str] = Counter()
        self.answered = 0
        self.derived: set[str] = set()

    def fill(self, oid: str, field: str, origin_of_value: str) -> None:
        """Record one filled field. A CRF item repeated per Concept is filled in every copy but
        counted once."""
        if field in self.applied.get(oid, {}):
            return
        self.applied.setdefault(oid, {})[field] = origin_of_value
        if origin_of_value == "answer":
            self.answered += 1
        else:
            self.filled[field] += 1

    def conflict(self, oid: str, entry: Entry, current: Any) -> None:
        found = {"entry": source(entry), "dataType": current, "default": entry.values.get("dataType")}
        if found not in self.conflicts.setdefault(oid, []):
            self.conflicts[oid].append(found)

    def write(self, path: str | Path, unmatched: list[Entry], remaining_crf: dict[str, list[str]]) -> None:
        content = {
            "applied": self.applied,
            "conflicts": self.conflicts,
            "noPages": self.no_pages,
            "unmatched": [source(entry) for entry in unmatched],
            "remainingCrf": remaining_crf,
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(HEADER) + "\n")
            yaml.safe_dump(content, f, sort_keys=False, allow_unicode=True, width=110)
