from DDS_excel.base_sheet import BaseSheet
from DDS_excel.globals import Globals
import pandas as pd

class CodeListsSheet(BaseSheet):

    def __init__(self, file_path: str, globals: Globals):

        self._codelists=[]

        try:
            super().__init__(
                file_path=file_path,
                globals=globals,
                sheet_name="CodeLists"
            )        
            self.sheet_CodeLists = self.sheet
            self._process_sheet()

        except Exception as e:
            self._sheet_exception(e)

    def _process_sheet(self):
        self.sheet.columns = ['OID','name','CLCode','dataType','Order','codedValue','TMCode','decode','comments','isNonStandard','standard']
        for keys, dfs in self.sheet_CodeLists.groupby(['OID','name','CLCode','dataType','comments','isNonStandard','standard'],dropna=False):
            CLDict = {'OID':keys[0],'name':keys[1],'dataType':keys[3]}

            # True codelists have coded terms
            if pd.notna(dfs.iloc[0]['codedValue']):
                CLDict ['coding'] = [{'code':keys[2],'codeSystem':'nci:ExtCodeID'}]
                ItemsList = []
                for row in dfs.itertuples():
                    ItemDict = {'codedValue':row.codedValue,'coding':{'code':row.TMCode,'codeSystem':'nci:ExtCodeID'}}
                    if pd.notna(row.decode):
                        ItemDict['decode'] = row.decode
                    ItemsList.append(ItemDict)

                if pd.notna(keys[4]):
                    CLDict['comments'] = [keys[4]]
                
                if pd.notna(keys[5]) and keys[5].upper() == 'YES':
                    CLDict['isNonStandard'] = True

                if pd.notna(keys[6]):
                    CLDict['standard'] = keys[6]

                CLDict['codeListItems'] = ItemsList

            # Otherwise assume a dictionary definition
            else:
                CLDict['wasDerivedFrom'] = 'DICT.'+ keys[0]
                CLDict['codeListItems'] = []

            self._codelists.append(CLDict)

