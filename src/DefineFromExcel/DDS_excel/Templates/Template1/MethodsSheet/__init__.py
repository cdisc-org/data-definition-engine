from DDS_excel.base_sheet import BaseSheet
from DDS_excel.globals import Globals

class StandardsSheet(BaseSheet):

    def __init__(self, file_path: str, globals: Globals, template: dict):

        self._study_template=template

        try:
            super().__init__(
                file_path=file_path,
                globals=globals,
                sheet_name="Standards"
            )        
      
            self._process_sheet()

        except Exception as e:
            self._sheet_exception(e)

    def _process_sheet(self):
        pass

