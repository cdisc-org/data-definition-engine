# print ('hello')
# %%
from pathlib import Path
from DDS_main import DDSMain
import os

dde = DDSMain()

# %%

BASE_DIR = Path(os.getcwd())
print ('BASE DIR: ', BASE_DIR)
file = BASE_DIR / ".." / "DDS_excel" / "Templates" / "Template1" / "Sample1.xlsx"
print ('FILE: ',file)
template = 'Template1'
errors = dde.from_excel(file,template)
# %%
# %%


