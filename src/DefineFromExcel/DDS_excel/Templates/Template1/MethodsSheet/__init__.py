from DDS_excel.base_sheet import BaseSheet
from DDS_excel.globals import Globals
import pandas as pd

class MethodsSheet(BaseSheet):

    def __init__(self, file_path: str, globals: Globals):

        self._methods=[]

        try:
            super().__init__(
                file_path=file_path,
                globals=globals,
                sheet_name="Methods"
            )        
      
            self._process_sheet()

        except Exception as e:
            self._sheet_exception(e)

    def _process_sheet(self):
        for i,s in self.sheet.iterrows():
            methdict = {'OID':s['OID'],'name':s['Name'],'type':s['Type'],'description':s['Description']}

            if pd.notna(s['Document']):
                docdict = {'leafID':s['Document']}
                if pd.notna(s['Pages']):
                    docdict['pages'] = [int(x) for x in s['Pages'].split(',')] if isinstance(s['Pages'],str) else [s['Pages']]
                methdict['documents'] = docdict

            if pd.notna(s['Expression Code']):
                ExpDict = {'expression':s['Expression Code']}
                if pd.notna(s['Expression Context']):
                    ExpDict['context'] = s['Expression Code']
                methdict['expressions'] = [ExpDict]

            self._methods.append(methdict)

