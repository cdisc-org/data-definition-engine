from typing import Any
from odmlib.define_2_1 import model as DEFINE
import define_object


class CodeLists(define_object.DefineObject):
    """Create Define-XML v2.1 CodeList element objects."""

    def __init__(self) -> None:
        super().__init__()
        # self.igd: Any | None = None

    def create_define_objects(
        self,
        template: list[dict[str, Any]],
        define_objects: dict[str, list[Any]],
        lang: str,
        acrf: str
    ) -> None:
        """
        Create CodeList objects from the DDS template.

        :param template: list of codelist definitions from the DDS JSON
        :param define_objects: dictionary of odmlib objects updated by this method
        :param lang: xml:lang setting for TranslatedText
        :param acrf: part of the common interface but not used by this class
        """
        self.lang = lang
        for cl in template:
            cl_oid = self.require_key(cl, "OID", "CodeList")
            # Dedup CodeLists by OID so two datasets that reference the same codelist
            # don't land duplicate definitions in the output.
            if self.find_object(define_objects["CodeList"], cl_oid) is not None:
                continue
            cl_defn = self._create_codelist_object(cl)
            is_non_standard = self._set_is_non_standard(cl_defn)
            coding = cl.get("coding", [])
            cl_c_code = coding[0].get("code") if coding else None
            cl_name = cl.get("name", "__PLACEHOLDER__")
            codelist_items = self.require_key(cl, "codeListItems", f"CodeList {cl_name}")
            # assumes there is never a case where decode and enumerated items are mixed
            for term in codelist_items:
                if "decode" in term:
                    cl_item = self._create_codelistitem_object(term, is_non_standard)
                    cl_defn.CodeListItem.append(cl_item)
                else:
                    en_item = self._create_enumerateditem_object(term, is_non_standard)
                    cl_defn.EnumeratedItem.append(en_item)
            self._add_codelist_to_objects(cl_c_code, cl_defn, define_objects)

    @staticmethod
    def _add_codelist_to_objects(cl_c_code, cl, objects):
        if cl_c_code:
            alias = DEFINE.Alias(Context="nci:ExtCodeID", Name=cl_c_code)
            cl.Alias.append(alias)
        objects["CodeList"].append(cl)

    def _create_codelist_object(self, obj):
        oid = self.require_key(obj, "OID", "CodeList")
        name = self.require_key(obj, "name", f"CodeList {oid}")
        data_type = obj.get("dataType", "text")
        attr = {"OID": oid, "Name": name, "DataType": data_type}
        if obj.get("comment"):
            attr["CommentOID"] = obj["comment"]
        if "isNonStandard" in obj:
            attr["IsNonStandard"] = "Yes"
        if obj.get("standard"):
            attr["StandardOID"] = obj["standard"]
        cl = DEFINE.CodeList(**attr)
        return cl

    def _create_enumerateditem_object(self, obj, is_non_standard):
        coded_value = self.require_key(obj, "codedValue", "CodeListItem")
        attr = {"CodedValue": coded_value}
        en_item = DEFINE.EnumeratedItem(**attr)
        coding = obj.get("coding", {})
        if coding:
            alias = DEFINE.Alias(Context="nci:ExtCodeID", Name=coding.get("code"))
            en_item.Alias.append(alias)
        elif not is_non_standard:
            alias = DEFINE.Alias(Context="nci:ExtCodeID", Name="__PLACEHOLDER__")
            en_item.Alias.append(alias)
        return en_item

    def _create_codelistitem_object(self, obj, is_non_standard):
        coded_value = self.require_key(obj, "codedValue", "CodeListItem")
        attr = {"CodedValue": coded_value}
        cl_item = DEFINE.CodeListItem(**attr)
        decode = DEFINE.Decode()
        if obj.get("decode", None):
            tt = DEFINE.TranslatedText(_content=obj["decode"], lang="en")
        else:
            # assumption: if no decode for this term the use the submission value
            tt = DEFINE.TranslatedText(_content=coded_value, lang="en")
        decode.TranslatedText.append(tt)
        cl_item.Decode = decode
        coding = obj.get("coding", {})
        if coding:
            alias = DEFINE.Alias(Context="nci:ExtCodeID", Name=coding.get("code"))
            cl_item.Alias.append(alias)
        elif not is_non_standard:
            alias = DEFINE.Alias(Context="nci:ExtCodeID", Name="__PLACEHOLDER__")
            cl_item.Alias.append(alias)
        return cl_item

    @staticmethod
    def _set_is_non_standard(cl_defn):
        if cl_defn.IsNonStandard and cl_defn.IsNonStandard == "Yes":
            return True
        else:
            return False
