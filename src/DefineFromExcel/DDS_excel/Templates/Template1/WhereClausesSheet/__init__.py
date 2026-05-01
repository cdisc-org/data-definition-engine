from DDS_excel.base_sheet import BaseSheet
from DDS_excel.globals import Globals
import pandas as pd

class WhereClausesSheet(BaseSheet):

    def __init__(self, file_path: str, globals: Globals):

        self._conditions=[]
        self._whereclauses=[]

        try:
            super().__init__(
                file_path=file_path,
                globals=globals,
                sheet_name="WhereClauses"
            )        
      
            self.whereclauses_sheet = self.sheet
            print ('WHERECLAUSES SHEET', self.whereclauses_sheet)

            super().__init__(
                file_path=file_path,
                globals=globals,
                sheet_name="Variables"
            )        

            self.variables_sheet = self.sheet[['Dataset','Variable','OID']].rename(columns={'Dataset':'DatasetOID','OID':'VariableOID'})
        
            super().__init__(
                file_path=file_path,
                globals=globals,
                sheet_name="Datasets"
            )        

            self.datasets_sheet = self.sheet[['Dataset','OID']].rename(columns={'OID':'DatasetOID'})

            self._process_sheet()

        except Exception as e:
            self._sheet_exception(e)

    def _process_sheet(self):
        # Get dataset OID
        wc1 = pd.merge(self.whereclauses_sheet,self.datasets_sheet,how='left',on='Dataset').drop(columns='Dataset')
        print ('WC1: ',wc1)
        # Get variable OID
        wc2 = pd.merge(wc1,self.variables_sheet,how='left',on=['DatasetOID','Variable']).drop(columns=['DatasetOID','Variable'])
        
        # Create rangechecks
        wc2['rangeChecks'] = pd.Series([{'comparator':row.Comparator,'checkValues':str(row.Value).split(','),'item':row.VariableOID,'softHard':'Soft'} for row in wc2.itertuples()])
        print ('WC2: ', wc2)
        # Now group by OID
        wc2gp = wc2.groupby('OID',as_index=False).agg(list)[['OID','rangeChecks']]
        print ('WC2GP 1: ',wc2gp)
        wc2gp['ConditionOID'] = 'COND.'+wc2gp['OID']
        print ('WC2GP 2: ',wc2gp)

        for row in wc2gp.itertuples():
            self._conditions.append({'OID':row.ConditionOID,'rangeChecks':row.rangeChecks})
            self._whereclauses.append({'OID':row.OID,'conditions':[row.ConditionOID]})

        print ('_CONDITIONS: ',self._conditions)