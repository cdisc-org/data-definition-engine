"""``origin-review.yaml``: what the pagerefs loader decided that a person should confirm.

Sections, each keyed so an answer survives the file being regenerated:

* ``replaced`` — a Define-loader origin that is not a placeholder and that the CRF evidence
  replaced (LBORRES Collected/Vendor -> Collected/Investigator);
* ``noPages`` — Collected/Investigator Define items that still have no aCRF pages;
* ``unknownOids`` — Define OIDs the pagerefs file names that the DDS does not have;
* ``unpaired`` — CRF targets crfpdf could not pair with a Define OID (its
  ``define_oid_unpaired`` warnings);
* ``pins`` — extra pins by item OID, ValueListDef OID or ``DATASET.VARIABLE``, so one pin
  covers a whole value list.

Each entry's ``pin`` is ``__PLACEHOLDER__`` until answered:

* ``crf`` — accept the CRF origin;
* ``stageA`` — keep the Define loader's origin;
* ``ack`` — acknowledged, change nothing;
* ``{type: ..., source: ...}`` — this origin, with the CRF pages when the CRF evidence has the
  same type and source (or the same type and a placeholder source).

An entry still set to ``__PLACEHOLDER__`` is an open item; the pipeline's ``--strict`` fails
while any is open.
"""
from __future__ import annotations

from typing import Any

from ..common.patch import (PLACEHOLDER, is_placeholder, load_patch, write_patch_file,
                            yaml_scalar)

SECTIONS = ("replaced", "noPages", "unknownOids", "unpaired")
PIN_SECTIONS = ("replaced", "noPages")      # sections whose pins change an origin

BANNER = [
    "Origin review file - written by loaders/pagerefs (Stage E)",
    "",
    "Answer each pin and re-run with --apply_patch:",
    "  crf     accept the origin and pages the aCRF gives",
    "  stageA  keep the Define loader's origin",
    "  ack     acknowledged; change nothing",
    "  {type: Collected, source: Vendor}   use this origin",
    "Under pins, a key may be an item OID, a ValueListDef OID (VL.LB.LBORRES) or",
    "DATASET.VARIABLE, so one pin covers a whole value list.",
    "",
    "This file is regenerated on every run; answered pins are carried over.",
]


def read_pins(path: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    """
    :return: (pins by key, the ``pins`` section as written, answered pins per section by key)
    """
    content = load_patch(path) or {}
    answered: dict[str, dict[str, Any]] = {}
    pins: dict[str, Any] = {}
    for section in SECTIONS:
        for key, entry in (content.get(section) or {}).items():
            pin = entry.get("pin") if isinstance(entry, dict) else None
            if pin is None or is_placeholder(pin):
                continue
            answered.setdefault(section, {})[key] = pin
            if section in PIN_SECTIONS:
                pins[key] = pin
    extra = {k: v for k, v in (content.get("pins") or {}).items() if not is_placeholder(v)}
    pins.update(extra)
    return pins, content.get("pins") or {}, answered


def write_review(path: str, review: dict[str, dict[str, dict[str, Any]]],
                 extra_pins: dict[str, Any]) -> None:
    sections = []
    for section in SECTIONS:
        lines = []
        for key, entry in review.get(section, {}).items():
            lines.append(f"  {yaml_scalar(key)}:")
            for field, value in entry.items():
                if field != "pin":
                    lines.append(f"    {field}: {yaml_scalar(value)}")
            lines.append(f"    pin: {_pin(entry.get('pin', PLACEHOLDER))}")
        sections.append((section, lines))
    sections.append(("pins", [f"  {yaml_scalar(k)}: {_pin(v)}" for k, v in extra_pins.items()]))
    write_patch_file(path, BANNER, sections)


def _pin(value: Any) -> str:
    if isinstance(value, dict):
        return "{" + ", ".join(f"{k}: {yaml_scalar(v)}" for k, v in value.items()) + "}"
    return yaml_scalar(PLACEHOLDER if value is None else value)
