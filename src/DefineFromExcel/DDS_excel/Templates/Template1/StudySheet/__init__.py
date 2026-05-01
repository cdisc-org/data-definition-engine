from DDS_excel.base_sheet import BaseSheet
from DDS_excel.globals import Globals
from datetime import datetime


class StudySheet(BaseSheet):

    def __init__(self, file_path: str, globals: Globals):

        self._study_template={}

        try:
            super().__init__(
                file_path=file_path,
                globals=globals,
                sheet_name="Study"
            )        
      
            self._process_sheet()

        except Exception as e:
            self._sheet_exception(e)

    def _process_sheet(self):
        # map of attribute names in Study sheet to corresponding names in DDS
        studyatts = {'StudyName':'studyName','StudyDescription':'studyDescription','ProtocolName':'protocolName'}

        for row in self.sheet.itertuples():
            if row.Attribute in studyatts:
                self._study_template[studyatts[str(row.Attribute)]] = row.Value
            else:
                self._general_info(f"Unsupported Study attribute {row.Attribute}")

        self._study_template['fileOID'] = f'ODM.DEFINE-360I.{self._study_template["studyName"]}'
        self._study_template['creationDateTime'] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f") + "+00:00"
        self._study_template['OID'] = f'MDV.{self._study_template["studyName"]}'
        self._study_template['name'] = f'MDV {self._study_template["studyName"]}'
        self._study_template['description'] = f'Data Definitions for {self._study_template["studyName"]}'

