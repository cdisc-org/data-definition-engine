from DDS_excel.base_sheet import BaseSheet
from DDS_excel.globals import Globals
import pandas as pd

class StandardsSheet(BaseSheet):

    def __init__(self, file_path: str, globals: Globals):

        self._standards_template=[]

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
        # map of attribute names in Standards sheet to corresponding names in DDS
        attribs = {'OID':'OID','Name':'name','Type':'type','Publishing Set':'publishingSet','Version':'version','Status':'status'}

        for i, s in self.sheet.iterrows():
            rowdict = {}
            for x in attribs.keys():
                if pd.notna(getattr(s,x)):
                    rowdict[attribs[x]] = getattr(s,x)

            self._standards_template.append(rowdict)