from odmlib.define_2_1 import model as DEFINE


class SupportingDocuments:

    @staticmethod
    def create_annotatedcrf(annotated_crf):
        acrf = DEFINE.AnnotatedCRF()
        dr = DEFINE.DocumentRef(leafID=annotated_crf)
        acrf.DocumentRef = dr
        return acrf

    @staticmethod
    def create_leaf_object(leaf_id, href, title):
        leaf = DEFINE.leaf(ID=leaf_id, href=href)
        title = DEFINE.title(_content=title)
        leaf.title = title
        return leaf

    @staticmethod
    def create_supplementaldoc(annotated_crf, leaf_objects):
        if not leaf_objects:
            return None
        refs = [lo for lo in leaf_objects if lo.ID != annotated_crf]
        if not refs:
            return None
        sdoc = DEFINE.SupplementalDoc()
        for lo in refs:
            sdoc.DocumentRef.append(DEFINE.DocumentRef(leafID=lo.ID))
        return sdoc
