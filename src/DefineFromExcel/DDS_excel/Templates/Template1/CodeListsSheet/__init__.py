from DDS_excel.base_sheet import BaseSheet
from DDS_excel.globals import Globals
import pandas as pd

class StandardsSheet(BaseSheet):

    def __init__(self, file_path: str, globals: Globals, template: dict):

        self._codelists=[]

        try:
            super().__init__(
                file_path=file_path,
                globals=globals,
                sheet_name="CodeLists"
            )        
      
            self._process_sheet()

        except Exception as e:
            self._sheet_exception(e)

    def _process_sheet(self):
        self.sheet.columns = ['OID','name','CLCode','dataType','Order','codedValue','TMCode','decode','comments','isNonStandard','standard']
        for keys, dfs in self.sheet.groupby(['OID','name','CLCode','dataType','comments','isNonStandard','standard'],dropna=False):
            CLDict = {'OID':keys[0],'name':keys[1],'coding':[{'code':keys[2],'codeSystem':'nci:ExtCodeID'}],'dataType':keys[3]}

            ItemsList = []
            for row in dfs.itertuples():
                ItemDict = {'codedValue':row.codedValue,'coding':[{'code':row.TMCode,'codeSystem':'nci:ExtCodeID'}]}
                if pd.notna(row.decode):
                    ItemDict['decode'] = row.decode
                ItemsList.append(ItemDict)

            if pd.notna(keys[4]):
                pass
            
            if keys[5].upcase() == 'YES':
                CLDict['isNonStandard'] = True

            if pd.notna(keys[6]):
                pass

            CLDict['codeListItems'] = ItemsList

