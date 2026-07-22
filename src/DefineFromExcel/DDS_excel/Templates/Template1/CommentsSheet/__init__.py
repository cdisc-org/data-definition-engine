from DDS_excel.base_sheet import BaseSheet
from DDS_excel.globals import Globals
import pandas as pd

class CommentsSheet(BaseSheet):

    def __init__(self, file_path: str, globals: Globals):

        self._comments=[]

        try:
            super().__init__(
                file_path=file_path,
                globals=globals,
                sheet_name="Comments"
            )        
            self.sheet['Pages'] = self.sheet['Pages'].astype(str)
      
            self._process_sheet()

        except Exception as e:
            self._sheet_exception(e)

    def _process_sheet(self):
        for row in self.sheet.itertuples():
            commdict = {'OID':row.OID,'text':row.Description}
            if pd.notna(row.Document):
                docdict = {'leafID':row.Document}
                if pd.notna(row.Pages):
                    docdict['pages'] = row.Pages.split(',')
                commdict['documents'] = docdict

            self._comments.append(commdict)

