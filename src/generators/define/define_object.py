from abc import ABC
import logging
from typing import Any
from odmlib.define_2_1 import model as DEFINE

from constants import DEFAULT_LANGUAGE


class DefineObject(ABC):
    """Abstract base class for all Define-XML loader classes."""

    def __init__(self) -> None:
        self.lang: str = DEFAULT_LANGUAGE
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)

    def require_key(self, obj: dict[str, Any], key: str, context: str = "") -> Any:
        """
        Get a required key from a dictionary, raising a helpful error if missing.

        :param obj: dictionary to get key from
        :param key: key name to retrieve
        :param context: optional context string for error message (e.g., "ItemDef USUBJID")
        :return: value of the key
        :raises ValueError: if key is missing from obj
        """
        if key not in obj:
            context_str = f" in {context}" if context else ""
            raise ValueError(f"Required field '{key}' missing{context_str}")
        return obj[key]

    def generate_oid(self, descriptors: list[str]) -> str:
        """
        Generate an OID from a list of descriptors.

        :param descriptors: list of strings to join (e.g., ["IT", "DM", "USUBJID"])
        :return: OID string (e.g., "IT.DM.USUBJID")
        """
        # ensure the element type prefix is not already pre-pended to the OID
        if len(descriptors) > 1 and descriptors[1].startswith(descriptors[0] + "."):
            oid = ".".join(descriptors[1:]).upper().replace(" ", "-")
        else:
            oid = ".".join(descriptors).upper().replace(" ", "-")
        return oid

    def find_object(self, objects: list[Any], oid: str) -> Any | None:
        """
        Find an object in a list by its OID attribute.

        :param objects: list of odmlib objects with OID attribute
        :param oid: OID to search for
        :return: object with matching OID or None if not found
        """
        for o in objects:
            if oid == o.OID:
                return o
        return None

    def document_ref(self, doc: dict[str, Any], default_leaf_id: str | None = None) -> Any | None:
        """
        A def:DocumentRef for one DDS DocumentReference, shared by origins and methods.

        Integer pages become one contiguous FirstPage/LastPage range, or a space-separated
        PageRefs list, both Type="PhysicalRef". A reference with no pages points at the whole
        document. Returns None when neither the reference nor the caller names a leaf.

        :param doc: DDS DocumentReference dictionary (leafID, pages)
        :param default_leaf_id: leaf to use when the reference has no leafID (the aCRF for origins)
        :return: odmlib DocumentRef object, or None
        """
        leaf_id = doc.get("leafID") or default_leaf_id
        if not leaf_id:
            return None
        dr = DEFINE.DocumentRef(leafID=leaf_id)
        pages = sorted({int(p) for p in doc.get("pages") or []})
        if len(pages) > 1 and pages == list(range(pages[0], pages[-1] + 1)):
            dr.PDFPageRef.append(DEFINE.PDFPageRef(FirstPage=pages[0], LastPage=pages[-1], Type="PhysicalRef"))
        elif pages:
            dr.PDFPageRef.append(DEFINE.PDFPageRef(PageRefs=" ".join(str(p) for p in pages), Type="PhysicalRef"))
        return dr

    def translated_text(self, value: Any) -> list[Any]:
        """
        TranslatedText elements for a DDS text slot that is either a plain string or a
        DDS TranslatedText ({"translations": [{"language": ..., "value": ...}]}).

        :param value: string, DDS TranslatedText dictionary, or None
        :return: list of odmlib TranslatedText objects (one per translation; one for a string)
        """
        if isinstance(value, dict):
            return [
                DEFINE.TranslatedText(_content=t.get("value", ""), lang=t.get("language") or self.lang)
                for t in value.get("translations") or []
                if isinstance(t, dict)
            ]
        return [DEFINE.TranslatedText(_content="" if value is None else str(value), lang=self.lang)]

    def create_external_codelist(
        self, cl_oid: str, name: str, data_type: str, dictionary: str, version: str | None = None
    ) -> Any:
        """
        Create a CodeList with ExternalCodeList for external dictionaries.

        :param cl_oid: OID for the CodeList
        :param name: Name of the CodeList
        :param data_type: DataType for the CodeList (e.g., "text")
        :param dictionary: Dictionary name for ExternalCodeList
        :param version: Optional version for ExternalCodeList
        :return: CodeList odmlib object with ExternalCodeList
        """
        cl = DEFINE.CodeList(OID=cl_oid, Name=name, DataType=data_type)
        attr = {"Dictionary": dictionary}
        if version:
            attr["Version"] = version
        cl.ExternalCodeList = DEFINE.ExternalCodeList(**attr)
        return cl
