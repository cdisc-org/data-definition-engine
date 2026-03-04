from odmlib.define_2_1 import model as DEFINE
import define_object


""" Note: Documents have not yet been implemented in the template """
class Documents(define_object.DefineObject):
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
        self.logger.info("in Documents...")
        self.lang = lang
        define_objects["leaf"] = []
        for doc in template:
            leaf = self._create_leaf_object(doc)
            define_objects["leaf"].append(leaf)

    def _create_leaf_object(self, doc):
        """
        use the values from the Documents section of the template to create a leaf odmlib template
        :param doc: define-template metadata dictionary
        :return: a leaf odmlib template
        """
        lf = DEFINE.leaf(ID=doc["ID"], href=doc["href"])
        title = DEFINE.title(_content=doc["title"])
        lf.title = title
        return lf
