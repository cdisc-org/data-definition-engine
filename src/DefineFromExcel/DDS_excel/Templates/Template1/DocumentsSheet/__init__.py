from DDS_excel.base_sheet import BaseSheet
from DDS_excel.globals import Globals

class DocumentsSheet(BaseSheet):

    def __init__(self, file_path: str, globals: Globals):

        self._documents=[]

        try:
            super().__init__(
                file_path=file_path,
                globals=globals,
                sheet_name="Documents"
            )        
      
            self._process_sheet()

        except Exception as e:
            self._sheet_exception(e)

    def _process_sheet(self):
        for row in self.sheet.itertuples():
            self._documents.append({'OID':row.ID,'leafID':row.ID,'title':row.Title,'href':row.Href})

