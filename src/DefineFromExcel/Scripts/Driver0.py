from pathlib import Path
from DDS_main import DDSMain
import json
import os

dde = DDSMain()

instanceName = 'Sample1' # Excel file name without the path
template = 'Template1'

# Assumes current directory is data-definition-engine/src/DefineFromExcel/Scripts
#BASE_DIR = Path(os.getcwd())
BASE_DIR = Path(__file__).parent
print ('BASEDIR: ', BASE_DIR)
file = BASE_DIR / ".." / "DDS_excel" / "Templates" / template / f"{instanceName}.xlsx"
print ('FILE: ',file)
# schema_file = BASE_DIR / ".." / ".." / "define-xml" / "define.yaml"
# Test schema file
schema_file = BASE_DIR / '..' / 'defineTest.yaml'

errors = dde.from_excel(file,template,schema_file)



