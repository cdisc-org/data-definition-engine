from odmlib.define_2_1 import model as DEFINE
import define_object
from constants import DEFINE_STANDARD_NAMES

class Standards(define_object.DefineObject):
    """ create a Define-XML v2.1 Standards element template """
    def __init__(self):
        super().__init__()

    def create_define_objects(self, template, define_objects, lang, acrf):
        """
        parse each value in the define-template and create odmlib define_objects to return in the define_objects dictionary
        :param template: DDS template template section
        :param define_objects: dictionary of odmlib define_objects updated by this method
        :param lang: xml:lang setting for TranslatedText
        :param acrf: part of the common interface but not used by this class
        """
        standards = DEFINE.Standards()
        self.lang = lang
        for standard in template:
            if standard.get("name") not in DEFINE_STANDARD_NAMES:
                # a CRF-only standard (CDASHIG) in a combined DDS: Define-XML 2.1 has no name for it
                self.logger.info("skipping standard %s: %r is not a Define-XML 2.1 standard name",
                                 standard.get("OID"), standard.get("name"))
                continue
            std = self._create_standard_object(standard)
            standards.Standard.append(std)
        define_objects["Standards"] = standards

    @staticmethod
    def _create_standard_object(standard):
        """
        use the values from the Standards define-template dictionary to create a Standard odmlib template
        :param standard: Standards define-template dictionary section
        :return: odmlib Standard template
        """
        attr = {"OID": standard["OID"], "Name": standard["name"], "Type": standard["type"],
                "Version": str(standard["version"]), "Status": standard["status"]}
        if standard.get("publishingSet"):
            attr["PublishingSet"] = standard["publishingSet"]
        if standard.get("comment"):
            attr["CommentOID"] = standard["comment"]
        return DEFINE.Standard(**attr)
