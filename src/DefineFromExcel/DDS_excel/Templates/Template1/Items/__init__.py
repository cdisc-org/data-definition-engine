from DDS_excel.base_sheet import BaseSheet
from DDS_excel.globals import Globals
import pandas as pd
import traceback

class ItemDefs(BaseSheet):

    def __init__(self, file_path: str, globals: Globals):

        self._items=[]

        try:
            super().__init__(
                file_path=file_path,
                globals=globals,
                sheet_name="Datasets"
            )        

            self.sheet_dataset = self.sheet
      
            super().__init__(
                file_path=file_path,
                globals=globals,
                sheet_name="Variables"
            )              

            self.sheet_var = self.sheet

            super().__init__(
                file_path=file_path,
                globals=globals,
                sheet_name="ValueLevel"
            )              

            self.sheet_vlm = self.sheet

            self._process_sheet()

        except Exception as e:
            traceback.print_exc()
            self._sheet_exception(e)
            raise
            

    def _process_sheet(self):
        # map of attribute names in Variables sheet to corresponding names in DDS
        attvar = {'OID':'OID','Variable':'name','Label':'description','Data Type':'dataType','Length':'length','Significant Digits':'significantDigits','Format':'displayFormat','Role':'role','CodeList':'codeList','Method':'method'}
        attvarb = {'Mandatory':'mandatory','IsNonStandard':'isNonStandard','HasNoData':'hasNoData'}
        attvlm = {'ItemOID':'OID','Name':'name','Description':'description','Data Type':'dataType','Length':'length','Significant Digits':'significantDigits','Format':'displayFormat','Codelist':'codeList','Method':'method'}
        attvlmb = {'Mandatory':'mandatory'}

        for ds in self.sheet_dataset['OID']:

            for i,s in self.sheet_var[self.sheet_var['Dataset']==ds].reset_index(drop=True).iterrows():

                self._items.append(CreateItem(s,attvar,attvarb))

                if pd.notna(s.Valuelist):
                    for iv, sv in self.sheet_vlm[self.sheet_vlm['OID']==s.Valuelist].reset_index(drop=True).iterrows():
                        vlmitemdict = CreateItem(sv,attvlm,attvlmb)
                        vlmitemdict['applicableWhen'] = [sv['Where Clause']]
                        self._items.append(vlmitemdict)


def CreateItem(row,names,namesb):
    itemdict = {}

    for x in names:
        if pd.notna(getattr(row,x)):
            itemdict[names[x]] = getattr(row,x)

    for x in namesb:
        if getattr(row,x) == 'Yes':
            itemdict[namesb[x]] = True

    origindict = {}
    docdict = {}
    if pd.notna(row['Origin Type']):
        origindict['type'] = row['Origin Type']
    if pd.notna(row['Origin Source']):
        origindict['source'] = row['Origin Source']
    if pd.notna(row.Document):
        docdict['leafID'] = row.Document
        if pd.notna(row.Pages):
            docdict['pages']=row.Pages.split(',')
        origindict['documents'] = docdict
    if origindict:
        itemdict['origin'] = origindict

    if pd.notna(row.Comment):
        itemdict['comments'] = [row.Comment]
        
    return itemdict

