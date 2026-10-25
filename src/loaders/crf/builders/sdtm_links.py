"""The SDTM side of a CRF item: parse its annotation, check it against CDASHIG, link each
target to the Define item it populates, and classify how it maps.

The CRF specialization CSV writes the SDTM annotation as free text
(``VSORRES when VSTESTCD = SYSBP``, ``[NOT SUBMITTED];MHSTRF;MHSTRTPT``, ``RACEOTH in
SUPPDM``). The CRF loader runs after the Define loader, so the Define items, value lists
and where clauses are already in the DDS; this module joins the two, so the aCRF can say
which Define ItemDef each field populates instead of leaving that to a reader's guess.

Value-level links use two keys, in order:

1. the SDTM dataset specialization: a value-level item the Define loader coded with the
   concept's specialization id (``vlm_group_id`` in the CSV);
2. the where clause, with "admits" semantics: every condition of the annotation's
   when-clause is on a variable the where clause tests, with values it admits, and the
   concept's prefilled values (LBSPEC = URINE) are admitted wherever the where clause tests
   their variable. A where-clause condition admits a value when EQ equals it, IN lists it,
   NE differs from it. Specialization where clauses add permissible ranges as IN lists
   (VSPOS IN (PRONE, SITTING, ...)), so exact comparison would reject correct matches.

Everything here is pure Python and never raises on odd input.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# mapping codes recorded in crfSdtmTarget.mapping and emitted as Alias SDTMMappingType
DIRECT = "direct"
CONCATENATED = "concatenated"
RELATIVE_TIMING = "relative_timing"
SPLIT = "split"
NOT_SUBMITTED = "not_submitted"
MAPPING_CODES = (DIRECT, CONCATENATED, RELATIVE_TIMING, SPLIT, NOT_SUBMITTED)

RELATIVE_TIMING_SUFFIXES = ("STRF", "ENRF", "STRTPT", "ENRTPT", "STTPT", "ENTPT")

# The CDASHIG mappingInstructions phrases, in the order crfutils/mapping.py tries them.
_KINDS = (
    (RELATIVE_TIMING, re.compile(r"\brelative timing variable", re.IGNORECASE)),
    (SPLIT, re.compile(r"\bnon-numeric\b|\bif numeric\b", re.IGNORECASE)),
    (CONCATENATED, re.compile(r"\bconcatenate", re.IGNORECASE)),
    (NOT_SUBMITTED, re.compile(r"\bnot submitted\b|\bdoes not map to an SDTM(?:IG)? variable",
                               re.IGNORECASE)),
    (DIRECT, re.compile(r"^maps directly\b", re.IGNORECASE)),
)

_NAME = r"[A-Z][A-Z0-9]{1,7}"
_NOT_SUBMITTED_RE = re.compile(r"^\[?\s*NOT SUBMITTED\s*\]?$", re.IGNORECASE)
_SUPP_RE = re.compile(rf"^({_NAME})\s+in\s+(SUPP[A-Z0-9]{{2,4}})$")
_TARGET_RE = re.compile(rf"^(?:({_NAME})\.)?({_NAME})(?:\s*=\s*(.+?))?$")
_WHEN_RE = re.compile(r"\s+(?:when|where|if)\s+", re.IGNORECASE)
_CONDITION_RE = re.compile(rf"^({_NAME})\s*(=|!=|\bEQ\b|\bNE\b|\bIN\b)\s*(.+)$", re.IGNORECASE)
_LIBRARY_VARIABLE_RE = re.compile(r"/variables/([A-Z0-9]+)$")


@dataclass(frozen=True)
class Condition:
    variable: str
    comparator: str                  # EQ | NE | IN
    values: tuple


@dataclass(frozen=True)
class Target:
    variable: str
    value: str | None = None
    conditions: tuple = ()
    dataset: str | None = None       # set only when the text qualifies it (DM.SEX, SUPPDM)
    qnam: str | None = None          # set for "XX in SUPPDD"


@dataclass(frozen=True)
class Annotation:
    not_submitted: bool = False
    targets: tuple = ()
    unparsed: tuple = ()


@dataclass
class Link:
    dataset: str
    variable: str
    item: str | None
    basis: str                       # "dss" | "whereClause" | "variable" | the review reason

    def as_dict(self) -> dict[str, str]:
        return {"dataset": self.dataset, "variable": self.variable, "item": self.item}


@dataclass
class ValueLevelItem:
    oid: str
    conditions: dict = field(default_factory=dict)   # variable -> (comparator, values)
    dss_ids: tuple = ()


# --------------------------------------------------------------------------------
# Annotation text
# --------------------------------------------------------------------------------
def parse_annotation(text: str | None) -> Annotation:
    """Parse a CRF specialization ``sdtm_annotation``.

    ``;`` separates segments; a segment is ``[NOT SUBMITTED]``, ``VAR``, ``DS.VAR``,
    ``VAR = VALUE``, ``XX in SUPPDD``, or any of those followed by ``when``/``where``/``if``
    and conditions joined with ``and``. ``VAR1/VAR2`` is two targets.
    """
    not_submitted, targets, unparsed = False, [], []
    for segment in (s.strip() for s in (text or "").split(";")):
        if not segment:
            continue
        if _NOT_SUBMITTED_RE.match(segment):
            not_submitted = True
            continue
        head, *rest = _WHEN_RE.split(segment, maxsplit=1)
        conditions = _parse_conditions(rest[0]) if rest else ()
        if conditions is None:
            unparsed.append(segment)
            continue
        supp = _SUPP_RE.match(head.strip())
        if supp:
            targets.append(Target("QVAL", None, (Condition("QNAM", "EQ", (supp.group(1),)),),
                                  supp.group(2), supp.group(1)))
            continue
        heads = [head] if "=" in head else head.split("/")
        parsed = [_TARGET_RE.match(h.strip()) for h in heads]
        if not all(parsed):
            unparsed.append(segment)
            continue
        for match in parsed:
            dataset, variable, value = match.groups()
            targets.append(Target(variable, _clean(value), conditions, dataset))
    return Annotation(not_submitted, tuple(targets), tuple(unparsed))


def _parse_conditions(text: str) -> tuple | None:
    conditions = []
    for part in re.split(r"\s+and\s+", text.strip(), flags=re.IGNORECASE):
        match = _CONDITION_RE.match(part.strip())
        if not match:
            return None
        variable, comparator, raw = match.groups()
        comparator = {"=": "EQ", "!=": "NE"}.get(comparator, comparator.upper())
        if comparator == "IN":
            values = tuple(_clean(v) for v in raw.strip().strip("()").split(",") if v.strip())
        else:
            values = (_clean(raw),)
        conditions.append(Condition(variable, comparator, values))
    return tuple(conditions)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().strip("'\"").strip() or None


def replace_variable(text: str, old: str, new: str) -> str:
    """Rewrite one variable name in annotation text, as a whole word."""
    return re.sub(rf"\b{re.escape(old)}\b", new, text or "")


# --------------------------------------------------------------------------------
# CDASHIG
# --------------------------------------------------------------------------------
def library_targets(field_data: dict[str, Any] | None) -> list[str]:
    """The SDTMIG variables a CDASHIG field maps to (``_links.sdtmigDatasetMappingTargets``)."""
    links = ((field_data or {}).get("_links") or {}).get("sdtmigDatasetMappingTargets") or []
    names = []
    for link in links:
        match = _LIBRARY_VARIABLE_RE.search((link or {}).get("href") or "")
        if match and match.group(1) not in names:
            names.append(match.group(1))
    return names


def classify_instructions(text: str | None) -> str | None:
    """The mapping kind a CDASHIG ``mappingInstructions`` text states, or None."""
    normalized = " ".join((text or "").split())
    if not normalized or normalized == "__PLACEHOLDER__":
        return None
    return next((kind for kind, pattern in _KINDS if pattern.search(normalized)), None)


def is_relative_timing(variable: str) -> bool:
    return len(variable) > 4 and variable[2:] in RELATIVE_TIMING_SUFFIXES


def mapping_type(cdash_variable: str, annotation: Annotation, library_variables: list[str],
                 instructions: str | None) -> str | None:
    """Classify how a CRF field maps to SDTM.

    Order: no targets under ``[NOT SUBMITTED]`` -> not_submitted; every target a relative
    timing variable -> relative_timing; a DAT/TIM field whose Library targets are --DTC ->
    concatenated; then the CDASHIG phrase rules; then direct when the only target is the
    field's own variable. None when nothing decides it.
    """
    variables = [t.variable for t in annotation.targets if t.qnam is None]
    if annotation.not_submitted and not annotation.targets:
        return NOT_SUBMITTED
    if variables and all(is_relative_timing(v) for v in variables):
        return RELATIVE_TIMING
    cdash = (cdash_variable or "").upper()
    if library_variables and cdash.endswith(("DAT", "TIM")) and \
            all(v.endswith("DTC") for v in library_variables):
        return CONCATENATED
    kind = classify_instructions(instructions)
    if kind == NOT_SUBMITTED and annotation.targets:
        kind = None                  # the annotation populates something: leave it to review
    if kind:
        return kind
    if variables == [cdash] or (len(variables) == 1 and library_variables == variables):
        return DIRECT
    return None


# --------------------------------------------------------------------------------
# The Define side
# --------------------------------------------------------------------------------
def admits(comparator: str, values: tuple, value: str) -> bool:
    """Whether a where-clause condition admits one value."""
    if comparator == "EQ":
        return value in values[:1]
    if comparator == "IN":
        return value in values
    if comparator == "NE":
        return value not in values
    return False


class DefineIndex:
    """The Define items, value lists and where clauses of a DDS, for linking."""

    def __init__(self, dds: dict[str, Any]) -> None:
        conditions = {c.get("OID"): c for c in dds.get("conditions") or []}
        where_clauses: dict[str, list[str]] = {}
        for wc in dds.get("whereClauses") or []:
            where_clauses.setdefault(wc.get("OID"), wc.get("conditions") or [])
        items_by_oid: dict[str, dict[str, Any]] = {}
        self.variables: dict[tuple, str] = {}
        self.value_lists: dict[tuple, list[ValueLevelItem]] = {}
        self.datasets: dict[str, set] = {}
        for group in dds.get("itemGroups") or []:
            if group.get("type") in ("Form", "Section", "Concept"):
                continue
            dataset = group.get("domain") or group.get("name")
            names = self.datasets.setdefault(dataset, set())
            for item in group.get("items") or []:
                if item.get("OID") and item.get("name"):
                    self.variables[(dataset, item["name"])] = item["OID"]
                    items_by_oid[item["OID"]] = item
                    names.add(item["name"])
            for slice_ in group.get("slices") or []:
                if slice_.get("type") != "ValueList":
                    continue
                for item in slice_.get("items") or []:
                    if not item.get("OID") or not item.get("name"):
                        continue
                    self.value_lists.setdefault((dataset, item["name"]), []).append(
                        ValueLevelItem(item["OID"],
                                       _where(item.get("applicableWhen"), where_clauses, conditions),
                                       tuple(c.get("code") for c in item.get("coding") or []
                                             if isinstance(c, dict) and c.get("code"))))
        self._decodes = _testcd_decodes(dds, items_by_oid)

    def has_dataset(self, dataset: str | None) -> bool:
        return dataset in self.datasets

    def has_variable(self, dataset: str | None, variable: str) -> bool:
        return variable in self.datasets.get(dataset, ())

    def decode(self, dataset: str, variable: str, value: str) -> str | None:
        """The decode of a coded value in the variable's codelist (VSTESTCD SYSBP -> Systolic ...)."""
        return self._decodes.get((dataset, variable), {}).get(value)

    def link(self, dataset: str, variable: str, conditions: tuple = (),
             context: dict[str, str] | None = None, dss_id: str | None = None) -> Link:
        """Link one target to a Define item. ``item`` is None when it needs review."""
        candidates = self.value_lists.get((dataset, variable))
        variable_oid = self.variables.get((dataset, variable))
        if candidates:
            if dss_id:
                # the specialization decides, as long as the annotation's own conditions
                # agree (a group can hold several tests under one specialization id)
                by_dss = [c for c in candidates
                          if dss_id in c.dss_ids and _matches(c.conditions, conditions, {})]
                if len(by_dss) == 1:
                    return Link(dataset, variable, by_dss[0].oid, "dss")
            matches = [c for c in candidates if _matches(c.conditions, conditions, context or {})]
            if len(matches) == 1:
                return Link(dataset, variable, matches[0].oid, "whereClause")
            if len(matches) > 1:
                return Link(dataset, variable, None,
                            f"{len(matches)} value-level items match: "
                            + ", ".join(m.oid for m in matches))
            if not conditions and variable_oid:
                return Link(dataset, variable, variable_oid, "variable")
            return Link(dataset, variable, None, "no value-level item matches")
        if variable_oid:
            return Link(dataset, variable, variable_oid, "variable")
        if not self.has_dataset(dataset):
            return Link(dataset, variable, None, f"the Define has no {dataset} dataset")
        return Link(dataset, variable, None, f"the Define has no {dataset}.{variable}")


def _where(wc_oids: list[str] | None, where_clauses: dict[str, list[str]],
           conditions: dict[str, dict[str, Any]]) -> dict[str, tuple]:
    """A value-level item's where clause as variable -> (comparator, values)."""
    out: dict[str, tuple] = {}
    for wc_oid in (wc_oids or [])[:1]:   # the first where clause; DDE writes one per item
        for condition_oid in where_clauses.get(wc_oid) or []:
            for check in (conditions.get(condition_oid) or {}).get("rangeChecks") or []:
                variable = str(check.get("item") or "").rsplit(".", 1)[-1]
                if variable:
                    out[variable] = (str(check.get("comparator") or "EQ").upper(),
                                     tuple(str(v) for v in check.get("checkValues") or []))
    return out


def _matches(where: dict[str, tuple], conditions: tuple, context: dict[str, str]) -> bool:
    for condition in conditions:
        tested = where.get(condition.variable)
        if tested is None:
            return False
        if condition.comparator == "NE":
            if tested != ("NE", condition.values):
                return False
        elif not all(admits(tested[0], tested[1], v) for v in condition.values):
            return False
    for variable, value in context.items():
        tested = where.get(variable)
        if tested is not None and not admits(tested[0], tested[1], value):
            return False
    return True


def _testcd_decodes(dds: dict[str, Any], items_by_oid: dict[str, dict[str, Any]]) -> dict:
    """(dataset, variable) -> {codedValue: decode} for every coded Define variable."""
    codelists = {c.get("OID"): c for c in dds.get("codeLists") or []}
    out: dict[tuple, dict[str, str]] = {}
    for oid, item in items_by_oid.items():
        codelist = codelists.get(item.get("codeList"))
        if not codelist:
            continue
        parts = oid.split(".")
        if len(parts) != 3:
            continue
        out[(parts[1], parts[2])] = {
            str(t.get("codedValue")): str(t.get("decode") or t.get("codedValue"))
            for t in codelist.get("codeListItems") or [] if t.get("codedValue")
        }
    return out


def paired_name_variable(variable: str) -> str | None:
    """The name variable paired with a code variable: VSTESTCD -> VSTEST, TSPARMCD -> TSPARM."""
    if variable.endswith(("TESTCD", "PARMCD")):
        return variable[:-2]
    return None


def target_dataset(target: Target, domain: str | None, define: DefineIndex) -> str | None:
    """The dataset a target belongs to: as qualified, else by prefix, else the group domain."""
    if target.dataset:
        return target.dataset
    if domain and target.variable.startswith(domain):
        return domain
    prefix = target.variable[:2]
    if define.has_dataset(prefix):
        return prefix
    return domain


def oid_pairs(links: list[dict[str, Any]]) -> str:
    """The SDTMItemOIDs alias value: space-separated DATASET.VARIABLE=OID pairs."""
    return " ".join(f"{link['dataset']}.{link['variable']}={link['item']}"
                    for link in links if link.get("item"))
