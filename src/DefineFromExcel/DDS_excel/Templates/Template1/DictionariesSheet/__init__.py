from DDS_excel.base_sheet import BaseSheet
from DDS_excel.globals import Globals
import pandas as pd

class DictionariesSheet(BaseSheet):

    def __init__(self, file_path: str, globals: Globals):

        self._dictionaries = []

        try:
            super().__init__(
                file_path=file_path,
                globals=globals,
                sheet_name="Dictionaries"
            )        
      
            self._process_sheet()

        except Exception as e:
            self._sheet_exception(e)

    def _process_sheet(self):
        for row in self.sheet.itertuples():
            self._dictionaries.append({'OID':'DICT.'+row.OID,'name':row.Name,'version':row.Version})

