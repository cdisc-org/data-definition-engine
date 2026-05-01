from odmlib.define_2_1 import model as DEFINE
import define_object


class AnnotatedCRF(define_object.DefineObject):
    """ create Define-XML v2.1 AnnotatedCRF and leaf element objects """
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
        self.lang = lang
        for doc in template:
            a_crf = self._create_acrf_object(doc)
            define_objects["AnnotatedCRF"].append(a_crf)
            leaf = self._create_leaf_object(doc)
            if self.find_object(define_objects["leaf"], leaf.ID) is None:
                define_objects["leaf"].append(leaf)

    @staticmethod
    def _create_acrf_object(doc):
        """
        use the values from the Documents section of the template to create a leaf odmlib template
        :param doc: define-template metadata dictionary
        :return: a leaf odmlib template
        """
        acrf = DEFINE.AnnotatedCRF()
        doc_ref = DEFINE.DocumentRef(leafID=doc.get("leafID", "LF.acrf"))
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
        leaf_id = doc.get("leafID", "LF.acrf")
        lf = DEFINE.leaf(ID=leaf_id, href=href)
        lf.title = DEFINE.title(_content=doc.get("title", "Annotated CRF"))
        return lf
