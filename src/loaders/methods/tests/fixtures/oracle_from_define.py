"""Build a methods-loader oracle from a Define-XML 2.1 file: a DDS without methods, and the answers.

    python oracle_from_define.py <define.xml> <prefix>

writes ``<prefix>_dds.json`` and ``<prefix>_expected.json``. The DDS holds the datasets, their
variable-level items (name, data type, length, description, origin type and source), the value
lists that hold a Derived item or a method, and their where clauses, with every method reference
stripped. The expected file holds what the methods loader is compared with:

* ``derived``: each Derived item's ``ItemRef/@MethodOID`` in the source (null when it has none);
* ``notDerived``: methods the source attaches to items that are not Derived, which the loader never
  assigns (Define-XML 2.1 requires a method only on a Derived item);
* ``methods``: each source MethodDef's description, whitespace collapsed.

A value-level item is named after its variable, as in a DDS: the CDISC 2019 example names some of
them otherwise (``VSSTRESN6``, ``RACE1``). An ItemDef that several datasets share (``IT.USUBJID``)
becomes one item per dataset, ``IT.<dataset>.<name>``, because the DDE writes dataset-specific item
OIDs and the loader reads the first item with an OID. The fixtures were built from the CDISC sample
files named in ``README.md``.
"""
from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

NS = {"odm": "http://www.cdisc.org/ns/odm/v1.3", "def": "http://www.cdisc.org/ns/def/v2.1"}
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def text(element: ET.Element | None) -> str | None:
    """The English (or first) TranslatedText under an element's Description."""
    if element is None:
        return None
    texts = element.findall("odm:Description/odm:TranslatedText", NS)
    chosen = next((t for t in texts if t.get(XML_LANG) == "en"), texts[0] if texts else None)
    return " ".join((chosen.text or "").split()) if chosen is not None else None


def derived(item_def: ET.Element) -> bool:
    return any(o.get("Type") == "Derived" for o in item_def.findall("def:Origin", NS))


def build(define: Path) -> tuple[dict, dict]:
    mdv = ET.parse(define).find(".//odm:MetaDataVersion", NS)
    item_defs = {i.get("OID"): i for i in mdv.findall("odm:ItemDef", NS)}
    value_lists = {v.get("OID"): v for v in mdv.findall("def:ValueListDef", NS)}
    where_defs = {w.get("OID"): w for w in mdv.findall("def:WhereClauseDef", NS)}
    groups = mdv.findall("odm:ItemGroupDef", NS)
    shared = {oid for oid, n in Counter(r.get("ItemOID") for g in groups
                                        for r in g.findall("odm:ItemRef", NS)).items() if n > 1}
    expected: dict = {"derived": {}, "notDerived": {}}
    conditions: dict[str, dict] = {}
    where_clauses: dict[str, dict] = {}

    def item(ref: ET.Element, dataset: str, rename: dict[str, str], variable: str | None = None) -> dict:
        source = item_defs[ref.get("ItemOID")]
        oid = rename.get(source.get("OID"), source.get("OID"))
        out = {"OID": oid, "name": variable or source.get("Name"), "dataType": source.get("DataType")}
        for attr, key in (("Length", "length"), ("SignificantDigits", "significantDigits")):
            if source.get(attr):
                out[key] = int(source.get(attr))
        if text(source):
            out["description"] = text(source)
        origins = [{"type": o.get("Type"), **({"source": o.get("Source")} if o.get("Source") else {})}
                   for o in source.findall("def:Origin", NS)]
        if origins:
            out["origin"] = origins
        if derived(source):
            expected["derived"][oid] = ref.get("MethodOID")
        elif ref.get("MethodOID"):
            expected["notDerived"][oid] = ref.get("MethodOID")
        return out

    def where_clause(wc_oid: str, rename: dict[str, str]) -> None:
        if wc_oid in where_clauses:
            return
        refs = []
        for n, check in enumerate(where_defs[wc_oid].findall("odm:RangeCheck", NS), start=1):
            cond_oid = f"COND.{wc_oid.removeprefix('WC.')}.{n}"
            variable = check.get(f"{{{NS['def']}}}ItemOID")
            conditions[cond_oid] = {"OID": cond_oid, "rangeChecks": [{
                "comparator": check.get("Comparator"), "softHard": check.get("SoftHard"),
                "item": rename.get(variable, variable),
                "checkValues": [v.text for v in check.findall("odm:CheckValue", NS)]}]}
            refs.append(cond_oid)
        where_clauses[wc_oid] = {"OID": wc_oid, "conditions": refs}

    item_groups = []
    for group in groups:
        dataset = group.get("Name")
        rename = {oid: f"IT.{dataset}.{item_defs[oid].get('Name')}" for oid in shared}
        out = {"OID": group.get("OID"), "name": dataset, "domain": group.get("Domain") or dataset,
               **({"standard": group.get(f"{{{NS['def']}}}StandardOID")}
                  if group.get(f"{{{NS['def']}}}StandardOID") else {}),
               "description": text(group), "purpose": group.get("Purpose"),
               "structure": group.get(f"{{{NS['def']}}}Structure"), "items": [], "slices": []}
        for ref in group.findall("odm:ItemRef", NS):
            out["items"].append(item(ref, dataset, rename))
            vl_ref = item_defs[ref.get("ItemOID")].find("def:ValueListRef", NS)
            if vl_ref is None:
                continue
            vl_oid = vl_ref.get("ValueListOID")
            vl_refs = value_lists[vl_oid].findall("odm:ItemRef", NS)
            if not any(derived(item_defs[r.get("ItemOID")]) or r.get("MethodOID") for r in vl_refs):
                continue    # nothing in it for the methods loader
            vl_items = []
            for vl_item_ref in vl_refs:
                vl_item = item(vl_item_ref, dataset, rename, item_defs[ref.get("ItemOID")].get("Name"))
                wc_oids = [w.get("WhereClauseOID") for w in vl_item_ref.findall("def:WhereClauseRef", NS)]
                for wc_oid in wc_oids:
                    where_clause(wc_oid, rename)
                vl_items.append({**vl_item, "applicableWhen": wc_oids})
            out["slices"].append({"OID": vl_oid, "type": "ValueList", "items": vl_items})
        if not out["slices"]:
            del out["slices"]
        item_groups.append(out)

    study = ET.parse(define).find(".//odm:Study", NS)
    gv = {k: study.findtext(f"odm:GlobalVariables/odm:{k}", namespaces=NS)
          for k in ("StudyName", "StudyDescription", "ProtocolName")}
    dds = {"OID": mdv.get("OID"), "name": mdv.get("Name"), "description": mdv.get("Description"),
           "studyOID": study.get("OID"), "studyName": gv["StudyName"],
           "studyDescription": " ".join((gv["StudyDescription"] or "").split()), "protocolName": gv["ProtocolName"],
           "standards": [{"OID": st.get("OID"), "name": st.get("Name"), "type": st.get("Type"),
                          "version": st.get("Version"), "status": st.get("Status"),
                          **({"publishingSet": st.get("PublishingSet")} if st.get("PublishingSet") else {})}
                         for st in mdv.findall("def:Standards/def:Standard", NS)],
           "itemGroups": item_groups, "conditions": list(conditions.values()),
           "whereClauses": list(where_clauses.values()), "methods": []}
    expected["methods"] = {m.get("OID"): text(m) for m in mdv.findall("odm:MethodDef", NS)}
    return dds, expected


def dump(content: dict, path: Path) -> None:
    """JSON with one item, condition or where clause per line, so a diff names the object."""
    def nested(value) -> bool:     # a list of objects with OIDs (items, slices, itemGroups, ...)
        return isinstance(value, list) and any(isinstance(v, dict) and "OID" in v for v in value)

    def lines(value, indent: str) -> str:
        if isinstance(value, dict) and ("OID" not in value or any(nested(v) for v in value.values())):
            inner = [f'{indent}  {json.dumps(k)}: {lines(v, indent + "  ")}' for k, v in value.items()]
            return "{\n" + ",\n".join(inner) + f"\n{indent}}}"
        if nested(value):
            inner = [f"{indent}  {lines(v, indent + '  ')}" for v in value]
            return "[\n" + ",\n".join(inner) + f"\n{indent}]"
        return json.dumps(value, ensure_ascii=False)
    path.write_text(lines(content, "") + "\n", encoding="utf-8")


def main() -> None:
    define, prefix = Path(sys.argv[1]), sys.argv[2]
    dds, expected = build(define)
    dump(dds, Path(f"{prefix}_dds.json"))
    dump(expected, Path(f"{prefix}_expected.json"))
    print(f"{len(dds['itemGroups'])} datasets, {len(expected['derived'])} Derived items "
          f"({sum(1 for m in expected['derived'].values() if m)} with a method), "
          f"{len(expected['notDerived'])} methods on items that are not Derived")


if __name__ == "__main__":
    main()
