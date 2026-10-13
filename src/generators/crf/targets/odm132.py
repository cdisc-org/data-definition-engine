"""ODM 1.3.2 target: FormDef + ItemGroupDef, with the Section level flattened.

ODM 1.3.2 has only two levels of containment (``FormDef -> ItemGroupDef``) where the DDS
has three (Form -> Section -> Concept). Concepts therefore become the ItemGroupDefs the
Form references directly, and the Section survives as
``Alias Context=section Name="<SEC OID>|<label>"`` on each Concept plus
``Alias Context=sectionOrder`` on the Form, so a stylesheet can rebuild the headings.

Everything ODM 2.0 says with a native element, this version says with an ``Alias``.
"""
from __future__ import annotations

import datetime
import logging
from typing import Any

import odmlib.odm_1_3_2.model as ODM

from generators.crf.constants import (CTX_BC, CTX_CDISC_NOTES, CTX_COMPLETION,
                                      CTX_CRF_SPEC, CTX_DEFINITION, CTX_IMPLEMENTATION,
                                      CTX_MAPPING, CTX_NCI, CTX_PRESPECIFIED, CTX_PROMPT,
                                      CTX_SDTM, CTX_SDTM_SPEC, CTX_SECTION,
                                      CTX_SECTION_ORDER, CTX_SELECTION, CTX_STANDARD,
                                      CTX_SUBSET_OF, CTX_TIMING, CTX_USDM,
                                      DATATYPE_TO_ODM, DEFAULT_ORIGINATOR,
                                      DEFAULT_SOURCE_SYSTEM, NS_URI, REPEATING_TO_132)
from generators.crf.targets.base import OdmTarget, as_list

logger = logging.getLogger(__name__)

BC_SYSTEM_HINT = "biomedicalconcepts"
SDTM_SYSTEM_HINT = "datasetspecializations"


class Odm132Target(OdmTarget):
    """Builds ODM 1.3.2 objects."""

    version = "1.3.2"
    package = "odm_1_3_2"
    ns_uri = NS_URI["odm_1_3_2"]
    model = ODM

    def __init__(self) -> None:
        #: unit symbol -> MeasurementUnit OID, filled while building ItemDefs
        self.measurement_units: dict[str, str] = {}
        #: CodeList OID -> the DDS codelist dict, for resolving unit value lists
        self.codelist_index: dict[str, dict[str, Any]] = {}

    # -- text -----------------------------------------------------------------
    def translated(self, text: str, lang: str = "en") -> Any:
        return ODM.TranslatedText(_content=str(text), lang=lang)

    def description(self, text: str, lang: str = "en") -> Any:
        desc = ODM.Description()
        desc.TranslatedText.append(self.translated(text, lang))
        return desc

    # -- document -------------------------------------------------------------
    def odm_root(self, header: dict[str, Any]) -> Any:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return ODM.ODM(
            FileOID=header.get("fileOID") or "ODM.DDS.CRF",
            FileType=header.get("fileType") or "Snapshot",
            Granularity="Metadata",
            CreationDateTime=header.get("creationDateTime") or now,
            ODMVersion="1.3.2",
            Originator=header.get("originator") or DEFAULT_ORIGINATOR,
            SourceSystem=header.get("sourceSystem") or DEFAULT_SOURCE_SYSTEM,
            SourceSystemVersion=header.get("sourceSystemVersion") or _odmlib_version(),
        )

    def study(self, header: dict[str, Any], lang: str) -> Any:
        study = ODM.Study(OID=header.get("studyOID") or "ODM.STUDY")
        gv = ODM.GlobalVariables()
        gv.StudyName = ODM.StudyName(_content=header.get("studyName") or "STUDY")
        gv.StudyDescription = ODM.StudyDescription(
            _content=header.get("studyDescription") or header.get("studyName") or "NA")
        gv.ProtocolName = ODM.ProtocolName(
            _content=header.get("protocolName") or header.get("studyName") or "STUDY")
        study.GlobalVariables = gv
        return study

    def metadata_version(self, header: dict[str, Any], lang: str) -> Any:
        return ODM.MetaDataVersion(
            OID=header.get("OID") or "MDV.1",
            Name=header.get("name") or header.get("studyName") or "MDV",
            Description=header.get("description") or "",
        )

    def assemble(self, header: dict[str, Any], crf_objects: dict[str, Any],
                 lang: str) -> Any:
        odm = self.odm_root(header)
        study = self.study(header, lang)

        if self.measurement_units:
            basic = ODM.BasicDefinitions()
            for symbol, oid in self.measurement_units.items():
                unit = ODM.MeasurementUnit(OID=oid, Name=symbol)
                sym = ODM.Symbol()
                sym.TranslatedText.append(self.translated(symbol, lang))
                unit.Symbol = sym
                basic.MeasurementUnit.append(unit)
            study.BasicDefinitions = basic

        mdv = self.metadata_version(header, lang)
        if crf_objects.get("Protocol") is not None:
            mdv.Protocol = crf_objects["Protocol"]
        for event in crf_objects.get("StudyEventDef", []):
            mdv.StudyEventDef.append(event)
        for form in crf_objects.get("FormDef", []):
            mdv.FormDef.append(form)
        for group in crf_objects.get("ItemGroupDef", []):
            mdv.ItemGroupDef.append(group)
        for item in crf_objects.get("ItemDef", []):
            mdv.ItemDef.append(item)
        for codelist in crf_objects.get("CodeList", []):
            mdv.CodeList.append(codelist)

        study.MetaDataVersion.append(mdv)
        odm.Study.append(study)
        return odm

    # -- structure ------------------------------------------------------------
    def form(self, group: dict[str, Any], child_oids: list[tuple[str, bool]],
             lang: str) -> Any:
        form = ODM.FormDef(
            OID=group["OID"], Name=group.get("name") or group["OID"],
            Repeating=REPEATING_TO_132.get(group.get("repeating") or "No", "No"),
        )
        text = group.get("label") or group.get("description") or group.get("name")
        if text:
            form.Description = self.description(text, lang)
        # child_oids are the flattened Concepts, already in section order.
        for order, (oid, mandatory) in enumerate(child_oids, start=1):
            form.ItemGroupRef.append(ODM.ItemGroupRef(
                ItemGroupOID=oid, OrderNumber=order,
                Mandatory="Yes" if mandatory else "No"))
        for alias in as_list(group.get("aliases")):
            form.Alias.append(self.alias(alias["context"], alias["name"]))
        section_order = group.get("_sectionOrder") or []
        if section_order:
            form.Alias.append(self.alias(CTX_SECTION_ORDER, "|".join(section_order)))
        return form

    def section(self, group: dict[str, Any], child_oids: list[tuple[str, bool]],
                lang: str) -> None:
        """ODM 1.3.2 has no Section level; it is carried as an Alias on each Concept."""
        return None

    def concept(self, group: dict[str, Any], item_refs: list[Any], lang: str,
                section: dict[str, Any] | None = None) -> Any:
        igd = ODM.ItemGroupDef(
            OID=group["OID"], Name=group.get("name") or group["OID"],
            Repeating=REPEATING_TO_132.get(group.get("repeating") or "No", "No"),
        )
        text = group.get("label") or group.get("name")
        if text:
            igd.Description = self.description(text, lang)
        if group.get("domain"):
            igd.Domain = group["domain"]
        for ref in item_refs:
            igd.ItemRef.append(ref)

        if section is not None:
            label = section.get("label") or section.get("name") or ""
            igd.Alias.append(self.alias(CTX_SECTION, f"{section.get('OID')}|{label}"))
            if section.get("crfSectionInstructions"):
                igd.Alias.append(self.alias(CTX_COMPLETION,
                                            section["crfSectionInstructions"]))
        # Coding has no 1.3.2 equivalent, so provenance becomes contextual aliases.
        for coding in as_list(group.get("coding")):
            system = coding.get("codeSystem") or ""
            if BC_SYSTEM_HINT in system:
                igd.Alias.append(self.alias(CTX_BC, f"{system}/{coding.get('code')}"))
            elif SDTM_SYSTEM_HINT in system:
                igd.Alias.append(self.alias(CTX_SDTM_SPEC, f"{system}/{coding.get('code')}"))
        if group.get("crfSpecializationRef"):
            igd.Alias.append(self.alias(CTX_CRF_SPEC, group["crfSpecializationRef"]))
        for alias in as_list(group.get("aliases")):
            igd.Alias.append(self.alias(alias["context"], alias["name"]))
        return igd

    def item_def(self, item: dict[str, Any], lang: str) -> Any:
        attrs: dict[str, Any] = {
            "OID": item["OID"],
            "Name": item.get("name") or item["OID"],
            "DataType": DATATYPE_TO_ODM.get(item.get("dataType", "text"), "text"),
        }
        if item.get("length"):
            attrs["Length"] = int(item["length"])
        if item.get("significantDigits") is not None:
            attrs["SignificantDigits"] = int(item["significantDigits"])
        target = item.get("crfSdtmTarget") or {}
        if target.get("variables"):
            # Iversen's widely used 1.3.2 CRF stylesheet reads @SDSVarName.
            attrs["SDSVarName"] = target["variables"][0]
        if item.get("origin"):
            attrs["Origin"] = "CRF"
        item_def = ODM.ItemDef(**attrs)

        if item.get("description"):
            item_def.Description = self.description(item["description"], lang)
        if item.get("question"):
            question = ODM.Question()
            question.TranslatedText.append(self.translated(item["question"], lang))
            item_def.Question = question

        if item.get("codeList"):
            item_def.CodeListRef = ODM.CodeListRef(CodeListOID=item["codeList"])
        # ODM 2.0 points a result item at its unit item with ItemRef/@UnitsItemOID.
        # 1.3.2 has no such attribute, so the *unit's value* is resolved off that
        # sibling item and becomes a BasicDefinitions/MeasurementUnit reference.
        for unit_symbol in self._unit_symbols(item):
            item_def.MeasurementUnitRef.append(
                ODM.MeasurementUnitRef(MeasurementUnitOID=self.register_unit(unit_symbol)))

        # Everything ODM 2.0 has a native element for becomes an Alias here.
        for key, context in (("prompt", CTX_PROMPT),
                             ("definition", CTX_DEFINITION),
                             ("crfCompletionInstructions", CTX_COMPLETION),
                             ("implementationNotes", CTX_IMPLEMENTATION),
                             ("cdiscNotes", CTX_CDISC_NOTES),
                             ("mappingInstructions", CTX_MAPPING),
                             ("preSpecifiedValue", CTX_PRESPECIFIED),
                             ("crfSelectionType", CTX_SELECTION)):
            if item.get(key):
                item_def.Alias.append(self.alias(context, item[key]))
        for alias in as_list(item.get("aliases")):
            item_def.Alias.append(self.alias(alias["context"], alias["name"]))
        if target.get("annotation"):
            item_def.Alias.append(self.alias(CTX_SDTM, target["annotation"]))
        for coding in as_list(item.get("coding")):
            item_def.Alias.append(self.alias(CTX_NCI, coding.get("code")))
        return item_def

    def item_ref(self, item: dict[str, Any], order: int) -> Any:
        attrs: dict[str, Any] = {
            "ItemOID": item["OID"],
            "OrderNumber": order,
            "Mandatory": "Yes" if item.get("mandatory") else "No",
        }
        if item.get("role"):
            attrs["Role"] = item["role"]
        return ODM.ItemRef(**attrs)

    def codelist(self, codelist: dict[str, Any], lang: str) -> Any:
        cl = ODM.CodeList(
            OID=codelist["OID"], Name=codelist.get("name") or codelist["OID"],
            DataType=codelist.get("dataType") or "text",
        )
        for order, term in enumerate(codelist.get("codeListItems") or [], start=1):
            if not term.get("codedValue"):
                continue
            cli = ODM.CodeListItem(CodedValue=str(term["codedValue"]), OrderNumber=order)
            decode = ODM.Decode()
            decode.TranslatedText.append(
                self.translated(term.get("decode") or term["codedValue"], lang))
            cli.Decode = decode
            for coding in as_list(term.get("coding")):
                cli.Alias.append(self.alias(CTX_NCI, coding.get("code")))
            cl.CodeListItem.append(cli)
        for coding in as_list(codelist.get("coding")):
            cl.Alias.append(self.alias(CTX_NCI, coding.get("code")))
        if codelist.get("wasDerivedFrom"):
            cl.Alias.append(self.alias(CTX_SUBSET_OF, codelist["wasDerivedFrom"]))
        return cl

    def study_event(self, event: dict[str, Any], lang: str) -> Any:
        sed = ODM.StudyEventDef(
            OID=event["OID"], Name=event.get("name") or event["OID"],
            Repeating="Yes" if event.get("repeating") else "No",
            Type=event.get("type") or "Scheduled",
        )
        if event.get("category"):
            sed.Category = event["category"]
        text = event.get("label") or event.get("description")
        if text:
            sed.Description = self.description(text, lang)
        for order, form_oid in enumerate(event.get("itemGroups") or [], start=1):
            sed.FormRef.append(ODM.FormRef(
                FormOID=form_oid, OrderNumber=order, Mandatory="Yes"))
        timing = (event.get("occurrence") or {}).get("timing") or {}
        if timing.get("value"):
            sed.Alias.append(self.alias(CTX_TIMING, _timing_text(timing)))
        if event.get("crfEncounterRef"):
            sed.Alias.append(self.alias(CTX_USDM, event["crfEncounterRef"]))
        return sed

    def protocol(self, events: list[dict[str, Any]], standards: list[dict[str, Any]],
                 crf_objects: dict[str, Any]) -> Any:
        protocol = ODM.Protocol()
        for order, event in enumerate(events, start=1):
            protocol.StudyEventRef.append(ODM.StudyEventRef(
                StudyEventOID=event["OID"], OrderNumber=order, Mandatory="Yes"))
        # 1.3.2 has no Standards element at all, so every standard becomes an alias.
        # Protocol/Alias/@Context must be unique (XSD unique constraint UC-P-3), so the
        # standards share one alias rather than getting one each.
        names = [f"{s.get('name')} {s.get('version')}".strip() for s in standards
                 if s.get("name")]
        if names:
            protocol.Alias.append(self.alias(CTX_STANDARD, "; ".join(names)))
        return protocol

    def standards(self, standards: list[dict[str, Any]],
                  crf_objects: dict[str, Any]) -> None:
        """ODM 1.3.2 has no Standards element; see :meth:`protocol`."""
        return None

    def annotated_crf(self, leaf_id: str, href: str, title: str,
                      crf_objects: dict[str, Any]) -> None:
        """ODM 1.3.2 has no AnnotatedCRF or Leaf element."""
        return None

    # -- helpers --------------------------------------------------------------
    def _unit_symbols(self, item: dict[str, Any]) -> list[str]:
        """Unit values for an item, resolved from the item its ``unitsItem`` names.

        A unit item either pre-specifies a single value (``mmHg``) or offers a codelist
        of them, in which case every term is a measurement unit the result may carry.
        """
        units_oid = item.get("unitsItem")
        if not units_oid:
            return []
        unit_item = self.item_index.get(units_oid)
        if unit_item is None:
            logger.warning("item %s names unitsItem %s, which is not in the DDS",
                           item.get("OID"), units_oid)
            return []
        if unit_item.get("preSpecifiedValue"):
            return [str(unit_item["preSpecifiedValue"])]
        codelist = self.codelist_index.get(unit_item.get("codeList") or "")
        if codelist:
            return [str(t["codedValue"]) for t in codelist.get("codeListItems") or []
                    if t.get("codedValue")]
        return []

    def register_unit(self, symbol: str) -> str:
        """Register a measurement unit and return its OID."""
        if symbol not in self.measurement_units:
            self.measurement_units[symbol] = "MU." + symbol.upper().replace(" ", "-")
        return self.measurement_units[symbol]


def _timing_text(timing: dict[str, Any]) -> str:
    parts = [timing.get("type") or "", timing.get("value") or ""]
    if timing.get("label"):
        parts.append(f"({timing['label']})")
    return " ".join(p for p in parts if p)


def _odmlib_version() -> str:
    try:
        import odmlib
        return odmlib.__version__
    except Exception:  # noqa: BLE001 - version reporting must never break generation
        return "unknown"
