from odmlib.define_2_1 import model as DEFINE
import define_object


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
        self.lang = lang
        for doc in template:
            leaf_id = doc.get("ID") or doc.get("id") or doc.get("leafID")
            if leaf_id is None:
                raise ValueError("Required field 'ID' missing in Documents")
            if self.find_object(define_objects["leaf"], leaf_id) is not None:
                continue
            leaf = self._create_leaf_object(leaf_id, doc)
            define_objects["leaf"].append(leaf)

    @staticmethod
    def _create_leaf_object(leaf_id, doc):
        """
        use the values from the Documents section of the template to create a leaf odmlib template
        """
        lf = DEFINE.leaf(ID=leaf_id, href=doc["href"])
        lf.title = DEFINE.title(_content=doc["title"])
        return lf
