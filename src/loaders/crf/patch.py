"""The CRF refinement YAML: collect what the loader could not derive, and apply answers.

The refinement file is how a study-specific CRF is shaped without touching code. It
carries four kinds of content:

* **placeholders** — values the loader could not derive (section labels and instructions,
  a question with no CDASHIG text behind it)
* **choices** — where a Biomedical Concept resolved to several CRF groups
* **gaps** — concepts with no CRF specialization at all, and visits with no forms bound
* **structure** — which Concepts sit in which Section, which Sections in which Form, and
  which Forms are collected at which visit

Applying a patch is deliberately conservative: a value still set to ``__PLACEHOLDER__``
means the human has not answered, so it is never written back over the loader's output.
"""
from __future__ import annotations

import logging
from typing import Any

from ..common.patch import (PLACEHOLDER, apply_field_patches, is_placeholder, load_patch,
                            write_patch_file, yaml_list, yaml_scalar)

logger = logging.getLogger(__name__)

FORM_FIELDS = ("label", "description", "repeating", "mandatory", "domain")
SECTION_FIELDS = ("label", "name", "repeating", "mandatory", "crfSectionInstructions")
ITEM_FIELDS = ("question", "prompt", "crfCompletionInstructions", "definition",
               "implementationNotes", "cdiscNotes", "mappingInstructions",
               "description", "length", "significantDigits", "mandatory")

BANNER = [
    "CRF refinement file - written by crf_loader.py",
    "",
    "Fill in every __PLACEHOLDER__ and re-run crf_loader.py with --apply_patch to fold",
    "the answers into the DDS. Values left as __PLACEHOLDER__ are ignored, so a partly",
    "completed file is safe to apply.",
    "",
    "This file is regenerated on every run. Your answers survive because applying them",
    "first removes the placeholder they replaced.",
]


# --------------------------------------------------------------------------------
# Collect
# --------------------------------------------------------------------------------
def generate_patch_file(path: str, dds: dict[str, Any], extras: dict[str, Any]) -> None:
    """Write the refinement YAML for a freshly built DDS.

    :param path: output path
    :param dds: the combined DDS
    :param extras: loader findings — ``crfGroupChoices``, ``uncoveredConcepts``,
        ``formCandidates``
    """
    forms, sections, items = [], [], []
    for form in _crf_forms(dds):
        forms.extend(_form_lines(form))
        for section in form.get("slices") or []:
            sections.extend(_section_lines(section))

    for oid, occurrences in _crf_items_by_oid(dds).items():
        lines = _item_lines(occurrences[0])
        if lines:
            items.extend(lines)

    study_events = []
    candidates = extras.get("formCandidates") or []
    for event in dds.get("studyEvents") or []:
        study_events.extend(_study_event_lines(event, candidates))

    choices = []
    for code, choice in (extras.get("crfGroupChoices") or {}).items():
        choices.append(f"  {code}:")
        choices.append(f"    selected: {yaml_scalar(choice['selected'])}")
        choices.append(f"    candidates: {yaml_list(choice['candidates'])}")

    uncovered = []
    for entry in extras.get("uncoveredConcepts") or []:
        uncovered.append(f"  - code: {yaml_scalar(entry.get('code'))}")
        uncovered.append(f"    name: {yaml_scalar(entry.get('name'))}")
        if entry.get("activity"):
            uncovered.append(f"    activity: {yaml_scalar(entry['activity'])}")

    code_lists = []
    for codelist in dds.get("codeLists") or []:
        if not str(codelist.get("OID", "")).startswith(("CL.CDASH", "CL.CRF")):
            continue
        if codelist.get("codeListItems"):
            continue
        code_lists.append(f"  {codelist['OID']}:")
        code_lists.append("    codeListItems: []   # no terms resolved from CT")

    write_patch_file(path, BANNER, [
        ("forms", forms),
        ("sections", sections),
        ("items", items),
        ("studyEvents", study_events),
        ("crfGroupChoices", choices),
        ("uncoveredConcepts", uncovered),
        ("codeLists", code_lists),
    ])


def _form_lines(form: dict[str, Any]) -> list[str]:
    sections = [s.get("OID") for s in form.get("slices") or []]
    return [
        f"  {form['OID']}:",
        f"    label: {yaml_scalar(form.get('label'))}",
        f"    repeating: {yaml_scalar(form.get('repeating', 'No'))}",
        f"    sections: {yaml_list(sections)}",
    ]


def _section_lines(section: dict[str, Any]) -> list[str]:
    concepts = [c.get("OID") for c in section.get("slices") or []]
    return [
        f"  {section['OID']}:",
        f"    label: {yaml_scalar(section.get('label'))}",
        f"    crfSectionInstructions: {yaml_scalar(section.get('crfSectionInstructions'))}",
        f"    concepts: {yaml_list(concepts)}",
    ]


def _item_lines(item: dict[str, Any]) -> list[str]:
    """Only items with an unfilled question need an entry."""
    if item.get("question") != PLACEHOLDER:
        return []
    return [
        f"  {item['OID']}:",
        f"    question: {yaml_scalar(item.get('question'))}",
        f"    prompt: {yaml_scalar(item.get('prompt'))}",
        f"    crfCompletionInstructions: {yaml_scalar(item.get('crfCompletionInstructions'))}",
    ]


def _study_event_lines(event: dict[str, Any], candidates: list[str]) -> list[str]:
    return [
        f"  {event['OID']}:",
        f"    itemGroups: {yaml_list(event.get('itemGroups') or [])}",
        f"    candidates: {yaml_list(candidates)}",
    ]


# --------------------------------------------------------------------------------
# Apply
# --------------------------------------------------------------------------------
def apply_patch_file(path: str, dds: dict[str, Any]) -> list[str]:
    """Apply a refinement YAML to a DDS in place.

    :return: human-readable descriptions of everything changed
    """
    patch = load_patch(path)
    if not patch:
        logger.warning("refinement file %s is empty - nothing to apply", path)
        return []

    changes: list[str] = []
    changes += _apply_forms(patch.get("forms") or {}, dds)
    changes += _apply_sections(patch.get("sections") or {}, dds)
    changes += _apply_items(patch.get("items") or {}, dds)
    changes += _apply_study_events(patch.get("studyEvents") or {}, dds)
    changes += _apply_codelists(patch.get("codeLists") or {}, dds)
    logger.info("applied %d change(s) from %s", len(changes), path)
    return changes


def _apply_forms(patches: dict[str, Any], dds: dict[str, Any]) -> list[str]:
    changes = []
    forms = {f["OID"]: f for f in _crf_forms(dds)}
    sections = {s["OID"]: s for s in _crf_sections(dds)}
    for oid, patch in patches.items():
        form = forms.get(oid)
        if form is None:
            logger.warning("refinement names unknown form %s - skipped", oid)
            continue
        for field in apply_field_patches(form, patch, FORM_FIELDS):
            changes.append(f"form {oid}.{field}")
        if isinstance(patch.get("aliases"), list):
            form["aliases"] = patch["aliases"]
            changes.append(f"form {oid}.aliases")
        wanted = patch.get("sections")
        if isinstance(wanted, list) and wanted:
            reordered = [sections[s] for s in wanted if s in sections]
            if len(reordered) == len(wanted):
                form["slices"] = reordered
                changes.append(f"form {oid}.sections")
            else:
                missing = [s for s in wanted if s not in sections]
                logger.warning("form %s names unknown section(s) %s - layout unchanged",
                               oid, missing)
    return changes


def _apply_sections(patches: dict[str, Any], dds: dict[str, Any]) -> list[str]:
    changes = []
    sections = {s["OID"]: s for s in _crf_sections(dds)}
    concepts = {c["OID"]: c for c in _crf_concepts(dds)}
    for oid, patch in patches.items():
        section = sections.get(oid)
        if section is None:
            logger.warning("refinement names unknown section %s - skipped", oid)
            continue
        for field in apply_field_patches(section, patch, SECTION_FIELDS):
            changes.append(f"section {oid}.{field}")
        wanted = patch.get("concepts")
        if isinstance(wanted, list) and wanted:
            reordered = [concepts[c] for c in wanted if c in concepts]
            if len(reordered) == len(wanted):
                section["slices"] = reordered
                changes.append(f"section {oid}.concepts")
            else:
                missing = [c for c in wanted if c not in concepts]
                logger.warning("section %s names unknown concept(s) %s - layout unchanged",
                               oid, missing)
    return changes


def _apply_items(patches: dict[str, Any], dds: dict[str, Any]) -> list[str]:
    changes = []
    items = _crf_items_by_oid(dds)
    for oid, patch in patches.items():
        occurrences = items.get(oid)
        if not occurrences:
            logger.warning("refinement names unknown item %s - skipped", oid)
            continue
        # A shared item is inlined once per concept; patch every copy so they agree.
        fields: set[str] = set()
        for item in occurrences:
            fields.update(apply_field_patches(item, patch, ITEM_FIELDS))
        changes.extend(f"item {oid}.{field}" for field in sorted(fields))
    return changes


def _apply_study_events(patches: dict[str, Any], dds: dict[str, Any]) -> list[str]:
    changes = []
    events = {e["OID"]: e for e in dds.get("studyEvents") or []}
    known_forms = {f["OID"] for f in _crf_forms(dds)}
    for oid, patch in patches.items():
        event = events.get(oid)
        if event is None:
            logger.warning("refinement names unknown studyEvent %s - skipped", oid)
            continue
        bound = patch.get("itemGroups")
        if not isinstance(bound, list):
            continue
        unknown = [f for f in bound if f not in known_forms]
        if unknown:
            logger.warning("studyEvent %s binds unknown form(s) %s - skipped", oid, unknown)
            continue
        if event.get("itemGroups") != bound:
            event["itemGroups"] = bound
            changes.append(f"studyEvent {oid}.itemGroups")
    return changes


def _apply_codelists(patches: dict[str, Any], dds: dict[str, Any]) -> list[str]:
    changes = []
    code_lists = {c["OID"]: c for c in dds.get("codeLists") or []}
    for oid, patch in patches.items():
        codelist = code_lists.get(oid)
        if codelist is None:
            logger.warning("refinement names unknown codeList %s - skipped", oid)
            continue
        terms = patch.get("codeListItems")
        if isinstance(terms, list) and terms:
            codelist["codeListItems"] = terms
            changes.append(f"codeList {oid}.codeListItems")
    return changes


# --------------------------------------------------------------------------------
# Traversal
# --------------------------------------------------------------------------------
def _crf_forms(dds: dict[str, Any]) -> list[dict[str, Any]]:
    return [g for g in dds.get("itemGroups") or [] if g.get("type") == "Form"]


def _crf_sections(dds: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for f in _crf_forms(dds) for s in f.get("slices") or []
            if s.get("type") == "Section"]


def _crf_concepts(dds: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for s in _crf_sections(dds) for c in s.get("slices") or []
            if c.get("type") == "Concept"]


def _crf_items(dds: dict[str, Any]) -> list[dict[str, Any]]:
    """Every CRF item occurrence, inlined inside the Concept groups.

    ``ItemGroup.items`` is ``inlined_as_list`` in the DDS model, so an item shared by
    several concepts (``IT.CRF.VSDAT`` sits on every Vital Signs concept) appears once
    per concept. This returns every occurrence, not a deduplicated set, so a patch can
    be applied to all of them.
    """
    return [item for concept in _crf_concepts(dds)
            for item in concept.get("items") or []]


def _crf_items_by_oid(dds: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """CRF item occurrences grouped by OID."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in _crf_items(dds):
        oid = item.get("OID")
        if oid:
            grouped.setdefault(oid, []).append(item)
    return grouped
