from odmlib.define_2_1 import model as DEFINE
import define_object


class AnnotatedCRF(define_object.DefineObject):
    """ create a Define-XML v2.1 leaf element template """
    def __init__(self):
        super().__init__()

    def create_define_objects(self, template, define_objects, lang, acrf):
        """
        parse the DDS template and create odmlib define_objects to return in the define_objects dictionary
        :param template: define-template dictionary section
        :param define_objects: dictionary of odmlib define_objects updated by this method
        :param lang: xml:lang setting for TranslatedText
        :param acrf: part of the common interface but not used by this class
        """
        self.logger.info("in annotatedCRF...")
        self.lang = lang
        define_objects["AnnotatedCRF"] = []
        define_objects["leaf"] = []
        for doc in template:
            a_crf = self._create_acrf_object(doc)
            define_objects["AnnotatedCRF"].append(a_crf)
            leaf = self._create_leaf_object(doc)
            define_objects["leaf"].append(leaf)

    @staticmethod
    def _create_acrf_object(doc):
        """
        use the values from the Documents section of the template to create a leaf odmlib template
        :param doc: define-template metadata dictionary
        :return: a leaf odmlib template
        """
        acrf = DEFINE.AnnotatedCRF()
        doc_ref = DEFINE.DocumentRef(leafID=doc["leafID"])
        acrf.DocumentRef = doc_ref
        return acrf

    @staticmethod
    def _create_leaf_object(doc):
        """
        use the values from the Documents section of the template to create a leaf odmlib template
        :param doc: define-template metadata dictionary
        :return: a leaf odmlib template
        """
        href = doc.get("href", "acrf.pdf")
        id = "LF.acrf"
        # TODO how generate the ID correctly?
        lf = DEFINE.leaf(ID=id, href=href)
        title = DEFINE.title(_content=doc["title"])
        lf.title = title
        return lf