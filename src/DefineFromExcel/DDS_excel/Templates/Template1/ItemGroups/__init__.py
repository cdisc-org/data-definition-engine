from DDS_excel.base_sheet import BaseSheet
from DDS_excel.globals import Globals
import pandas as pd
import traceback

class ItemGroups(BaseSheet):

    def __init__(self, file_path: str, globals: Globals, datamodel: str):

        self._itemGroups=[]

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

            self._process_sheet(datamodel)

        except Exception as e:
            traceback.print_exc()
            self._sheet_exception(e)
            raise
            

    def _process_sheet(self,datamodel):
        # map of attribute names in Datasets sheet to corresponding names in DDS
        attd = {'OID':'OID','Dataset':'name','Description':'description','Structure':'structure','Purpose':'purpose','StandardOID':'standard'}
        attdb = {'Reference Data':'isReferenceData','IsNonStandard':'isNonStandard','HasNoData':'hasNoData'}
 
        for i, s in self.sheet_dataset.iterrows():
            dsdict = {}

            for x in attd:
                if pd.notna(getattr(s,x)):
                    dsdict[attd[x]] = getattr(s,x)

            for x in attdb:
                if getattr(s,x) == 'Yes':
                    dsdict[attdb[x]] = True

            if datamodel == 'SDTMIG':
                dsdict['domain'] = getattr(s,'Dataset')[4:] if getattr(s,'Dataset').startswith('SUPP') else getattr(s,'Dataset')

            dsdict['items'] = list(self.sheet_var[self.sheet_var['Dataset']==s.OID].reset_index(drop=True).sort_values('Order')['OID'])
            dsdict['keySequence'] = list(self.sheet_var[(pd.notna(self.sheet_var['KeySequence'])) & (self.sheet_var['Dataset']==s.OID)].sort_values('KeySequence')['OID'])

            if pd.notna(s.Comment):
                dsdict['comments'] = [s.Comment]

            slicelist = []
            for x in self.sheet_var[(pd.notna(self.sheet_var['Valuelist'])) & (self.sheet_var['Dataset']==s.OID)]['Valuelist']:
                sldict = {'OID':x,'name':x.replace('.','_'),'type':'ValueList'}
                sldict['items'] = list(self.sheet_vlm[self.sheet_vlm['OID']==x]['ItemOID'])
                slicelist.append(sldict)

            if slicelist:
                dsdict['slices'] = slicelist

            self._itemGroups.append(dsdict)


    