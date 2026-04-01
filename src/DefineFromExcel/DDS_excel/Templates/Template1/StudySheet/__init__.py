from DDS_excel.base_sheet import BaseSheet
from DDS_excel.globals import Globals

class StudySheet(BaseSheet):

    def __init__(self, file_path: str, globals: Globals, template: dict):

        self._study_template=template

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
        studyatts = {'StudyName':'studyName','StudyDescription':'studyDescription','ProtocolName':'protocolName','AnnotatedCRF':'annotatedCRF'}
        for row in self.sheet.itertuples():
            if row.Attribute in studyatts:
                self._study_template[studyatts[str(row.Attribute)]] = row.Value
            else:
                self._general_info(f"Unsupported Study attribute {row.Attribute}")

