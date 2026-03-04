from odmlib.define_2_1 import model as DEFINE
import define_object


""" Note: Methods have not yet been implemented in the template """
class Methods(define_object.DefineObject):
    """ create a Define-XML v2.1 MethodDef element """
    def __init__(self):
        super().__init__()

    def create_define_objects(self, template, define_objects, lang, acrf):
        """
        parse the define-template dictionary and create a odmlib define_objects to return in the define_objects dictionary
        :param template: define-template dictionary metadata
        :param define_objects: dictionary of odmlib define_objects updated by this method
        :param lang: xml:lang setting for TranslatedText
        :param acrf: part of the common interface but not used by this class
        """
        self.logger.info("in methods...")
        self.lang = lang
        define_objects["MethodDef"] = []
        for method in template:
            item = self._create_methoddef_object(method)
            define_objects["MethodDef"].append(item)

    def _create_methoddef_object(self, method):
        """
        use the values from the Methods section of the define-template to create a MethodDef odmlib ojbect
        :param method: Methods define-template dictionary section
        :return: a MethodDef odmlib template
        """
        attr = {"OID": method["OID"], "Name": method["name"], "Type": method["type"]}
        methoddef = DEFINE.MethodDef(**attr)
        tt = DEFINE.TranslatedText(_content=method["description"], lang=self.lang)
        methoddef.Description = DEFINE.Description()
        methoddef.Description.TranslatedText.append(tt)
        if method.get("context"):
            methoddef.FormalExpression.append(DEFINE.FormalExpression(Context=method["context"], _content=method["code"]))
        if method.get("document"):
            self._add_document(method, methoddef)
        return method

    def _add_document(self, method, methoddef):
        """
        creates a DocumentRef template using metadata from the define-template dictionary
        :param method: Methods section in the define-template dictionary
        :param methoddef: odmlib MethodDef template that gets updated with a DocumentRef template
        """
        dr = DEFINE.DocumentRef(leafID=method["document"])
        pdf = DEFINE.PDFPageRef(PageRefs=method["pages"], Type="namedDestination")
        dr.PDFPageRef.append(pdf)
        methoddef.DocumentRef.append(dr)
