from odmlib.define_2_1 import model as DEFINE
import define_object
from typing import Any


class Dictionaries(define_object.DefineObject):
    """ create Define-XML v2.1 CodeList elements with ExternalCodeList references """
    def __init__(self):
        super().__init__()

    def create_define_objects(
            self,
            template,
            define_objects,
            lang,
            acrf):
        """
        parse the define-template and create odmlib define_objects to return in the define_objects dictionary
        :param template: define-template dictionary section
        :param define_objects: dictionary of odmlib define_objects updated by this method
        :param lang: xml:lang setting for TranslatedText
        :param acrf: part of the common interface but not used by this class
        """
        self.lang = lang
        for dictionary in template:
            cl_oid = self.require_key(dictionary, "OID", "Dictionary")
            if self.find_object(define_objects["CodeList"], cl_oid) is not None:
                continue
            ex_cl = self._create_external_codelist(
                dictionary=self.require_key(dictionary, "name", f"Dictionary {cl_oid}"),
                version=dictionary.get("version"),
                href=dictionary.get("href"),
            )
            cl = self._create_codelist_object(dictionary, cl_oid, ex_cl)
            define_objects["CodeList"].append(cl)

    def _create_external_codelist(
            self, dictionary: str, version: str, href: str | None = None
    ) -> Any:
        """
        Create an ExternalCodeList reference for an external dictionary.

        :param dictionary: Dictionary name for ExternalCodeList
        :param version: version for ExternalCodeList
        :param href: optional href for the ExternalCodeList
        :return: ExternalCodeList odmlib object
        """
        attr = {"Dictionary": dictionary}
        if version:
            attr["Version"] = version
        if href:
            attr["href"] = href
        ex_cl = DEFINE.ExternalCodeList(**attr)
        return ex_cl

    def _create_codelist_object(self, obj, oid: str, ex_cl: DEFINE.ExternalCodeList):
        name = self.require_key(obj, "name", f"CodeList {oid}")
        data_type = obj.get("dataType", "text")
        attr = {"OID": oid, "Name": name, "DataType": data_type}
        if obj.get("comment"):
            attr["CommentOID"] = obj["comment"]
        if obj.get("isNonStandard"):
            attr["IsNonStandard"] = "Yes"
        if obj.get("standard"):
            attr["StandardOID"] = obj["standard"]
        cl = DEFINE.CodeList(**attr)
        cl.ExternalCodeList = ex_cl
        return cl

