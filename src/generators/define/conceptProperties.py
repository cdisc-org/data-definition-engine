import define_object


class ConceptProperties(define_object.DefineObject):
    """
    Read the DDS ``conceptProperties`` section.

    The loaders write Biomedical Concept properties here (ConceptProperty in the DDS
    schema), which have no Define-XML 2.1 element and are skipped. An entry in the legacy
    dictionary shape (``shortName``, ``dictionary``, ``version``) still becomes an external
    CodeList.
    """
    def __init__(self):
        super().__init__()

    def create_define_objects(self, template, objects, lang, acrf):
        """
        parse the define-template and create odmlib define_objects to return in the define_objects dictionary
        """
        self.lang = lang
        for concept in template:
            short_name = concept.get("shortName") or concept.get("Short Name")
            if not short_name:
                if concept.get("dictionary") is None:
                    continue  # a ConceptProperty: nothing to emit in Define-XML
                raise ValueError("Required field 'shortName' missing in ConceptProperties")
            cl_oid = self.generate_oid(["CL", short_name])
            if self.find_object(objects["CodeList"], cl_oid) is not None:
                continue
            cl = self.create_external_codelist(
                cl_oid=cl_oid,
                name=concept.get("name") or concept.get("Name"),
                data_type=concept.get("dataType") or concept.get("Data Type"),
                dictionary=concept.get("dictionary") or concept.get("Dictionary"),
                version=concept.get("version") or concept.get("Version"),
            )
            objects["CodeList"].append(cl)
