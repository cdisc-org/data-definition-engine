"""The ODM version abstraction.

Every structural difference between ODM 1.3.2 and ODM 2.0 lives behind this surface, so
the loader classes are written once. The differences that matter:

* a Form is a ``FormDef`` in 1.3.2 and an ``ItemGroupDef Type="Form"`` in 2.0
* 1.3.2 has no Section or Concept level, so the tree is flattened and the Section
  survives as an ``Alias``
* 2.0 has native ``Prompt``/``Definition``/``CRFCompletionInstructions``/
  ``ImplementationNotes``/``CDISCNotes`` and ``Coding``; 1.3.2 expresses all of them as
  ``Alias`` with the matching context from :mod:`generators.crf.constants`
* units are ``ItemRef/@UnitsItemOID`` in 2.0 and ``MeasurementUnitRef`` plus a
  ``BasicDefinitions/MeasurementUnit`` in 1.3.2
* visits reach forms through ``Protocol/StudyEventGroupRef -> StudyEventGroupDef`` in
  2.0 and ``Protocol/StudyEventRef`` in 1.3.2
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

XLINK_URI = "http://www.w3.org/1999/xlink"
_ODM_OPEN = re.compile(r"<ODM\b")


def as_list(value: Any) -> list[Any]:
    """Normalize a DDS field that may be a single object or a list of them.

    Some DDS producers write ``coding`` and ``origin`` as a bare object where the schema
    says list. Reading defensively here means the generator can consume a DDS it did not
    write; ``loaders.common.dds_io.normalize_dds`` repairs the file itself.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


class OdmTarget(ABC):
    """Builds odmlib objects for one ODM version."""

    #: ODM version string, e.g. ``"2.0"``
    version: str
    #: odmlib model package name, e.g. ``"odm_2_0"``
    package: str
    #: XML namespace URI for this version
    ns_uri: str
    #: the odmlib model module
    model: Any

    #: CRF item OID -> the DDS item dict, so a target can resolve a sibling it needs
    #: (ODM 1.3.2 reads the unit value off the item that ``unitsItem`` points at).
    item_index: dict[str, dict[str, Any]] = {}

    def set_item_index(self, index: dict[str, dict[str, Any]]) -> None:
        """Give the target a lookup from item OID to the DDS item dict."""
        self.item_index = index

    # -- text -----------------------------------------------------------------
    @abstractmethod
    def translated(self, text: str, lang: str = "en") -> Any:
        """A TranslatedText carrying ``text``."""

    @abstractmethod
    def description(self, text: str, lang: str = "en") -> Any:
        """A Description wrapping one TranslatedText."""

    def alias(self, context: str, name: str) -> Any:
        """An Alias. Both versions share this shape."""
        return self.model.Alias(Context=context, Name=str(name))

    # -- document -------------------------------------------------------------
    @abstractmethod
    def odm_root(self, header: dict[str, Any]) -> Any:
        """The ODM root element."""

    @abstractmethod
    def study(self, header: dict[str, Any], lang: str) -> Any:
        """The Study element."""

    @abstractmethod
    def metadata_version(self, header: dict[str, Any], lang: str) -> Any:
        """The MetaDataVersion element."""

    @abstractmethod
    def assemble(self, header: dict[str, Any], crf_objects: dict[str, Any],
                 lang: str) -> Any:
        """Attach every built object to the document tree and return the ODM root."""

    # -- structure ------------------------------------------------------------
    @abstractmethod
    def form(self, group: dict[str, Any], child_oids: list[tuple[str, bool]],
             lang: str) -> Any:
        """A Form, referencing its children in order as ``(oid, mandatory)``."""

    @abstractmethod
    def section(self, group: dict[str, Any], child_oids: list[tuple[str, bool]],
                lang: str) -> Any | None:
        """A Section, or ``None`` when the version has no Section level."""

    @abstractmethod
    def concept(self, group: dict[str, Any], item_refs: list[Any], lang: str,
                section: dict[str, Any] | None = None) -> Any:
        """A Concept group holding the given ItemRefs."""

    @abstractmethod
    def item_def(self, item: dict[str, Any], lang: str) -> Any:
        """An ItemDef."""

    @abstractmethod
    def item_ref(self, item: dict[str, Any], order: int) -> Any:
        """An ItemRef."""

    @abstractmethod
    def codelist(self, codelist: dict[str, Any], lang: str) -> Any:
        """A CodeList with its items."""

    @abstractmethod
    def study_event(self, event: dict[str, Any], lang: str) -> Any:
        """A StudyEventDef referencing the forms collected at that visit."""

    @abstractmethod
    def protocol(self, events: list[dict[str, Any]], standards: list[dict[str, Any]],
                 crf_objects: dict[str, Any]) -> Any:
        """The Protocol, wiring in every study event and the standard aliases."""

    @abstractmethod
    def standards(self, standards: list[dict[str, Any]],
                  crf_objects: dict[str, Any]) -> Any | None:
        """Native Standards, or ``None`` when the version has no such element."""

    def measurement_unit(self, name: str, lang: str) -> Any | None:
        """A MeasurementUnit. Only ODM 1.3.2 has them."""
        return None

    # -- serialization --------------------------------------------------------
    def bind_namespaces(self, odm: Any) -> None:
        """Bind this version's namespace to the document before serializing.

        odmlib's namespace registry is process-global and the last imported model package
        wins, so a generator that can emit both versions must re-register the URI it
        means every time. Without this an ODM 2.0 document silently serializes in the
        1.3.2 namespace and fails schema validation.
        """
        import odmlib.ns_registry as NS

        NS.NamespaceRegistry(prefix="odm", uri=self.ns_uri, is_default=True, is_reset=True)
        NS.bind_document_namespaces(odm, recursive=True)

    def to_xml_string(self, odm: Any, xml_declaration: bool = True) -> str:
        """Serialize, repairing the xlink declaration odmlib omits.

        odmlib 0.2.1 writes ``Leaf/@xlink:href`` without declaring ``xmlns:xlink`` on the
        root, so the result is not well-formed. Documented in FIXES.md and reported
        upstream; drop this once odmlib declares it.
        """
        self.bind_namespaces(odm)
        xml = odm.to_xml_string(xml_declaration=xml_declaration)
        if "xlink:" in xml and "xmlns:xlink" not in xml:
            xml = _ODM_OPEN.sub(f'<ODM xmlns:xlink="{XLINK_URI}"', xml, count=1)
        return xml
