from odmlib.define_2_1 import model as DEFINE
import define_object


""" Note: Comments have not yet been implemented in the template """
class Comments(define_object.DefineObject):
    """ create a Define-XML v2.1 CommentDef element template """
    def __init__(self):
        super().__init__()
        self.lookup_oid = None
        self.igd = None

    def create_define_objects(self, template, define_objects, lang, acrf):
        """
        parse the define-template dictionary and create odmlib define_objects to return in the define_objects dictionary
        :param template: DDS template dictionary
        :param define_objects: dictionary of odmlib define_objects updated by this method
        :param lang: xml:lang setting for TranslatedText
        """
        self.logger.info("in Comments...")
        self.lang = lang
        define_objects["CommentDef"] = []
        for comment in template:
            com_oid = self.generate_oid(["COM", comment.Name])
            comment = self._create_commentdef_object(com_oid, comment)
            define_objects["CommentDef"].append(comment)

    def _create_commentdef_object(self, com_oid, comment):
        """
        use the values from the Comments section of the DDS JSON to create a CommentDef odmlib template
        :param com_oid: unique identifier for the comment
        :param comment: comment dictionary from the DDS JSON
        :return: a CommentDef odmlib template
        """
        com = DEFINE.CommentDef(OID=com_oid, CommentType="FreeText")
        tt = DEFINE.TranslatedText(_content=comment["Description"], lang=self.lang)
        com.Description = DEFINE.Description()
        com.Description.TranslatedText.append(tt)
        if comment.get("Document"):
            self._add_document(comment, com)
        return com

    @staticmethod
    def _add_document(comment, com):
        """
        creates a DocumentRef template using a comment dictionary from the DDS JSON
        :param comment: comment dictionary from the DDS JSON
        :param com: define comment template
        """
        dr = DEFINE.DocumentRef(leafID=comment["Document"])
        if comment.get("Pages"):
            pdf = DEFINE.PDFPageRef(PageRefs=comment["Pages"], Type="NamedDestination")
            dr.PDFPageRef.append(pdf)
        com.DocumentRef.append(dr)
