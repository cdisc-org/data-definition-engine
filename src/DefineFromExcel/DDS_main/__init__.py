import json
import pandas as pd
from uuid import uuid4
from DDS_excel import DDSExcel
from DDS_main.errors_and_logging.errors_and_logging import ErrorsAndLogging
from DDS_main.errors_and_logging.errors import Errors
from pathlib import Path
from linkml.validator import validate_file

class DDSMain:

    def __init__(self):
        self._wrapper = None
        self._excel = None
        self._errors_and_logging = ErrorsAndLogging()

    def errors(self):
        return self._errors_and_logging.errors().dump(Errors.WARNING)

    def excel(self):
        return self._excel

    def from_excel(self, file: Path, xltemplate, schema_file: Path):
        self._excel = DDSExcel(file,xltemplate)
        self._wrapper = self._excel.execute()

        # Write to file
        with open (file.with_suffix('.json'),'w') as f:
            f.write(json.dumps(self._wrapper,indent=2))

        # Validate
        # val_errors = []
        # self.validation_report = validate_file(file.with_suffix('.json'),str(schema_file))

        # if report.results:
        #     for result in report.results:
        #         val_errors.append({'Message':str(result)})

        # else:
        #     val_errors.append({"Message":'No schema validation errors!'})

        # pd.DataFrame(val_errors).to_excel(file.with_name(file.stem+"_schema_validation.xlsx"))

        # print("input file      :", file.resolve())
        # print("json output     :", file.with_suffix('.json').resolve())
        # print("validation file :", file.with_name(file.stem+"_schema_validation.xlsx").resolve())


        return self._excel.errors()

