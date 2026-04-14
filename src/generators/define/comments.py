from odmlib.define_2_1 import model as DEFINE
import define_object


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
        self.lang = lang
        for comment in template:
            name = self.require_key(comment, "name", "CommentDef")
            com_oid = comment.get("OID") or self.generate_oid(["COM", name])
            if self.find_object(define_objects["CommentDef"], com_oid) is not None:
                continue
            com_def = self._create_commentdef_object(com_oid, comment)
            define_objects["CommentDef"].append(com_def)

    def _create_commentdef_object(self, com_oid, comment):
        """
        use the values from the Comments section of the DDS JSON to create a CommentDef odmlib template
        :param com_oid: unique identifier for the comment
        :param comment: comment dictionary from the DDS JSON
        :return: a CommentDef odmlib template
        """
        com = DEFINE.CommentDef(OID=com_oid)
        description = self.require_key(comment, "description", f"CommentDef {com_oid}")
        tt = DEFINE.TranslatedText(_content=description, lang=self.lang)
        com.Description = DEFINE.Description()
        com.Description.TranslatedText.append(tt)
        if comment.get("document"):
            self._add_document(comment, com)
        return com

    @staticmethod
    def _add_document(comment, com):
        """
        creates a DocumentRef template using a comment dictionary from the DDS JSON
        :param comment: comment dictionary from the DDS JSON
        :param com: define comment template
        """
        dr = DEFINE.DocumentRef(leafID=comment["document"])
        if comment.get("pages"):
            pdf = DEFINE.PDFPageRef(PageRefs=comment["pages"], Type="NamedDestination")
            dr.PDFPageRef.append(pdf)
        com.DocumentRef.append(dr)
