from odmlib.define_2_1 import model as DEFINE
import define_object


class Study(define_object.DefineObject):
    """ create a Define-XML v2.1 Study element template and initialize the MetaDataVersion template """
    def __init__(self):
        super().__init__()

    def create_define_objects(self, template, define_objects, lang, acrf):
        self.lang = lang
        self.acrf = acrf
        if "language" in template:
            self.lang = template["language"]
        if "annotatedCRF" in template and len(template["annotatedCRF"]) > 0:
            self.acrf = template["annotatedCRF"][0].get("leafID", None)
        define_objects["Study"] = self._create_study_object(template)
        define_objects["MetaDataVersion"] = self._create_metadataversion_object(template)

    @staticmethod
    def _create_study_object(study_dict):
        """
        create the study ODMLIB template from the Study template and return it
        :param study_dict: dictionary created from the define-template study section
        :return: odmlib Study template
        """
        study_oid = study_dict["studyOID"]
        study = DEFINE.Study(OID=study_oid)
        gv = DEFINE.GlobalVariables()
        gv.StudyName = DEFINE.StudyName(_content=study_dict["studyName"])
        gv.StudyDescription = DEFINE.StudyDescription(_content=study_dict.get("studyDescription", "NA"))
        gv.ProtocolName = DEFINE.ProtocolName(_content=study_dict.get("protocolName", "NA"))
        study.GlobalVariables = gv
        return study

    def _create_metadataversion_object(self, study_dict):
        """
        create the MetaDataVersion ODMLIB template from the DDS JSON and return it
        :param study_dict: dictionary created from the study section in the DDS JSON
        :return: odmlib MetaDataVersion template
        """
        # Prefer an explicit MDV OID from the DDS. Without one we synthesize from
        # the study name, which collides whenever two studies share a name or one
        # study carries multiple MDVs — warn loudly so callers notice.
        mdv_oid = study_dict.get("metaDataVersionOID")
        if not mdv_oid:
            mdv_oid = self.generate_oid(["MDV", study_dict["studyName"]])
            self.logger.warning(
                "metaDataVersionOID missing from DDS; synthesized %s from studyName. "
                "This collides across studies sharing a name or studies with multiple MDVs.",
                mdv_oid,
            )
        name = study_dict.get("metaDataVersionName", "MDV " + study_dict["studyName"])
        description = study_dict.get(
            "metaDataVersionDescription", f"Data Definitions for {study_dict['studyName']}"
        )
        mdv = DEFINE.MetaDataVersion(
            OID=mdv_oid, Name=name, Description=description, DefineVersion="2.1.0"
        )
        return mdv
