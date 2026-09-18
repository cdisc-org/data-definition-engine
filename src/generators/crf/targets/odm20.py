"""ODM 2.0 target: Form/Section/Concept as typed ItemGroupDefs, with native elements."""
from __future__ import annotations

import datetime
import logging
from typing import Any

import odmlib.odm_2_0.model as ODM

from generators.crf.constants import (ACRF_HREF, ACRF_LEAF_ID, CTX_SDTM, CTX_STANDARD,
                                      DATATYPE_TO_ODM, DEFAULT_ORIGINATOR,
                                      DEFAULT_SOURCE_SYSTEM, NS_URI, ODM20_CONTEXT,
                                      ODM20_STANDARD_NAMES, STANDARD_STATUS)
from generators.crf.targets.base import OdmTarget, as_list

logger = logging.getLogger(__name__)

#: ODM 2.0 MetaDataVersion child order, from the model. Objects must be attached in
#: this order or ``validate()`` reports a sequence error.
MDV_ORDER = ("Description", "Include", "Standards", "AnnotatedCRF", "SupplementalDoc",
             "ValueListDef", "WhereClauseDef", "Protocol", "WorkflowDef",
             "StudyEventGroupDef", "StudyEventDef", "ItemGroupDef", "ItemDef",
             "CodeList", "ConditionDef", "MethodDef", "CommentDef", "Leaf")


class Odm20Target(OdmTarget):
    """Builds ODM 2.0 objects."""

    version = "2.0"
    package = "odm_2_0"
    ns_uri = NS_URI["odm_2_0"]
    model = ODM

    # -- text -----------------------------------------------------------------
    def translated(self, text: str, lang: str = "en") -> Any:
        # ODM 2.0 makes TranslatedText/@Type required.
        return ODM.TranslatedText(_content=str(text), lang=lang, Type="text")

    def description(self, text: str, lang: str = "en") -> Any:
        desc = ODM.Description()
        desc.TranslatedText.append(self.translated(text, lang))
        return desc

    def _wrap(self, cls: Any, text: str, lang: str) -> Any:
        obj = cls()
        obj.TranslatedText.append(self.translated(text, lang))
        return obj

    # -- document -------------------------------------------------------------
    def odm_root(self, header: dict[str, Any]) -> Any:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return ODM.ODM(
            FileOID=header.get("fileOID") or "ODM.DDS.CRF",
            FileType=header.get("fileType") or "Snapshot",
            Granularity="Metadata",
            CreationDateTime=header.get("creationDateTime") or now,
            ODMVersion="2.0",
            Originator=header.get("originator") or DEFAULT_ORIGINATOR,
            SourceSystem=header.get("sourceSystem") or DEFAULT_SOURCE_SYSTEM,
            SourceSystemVersion=header.get("sourceSystemVersion") or _odmlib_version(),
            Context=ODM20_CONTEXT.get(header.get("context") or "Other", "Exchange"),
        )

    def study(self, header: dict[str, Any], lang: str) -> Any:
        study = ODM.Study(
            OID=header.get("studyOID") or "ODM.STUDY",
            StudyName=header.get("studyName") or "STUDY",
            ProtocolName=header.get("protocolName") or header.get("studyName") or "STUDY",
        )
        if header.get("studyDescription"):
            study.Description = self.description(header["studyDescription"], lang)
        return study

    def metadata_version(self, header: dict[str, Any], lang: str) -> Any:
        mdv = ODM.MetaDataVersion(
            OID=header.get("OID") or "MDV.1",
            Name=header.get("name") or header.get("studyName") or "MDV",
        )
        if header.get("description"):
            mdv.Description = self.description(header["description"], lang)
        return mdv

    def assemble(self, header: dict[str, Any], crf_objects: dict[str, Any],
                 lang: str) -> Any:
        odm = self.odm_root(header)
        study = self.study(header, lang)
        mdv = self.metadata_version(header, lang)

        if crf_objects.get("Standards") is not None:
            mdv.Standards = crf_objects["Standards"]
        if crf_objects.get("AnnotatedCRF") is not None:
            mdv.AnnotatedCRF = crf_objects["AnnotatedCRF"]
        if crf_objects.get("Protocol") is not None:
            mdv.Protocol = crf_objects["Protocol"]
        for group_def in crf_objects.get("StudyEventGroupDef", []):
            mdv.StudyEventGroupDef.append(group_def)
        for event in crf_objects.get("StudyEventDef", []):
            mdv.StudyEventDef.append(event)
        # Forms, then Sections, then Concepts: a stable, readable document order.
        for group in crf_objects.get("ItemGroupDef", []):
            mdv.ItemGroupDef.append(group)
        for item in crf_objects.get("ItemDef", []):
            mdv.ItemDef.append(item)
        for codelist in crf_objects.get("CodeList", []):
            mdv.CodeList.append(codelist)
        for leaf in crf_objects.get("Leaf", []):
            mdv.Leaf.append(leaf)

        study.MetaDataVersion.append(mdv)
        odm.Study.append(study)
        return odm

    # -- structure ------------------------------------------------------------
    def form(self, group: dict[str, Any], child_oids: list[tuple[str, bool]],
             lang: str) -> Any:
        form = ODM.ItemGroupDef(
            OID=group["OID"], Name=group.get("name") or group["OID"],
            Repeating=group.get("repeating") or "No", Type="Form",
        )
        text = group.get("label") or group.get("description") or group.get("name")
        if text:
            form.Description = self.description(text, lang)
        if group.get("domain"):
            form.Domain = group["domain"]
        for order, (oid, mandatory) in enumerate(child_oids, start=1):
            form.ItemGroupRef.append(ODM.ItemGroupRef(
                ItemGroupOID=oid, OrderNumber=order,
                Mandatory="Yes" if mandatory else "No"))
        self._add_aliases(form, group)
        return form

    def section(self, group: dict[str, Any], child_oids: list[tuple[str, bool]],
                lang: str) -> Any:
        section = ODM.ItemGroupDef(
            OID=group["OID"], Name=group.get("name") or group["OID"],
            Repeating=group.get("repeating") or "No", Type="Section",
        )
        text = group.get("label") or group.get("name")
        if text:
            section.Description = self.description(text, lang)
        for order, (oid, mandatory) in enumerate(child_oids, start=1):
            section.ItemGroupRef.append(ODM.ItemGroupRef(
                ItemGroupOID=oid, OrderNumber=order,
                Mandatory="Yes" if mandatory else "No"))
        self._add_aliases(section, group)
        return section

    def concept(self, group: dict[str, Any], item_refs: list[Any], lang: str,
                section: dict[str, Any] | None = None) -> Any:
        concept = ODM.ItemGroupDef(
            OID=group["OID"], Name=group.get("name") or group["OID"],
            Repeating=group.get("repeating") or "No", Type="Concept",
        )
        text = group.get("label") or group.get("name")
        if text:
            concept.Description = self.description(text, lang)
        if group.get("domain"):
            concept.Domain = group["domain"]
        for ref in item_refs:
            concept.ItemRef.append(ref)
        for coding in as_list(group.get("coding")):
            concept.Coding.append(self._coding(coding))
        self._add_aliases(concept, group)
        return concept

    def item_def(self, item: dict[str, Any], lang: str) -> Any:
        attrs: dict[str, Any] = {
            "OID": item["OID"],
            "Name": item.get("name") or item["OID"],
            "DataType": DATATYPE_TO_ODM.get(item.get("dataType", "text"), "text"),
        }
        if item.get("length"):
            attrs["Length"] = int(item["length"])
        if item.get("displayFormat"):
            attrs["DisplayFormat"] = item["displayFormat"]
        item_def = ODM.ItemDef(**attrs)

        if item.get("description"):
            item_def.Description = self.description(item["description"], lang)
        # Native elements: the whole reason ODM 2.0 output is richer than 1.3.2.
        for key, cls in (("definition", ODM.Definition),
                         ("question", ODM.Question),
                         ("prompt", ODM.Prompt),
                         ("crfCompletionInstructions", ODM.CRFCompletionInstructions),
                         ("implementationNotes", ODM.ImplementationNotes),
                         ("cdiscNotes", ODM.CDISCNotes)):
            if item.get(key):
                setattr(item_def, cls.__name__, self._wrap(cls, item[key], lang))

        if item.get("codeList"):
            item_def.CodeListRef = ODM.CodeListRef(CodeListOID=item["codeList"])
        for coding in as_list(item.get("coding")):
            item_def.Coding.append(self._coding(coding))

        for alias in as_list(item.get("aliases")):
            item_def.Alias.append(self.alias(alias["context"], alias["name"]))
        if item.get("mappingInstructions"):
            item_def.Alias.append(self.alias("mappingInstructions",
                                             item["mappingInstructions"]))
        target = item.get("crfSdtmTarget") or {}
        if target.get("annotation"):
            item_def.Alias.append(self.alias(CTX_SDTM, target["annotation"]))
        if item.get("crfSelectionType"):
            item_def.Alias.append(self.alias("selectionType", item["crfSelectionType"]))
        return item_def

    def item_ref(self, item: dict[str, Any], order: int) -> Any:
        attrs: dict[str, Any] = {
            "ItemOID": item["OID"],
            "OrderNumber": order,
            "Mandatory": "Yes" if item.get("mandatory") else "No",
        }
        if item.get("unitsItem"):
            attrs["UnitsItemOID"] = item["unitsItem"]
        if item.get("preSpecifiedValue"):
            attrs["PreSpecifiedValue"] = str(item["preSpecifiedValue"])
        if item.get("role"):
            attrs["Role"] = item["role"]
        ref = ODM.ItemRef(**attrs)
        for origin in as_list(item.get("origin")):
            ref.Origin.append(ODM.Origin(Type=origin["type"], Source=origin.get("source")))
        return ref

    def codelist(self, codelist: dict[str, Any], lang: str) -> Any:
        attrs: dict[str, Any] = {
            "OID": codelist["OID"],
            "Name": codelist.get("name") or codelist["OID"],
            "DataType": codelist.get("dataType") or "text",
        }
        if codelist.get("standard"):
            attrs["StandardOID"] = codelist["standard"]
        cl = ODM.CodeList(**attrs)
        for order, term in enumerate(codelist.get("codeListItems") or [], start=1):
            if not term.get("codedValue"):
                continue
            cli = ODM.CodeListItem(CodedValue=str(term["codedValue"]), OrderNumber=order)
            decode = term.get("decode") or term["codedValue"]
            cli.Decode = ODM.Decode()
            cli.Decode.TranslatedText.append(self.translated(decode, lang))
            for coding in as_list(term.get("coding")):
                cli.Coding.append(self._coding(coding))
            cl.CodeListItem.append(cli)
        for coding in as_list(codelist.get("coding")):
            cl.Coding.append(self._coding(coding))
        if codelist.get("wasDerivedFrom"):
            cl.Alias.append(self.alias("subsetOf", codelist["wasDerivedFrom"]))
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
            sed.ItemGroupRef.append(ODM.ItemGroupRef(
                ItemGroupOID=form_oid, OrderNumber=order, Mandatory="Yes"))
        for coding in as_list(event.get("coding")):
            sed.Coding.append(self._coding(coding))
        timing = (event.get("occurrence") or {}).get("timing") or {}
        if timing.get("value"):
            sed.Alias.append(self.alias("timing", _timing_text(timing)))
        if event.get("crfEncounterRef"):
            sed.Alias.append(self.alias("USDM", event["crfEncounterRef"]))
        return sed

    def protocol(self, events: list[dict[str, Any]], standards: list[dict[str, Any]],
                 crf_objects: dict[str, Any]) -> Any:
        """Protocol -> StudyEventGroupRef -> StudyEventGroupDef -> StudyEventRef.

        ODM 2.0 removed ``Protocol/StudyEventRef``; events are only reachable through a
        StudyEventGroupDef. One group is emitted per epoch (the events' ``category``).
        """
        protocol = ODM.Protocol()
        by_epoch: dict[str, list[dict[str, Any]]] = {}
        for event in events:
            by_epoch.setdefault(event.get("category") or "Study", []).append(event)

        for order, (epoch, epoch_events) in enumerate(by_epoch.items(), start=1):
            group_oid = "SEG." + epoch.upper().replace(" ", "-")
            protocol.StudyEventGroupRef.append(ODM.StudyEventGroupRef(
                StudyEventGroupOID=group_oid, OrderNumber=order, Mandatory="Yes"))
            group = ODM.StudyEventGroupDef(OID=group_oid, Name=epoch)
            for event_order, event in enumerate(epoch_events, start=1):
                group.StudyEventRef.append(ODM.StudyEventRef(
                    StudyEventOID=event["OID"], OrderNumber=event_order, Mandatory="Yes"))
            crf_objects.setdefault("StudyEventGroupDef", []).append(group)

        # CDASHIG has no legal Standard/@Name in the 2.0 XSD, so it is declared here
        # instead. Protocol/Alias/@Context must be unique, so any such standards share
        # a single alias.
        names = [f"{s.get('name')} {s.get('version')}".strip() for s in standards
                 if s.get("name") and s.get("name") not in ODM20_STANDARD_NAMES]
        if names:
            protocol.Alias.append(self.alias(CTX_STANDARD, "; ".join(names)))
        return protocol

    def standards(self, standards: list[dict[str, Any]],
                  crf_objects: dict[str, Any]) -> Any | None:
        """Native Standards, skipping any name the 2.0 XSD does not allow."""
        emitted = [s for s in standards if s.get("name") in ODM20_STANDARD_NAMES]
        if not emitted:
            return None
        container = ODM.Standards()
        for standard in emitted:
            attrs: dict[str, Any] = {
                "OID": standard["OID"],
                "Name": standard["name"],
                "Type": standard.get("type") or "IG",
                "Version": str(standard.get("version") or ""),
                # @Status is required in ODM 2.0 and is title-case.
                "Status": STANDARD_STATUS.get(
                    str(standard.get("status", "")).upper(), "Final"),
            }
            if standard.get("publishingSet"):
                attrs["PublishingSet"] = standard["publishingSet"]
            container.Standard.append(ODM.Standard(**attrs))
        return container

    def annotated_crf(self, leaf_id: str, href: str, title: str,
                      crf_objects: dict[str, Any]) -> Any:
        """AnnotatedCRF plus the Leaf it points at."""
        acrf = ODM.AnnotatedCRF()
        acrf.DocumentRef.append(ODM.DocumentRef(LeafID=leaf_id))
        leaf = ODM.Leaf(ID=leaf_id, href=href)
        leaf.Title = ODM.Title(_content=title)
        crf_objects.setdefault("Leaf", []).append(leaf)
        return acrf

    # -- helpers --------------------------------------------------------------
    def _coding(self, coding: dict[str, Any]) -> Any:
        attrs: dict[str, Any] = {"Code": str(coding.get("code"))}
        if coding.get("codeSystem"):
            attrs["System"] = coding["codeSystem"]
        if coding.get("codeSystemVersion"):
            attrs["SystemVersion"] = str(coding["codeSystemVersion"])
        if coding.get("decode"):
            attrs["Label"] = coding["decode"]
        return ODM.Coding(**attrs)

    def _add_aliases(self, obj: Any, group: dict[str, Any]) -> None:
        for alias in as_list(group.get("aliases")):
            obj.Alias.append(self.alias(alias["context"], alias["name"]))
        if group.get("crfSectionInstructions"):
            obj.Alias.append(self.alias("completionInstructions",
                                        group["crfSectionInstructions"]))
        if group.get("crfSpecializationRef"):
            obj.Alias.append(self.alias("CRFSpecialization", group["crfSpecializationRef"]))


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
