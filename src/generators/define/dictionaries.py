import define_object


""" Note: Dictionaries have not yet been implemented in the template """
class Dictionaries(define_object.DefineObject):
    """ create a Define-XML v2.1 ExternalCodeList element template """
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
        self.logger.info("in Dictionaries...")
        self.lang = lang
        for codelist in template:
            cl_oid = self.generate_oid(["CL", codelist["Short Name"]])
            cl = self.create_external_codelist(
                cl_oid=cl_oid,
                name=codelist["Name"],
                data_type=codelist["Data Type"],
                dictionary=codelist["Dictionary"],
                version=codelist.get("Version")
            )
            objects["CodeList"].append(cl)
