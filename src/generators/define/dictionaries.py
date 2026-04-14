import define_object


class Dictionaries(define_object.DefineObject):
    """ create Define-XML v2.1 CodeList elements with ExternalCodeList references """
    def __init__(self):
        super().__init__()

    def create_define_objects(self, template, objects, lang, acrf):
        """
        parse the define-template and create odmlib define_objects to return in the define_objects dictionary
        :param template: define-template dictionary section
        :param objects: dictionary of odmlib define_objects updated by this method
        :param lang: xml:lang setting for TranslatedText
        :param acrf: part of the common interface but not used by this class
        """
        self.lang = lang
        for codelist in template:
            short_name = codelist.get("shortName") or codelist.get("Short Name")
            if not short_name:
                raise ValueError("Required field 'shortName' missing in Dictionaries")
            cl_oid = self.generate_oid(["CL", short_name])
            if self.find_object(objects["CodeList"], cl_oid) is not None:
                continue
            cl = self.create_external_codelist(
                cl_oid=cl_oid,
                name=codelist.get("name") or codelist.get("Name"),
                data_type=codelist.get("dataType") or codelist.get("Data Type"),
                dictionary=codelist.get("dictionary") or codelist.get("Dictionary"),
                version=codelist.get("version") or codelist.get("Version"),
            )
            objects["CodeList"].append(cl)
