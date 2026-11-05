"""The defaults dictionary: load and validate one or more files, and rank the entries for an object.

A dictionary groups its entries by the kind of DDS object they fill (``items``, ``itemGroups``,
``crfItems``, ``crfSections``). An entry's ``name`` is the object's name exactly, a suffix
(``--SEQ`` matches any longer name ending in ``SEQ``), or ``*`` (every object in the datasets its
``domains`` lists). Candidates for an object are ranked best first:

1. an exact name, then a longer suffix before a shorter one, then ``*``;
2. at equal rank, an entry with domain filters before one without;
3. then a later file before an earlier one, and a later entry before an earlier one.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SECTIONS = ("items", "itemGroups", "crfItems", "crfSections")
SCHEMA_FILE = Path(__file__).resolve().parents[3] / "schemas" / "defaults" / "defaults.schema.json"
SUPPORTED_MAJOR = 1


class DictionaryError(Exception):
    """A dictionary cannot be read, does not validate, or repeats an entry."""


@dataclass(frozen=True)
class Entry:
    section: str
    name: str
    values: dict[str, Any] = field(hash=False, compare=False)
    domains: frozenset[str] | None = None
    exclude: frozenset[str] | None = None
    file: str = ""
    order: int = 0          # index of the file in the load order
    position: int = 0       # index of the entry in its section

    @property
    def key(self) -> tuple:
        return self.section, self.name, self.domains, self.exclude

    @property
    def label(self) -> str:
        """The entry as the report names it: ``--DTC [SE, SV]``, ``EPOCH [not TA]``."""
        text = self.name
        if self.domains:
            text += f" [{', '.join(sorted(self.domains))}]"
        if self.exclude:
            text += f" [not {', '.join(sorted(self.exclude))}]"
        return text

    def rank(self, name: str | None, domain: str | None) -> tuple | None:
        """This entry's rank for an object, or None when it does not apply."""
        if self.domains is not None and domain not in self.domains:
            return None
        if self.exclude is not None and domain in self.exclude:
            return None
        if self.name == "*":
            kind = (1, 0)
        elif self.name.startswith("--"):
            suffix = self.name[2:]
            if not name or not name.endswith(suffix) or len(name) <= len(suffix):
                return None
            kind = (2, len(suffix))
        elif self.name == name:
            kind = (3, 0)
        else:
            return None
        filtered = 1 if (self.domains is not None or self.exclude is not None) else 0
        return kind + (filtered, self.order, self.position)


class Dictionary:
    def __init__(self, entries: list[Entry], files: list[str]) -> None:
        self.entries = entries
        self.files = files
        self.matched: set[Entry] = set()

    @classmethod
    def load(cls, paths: list[str | Path]) -> "Dictionary":
        import jsonschema

        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            validator = jsonschema.Draft202012Validator(json.load(f))
        entries: list[Entry] = []
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
            seen: set[tuple] = set()
            for section in SECTIONS:
                for position, raw in enumerate(content.get(section) or []):
                    entry = Entry(section=section, name=raw["name"], values=raw["values"],
                                  domains=frozenset(raw["domains"]) if "domains" in raw else None,
                                  exclude=frozenset(raw["excludeDomains"]) if "excludeDomains" in raw else None,
                                  file=name, order=order, position=position)
                    if entry.key in seen:
                        problems.append(f"{name}: {section} has two entries for {entry.label}")
                    seen.add(entry.key)
                    entries.append(entry)
        if problems:
            raise DictionaryError("the defaults dictionary is not usable:\n  - " + "\n  - ".join(problems))
        return cls(entries, [str(p) for p in paths])

    def candidates(self, section: str, name: str | None, domain: str | None) -> list[Entry]:
        """The entries that apply to an object, best first. Each is recorded as matched."""
        ranked = [(rank, entry) for entry in self.entries if entry.section == section
                  and (rank := entry.rank(name, domain)) is not None]
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        found = [entry for _, entry in ranked]
        self.matched.update(found)
        return found

    def unmatched(self) -> list[Entry]:
        return [entry for entry in self.entries if entry not in self.matched]
