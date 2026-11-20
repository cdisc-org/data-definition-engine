"""The conformance checks the methods loader runs on the DDS it is about to write.

They are the CDISC Define-XML 2.1 conformance rules that concern methods, plus what ODM v2.0 requires
of a MethodDef, checked on the DDS rather than on a define.xml so a failure names the DDS object:

* rule 73: every Derived item has a ``method``;
* rule 74: every ``method`` names an OID in ``methods``;
* rules 56 and 210: every method has a non-empty ``description`` (a ``__PLACEHOLDER__`` is an open
  item for a person, not a failure);
* rules 208 and 209: every method's ``type`` is Computation or Imputation;
* rule 221: every expression has a ``context``;
* ODM v2.0: every method has a ``signature``, and every expression exactly one of ``expression``
  (inline code) or ``externalCodeLib``;
* and every method OID appears once.

A failure stops the loader before it writes anything (``MethodsLoader.process``).
"""
from __future__ import annotations

from typing import Any

from loaders.common.patch import is_placeholder

METHOD_TYPES = ("Computation", "Imputation")
#: an item's own Define items: OID -> (dataset, variable, item, ValueListDef OID or None)
DefineItems = dict[str, tuple[str, str, dict[str, Any], str | None]]


def is_derived(item: dict[str, Any]) -> bool:
    """Whether any of the item's origins has type Derived (aCRF pages or not)."""
    origins = item.get("origin")
    if isinstance(origins, dict):
        origins = [origins]
    return any(isinstance(o, dict) and o.get("type") == "Derived" for o in origins or [])


def has_method(item: dict[str, Any]) -> bool:
    """Whether the item names a method: set, and not the placeholder string."""
    value = item.get("method")
    return bool(value) and not is_placeholder(value)


def description_text(value: Any) -> str:
    """A description as text: a string, or the values of a DDS TranslatedText joined."""
    if isinstance(value, dict):
        return " ".join(str(t.get("value") or "") for t in value.get("translations") or []
                        if isinstance(t, dict)).strip()
    return "" if value is None else str(value).strip()


def check(dds: dict[str, Any], items: DefineItems) -> list[str]:
    """Every conformance problem in a DDS, as a sentence naming the object; empty when it conforms."""
    problems: list[str] = []
    methods = [m for m in dds.get("methods") or [] if isinstance(m, dict)]
    oids: set[str] = set()
    for method in methods:
        oid = method.get("OID")
        if not oid:
            problems.append(f"a method has no OID: {method.get('name')!r}")
            continue
        if oid in oids:
            problems.append(f"{oid}: defined twice in methods")
        oids.add(oid)
        problems += [f"{oid}: {p}" for p in method_problems(method)]
    for oid, (_, _, item, _) in items.items():
        if is_derived(item) and not has_method(item):
            problems.append(f"{oid}: Derived item without a method (rule 73)")
        if has_method(item) and item["method"] not in oids:
            problems.append(f"{oid}: method {item['method']} is not in methods (rule 74)")
    return problems


def method_problems(method: dict[str, Any]) -> list[str]:
    """What is wrong with one DDS method (empty when it conforms)."""
    problems: list[str] = []
    if not description_text(method.get("description")):
        problems.append("empty description (rules 56, 210)")
    if method.get("type") not in METHOD_TYPES:
        problems.append(f"type {method.get('type')!r} is not Computation or Imputation (rules 208, 209)")
    if not isinstance(method.get("signature"), dict):
        problems.append("no signature (ODM v2.0 requires a MethodSignature)")
    for n, expr in enumerate(method.get("expressions") or [], start=1):
        if not isinstance(expr, dict):
            problems.append(f"expression {n} is not an object")
            continue
        if not str(expr.get("context") or "").strip():
            problems.append(f"expression {n} has no context (rule 221)")
        bodies = [k for k in ("expression", "externalCodeLib") if expr.get(k)]
        if len(bodies) != 1:
            problems.append(f"expression {n} has {len(bodies)} bodies; ODM v2.0 needs exactly one of "
                            "expression or externalCodeLib")
    return problems
