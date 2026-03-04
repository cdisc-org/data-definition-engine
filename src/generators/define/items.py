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
        acrf: str
    ) -> None:
        """
        Create ItemDef objects from the DDS template.

        :param template: list of variable definitions from the DDS JSON
        :param define_objects: dictionary of odmlib objects updated by this method
        :param lang: xml:lang setting for TranslatedText
        :param acrf: annotated case report form leaf ID
        """
        self.lang = lang
        self.acrf = acrf
        for variable in template:
            it_oid = self.require_key(variable, "OID", "ItemDef")
            item = self._create_itemdef_object(variable, it_oid)
            define_objects["ItemDef"].append(item)

    def _create_itemdef_object(self, obj, oid):
        name = self.require_key(obj, "name", f"ItemDef {oid}")
        data_type = self.require_key(obj, "dataType", f"ItemDef {oid}")
        attr = {"OID": oid, "Name": name, "DataType": data_type, "SASFieldName": name}
        self._add_optional_itemdef_attributes(attr, obj)
        item = DEFINE.ItemDef(**attr)
        if obj.get("description"):
            tt = DEFINE.TranslatedText(_content=obj["description"], lang=self.lang)
            item.Description = DEFINE.Description()
            item.Description.TranslatedText.append(tt)
        self._add_optional_itemdef_elements(item, obj, oid)
        return item

    def _add_optional_itemdef_elements(self, item, obj, it_oid):
        """
        use the values from the Variables section in the define-template to add the optional ELEMENTS to the ItemDef
        """
        # TODO do not find codeList in define.json example for items
        if obj.get("codeList"):
            cl_oid = self.generate_oid(["CL", obj["codeList"].split(".")[1]])
            cl = DEFINE.CodeListRef(CodeListOID=cl_oid)
            item.CodeListRef = cl
        # TODO do not find origin content in define.json example for items (nice to have that information)
        attr = {}
        if obj.get("origin"):
            # define-template input only provides for 1 Origin, but multiple are supported by the spec
            if obj.get("origin").get("type"):
                attr["Type"] =  obj["origin"]["type"]
            if obj.get("origin").get("source"):
                attr["Source"] = obj["origin"]["source"]
            item.Origin.append(DEFINE.Origin(**attr))
            if obj.get("predecessor"):
                item.Origin[0].Description = DEFINE.Description()
                item.Origin[0].Description.TranslatedText.append(DEFINE.TranslatedText(_content=obj["Predecessor"]))
            if obj.get("pages"):
                dr = DEFINE.DocumentRef(leafID=self.acrf)
                dr.PDFPageRef.append(DEFINE.PDFPageRef(PageRefs=obj["Pages"], Type="PhysicalRef"))
                item.Origin[0].DocumentRef.append(dr)

    @staticmethod
    def _add_optional_itemdef_attributes(attr, obj):
        """
        use the values from the Variables section in the define-template to add the optional attributes to the ItemDef
        """
        if obj.get("length"):
            attr["Length"] = obj["length"]
        if obj.get("significantDigits"):
            attr["SignificantDigits"] = obj["significantDigits"]
        # TODO do not find format content in define.json example for items
        if obj.get("format"):
            attr["DisplayFormat"] = obj["format"]
        if obj.get("comment"):
            attr["CommentOID"] = obj["comment"]

