from typing import Any
from odmlib.define_2_1 import model as DEFINE
import define_object


class Items(define_object.DefineObject):
    """Create Define-XML v2.1 ItemDef element objects."""

    def __init__(self) -> None:
        super().__init__()
        self.lookup_oid: str | None = None
        self.igd: Any | None = None
        self.item_def_oids: list[str] = []
        self.vlm_oids: list[str] = []

    def create_define_objects(
        self,
        template: list[dict[str, Any]],
        define_objects: dict[str, list[Any]],
        lang: str,
        acrf: str,
        slice: list[dict[str, Any]] | None = None
    ) -> None:
        """
        Create ItemDef objects from the DDS template.

        :param template: list of variable definitions from the DDS JSON
        :param define_objects: dictionary of odmlib objects updated by this method
        :param lang: xml:lang setting for TranslatedText
        :param acrf: annotated case report form leaf ID
        :param slice: list of slice definitions from the DDS JSON (if applicable)
        """
        self.lang = lang
        self.acrf = acrf
        self.slice = slice
        for variable in template:
            it_oid = self.require_key(variable, "OID", "ItemDef")
            # Dedup: slices (VLM) can reference ItemDefs that share an OID with
            # the parent column ItemDef. Emitting both triggers a schema-level
            # OID uniqueness violation, so we skip anything already registered.
            if self.find_object(define_objects["ItemDef"], it_oid) is not None:
                continue
            item = self._create_itemdef_object(variable, it_oid, slice)
            define_objects["ItemDef"].append(item)

    def _create_itemdef_object(self, obj, oid, slice):
        name = self.require_key(obj, "name", f"ItemDef {oid}")
        data_type = self.require_key(obj, "dataType", f"ItemDef {oid}")
        attr = {"OID": oid, "Name": name, "DataType": data_type, "SASFieldName": name}
        self._add_optional_itemdef_attributes(attr, obj)
        # TODO hack — bypasses odmlib descriptor validation so "__PLACEHOLDER__" values
        # can be stashed on an ItemDef until odmlib v0.2.0 ships. We must manually
        # materialize the list-typed children that downstream code later appends to
        # because skipping __init__ skips their initialization.
        item = self._new_itemdef(attr)

        if obj.get("description"):
            tt = DEFINE.TranslatedText(_content=obj["description"], lang=self.lang)
            item.Description = DEFINE.Description()
            item.Description.TranslatedText.append(tt)
        self._add_optional_itemdef_elements(item, obj, oid, slice)
        # Materialize list-valued children that odmlib normally initializes in __init__.
        # Downstream code appends to these without checking truthiness.
        for list_attr in ("Origin",):
            if list_attr not in item.__dict__:
                item.__dict__[list_attr] = []
        return item

    @staticmethod
    def _new_itemdef(attr: dict[str, Any]) -> Any:
        """Instantiate an ItemDef without triggering descriptor validation."""
        item = object.__new__(DEFINE.ItemDef)
        for key, value in attr.items():
            item.__dict__[key] = value
        return item

    def _add_optional_itemdef_elements(self, item, obj, it_oid, slice):
        """
        use the values from the Variables section in the define-template to add the optional ELEMENTS to the ItemDef
        """
        if obj.get("codeList"):
            cl_oid = self.generate_oid(["CL", obj["codeList"].split(".")[1]])
            item.CodeListRef = DEFINE.CodeListRef(CodeListOID=cl_oid)
        for s in slice or []:
            if s.get("type") == "ValueList" and s.get("wasDerivedFrom") == it_oid:
                item.ValueListRef = DEFINE.ValueListRef(ValueListOID=s["OID"])
        if obj.get("origin"):
            self._add_origin(item, obj)

    def _add_origin(self, item, obj):
        origin_in = obj["origin"]
        origin_type = origin_in.get("type")
        origin_source = origin_in.get("source")
        attr: dict[str, Any] = {}
        if origin_type:
            attr["Type"] = origin_type
        if origin_source:
            attr["Source"] = origin_source
        # Bypass odmlib descriptor validation to allow __PLACEHOLDER__ values later.
        # TODO remove this hack when odmlib v0.2.0 is released.
        origin = object.__new__(DEFINE.Origin)
        for key, value in attr.items():
            origin.__dict__[key] = value
        origin.__dict__.setdefault("DocumentRef", [])

        if origin_type == "Collected" and origin_source == "Investigator":
            dr = DEFINE.DocumentRef(leafID=self.acrf)
            dr.PDFPageRef.append(DEFINE.PDFPageRef(PageRefs="__PLACEHOLDER__", Type="PhysicalRef"))
            origin.DocumentRef.append(dr)

        if obj.get("predecessor"):
            origin.Description = DEFINE.Description()
            origin.Description.TranslatedText.append(
                DEFINE.TranslatedText(_content=obj["predecessor"], lang=self.lang)
            )
        if obj.get("pages"):
            dr = DEFINE.DocumentRef(leafID=self.acrf)
            dr.PDFPageRef.append(DEFINE.PDFPageRef(PageRefs=obj["pages"], Type="PhysicalRef"))
            origin.DocumentRef.append(dr)

        item.Origin.append(origin)

    @staticmethod
    def _add_optional_itemdef_attributes(attr, obj):
        """
        use the values from the Variables section in the define-template to add the optional attributes to the ItemDef
        """
        if obj.get("length"):
            attr["Length"] = obj["length"]
        elif obj.get("dataType") in ["text", "integer", "float"]:
            attr["Length"] = "__PLACEHOLDER__"
        if obj.get("significantDigits"):
            attr["SignificantDigits"] = obj["significantDigits"]
        if obj.get("displayFormat"):
            attr["DisplayFormat"] = obj["displayFormat"]
        if obj.get("comment"):
            attr["CommentOID"] = obj["comment"]
