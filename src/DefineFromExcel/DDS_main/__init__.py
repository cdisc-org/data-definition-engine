import json
import traceback
from uuid import uuid4
from DDS_excel import DDSExcel
from DDS_main.errors_and_logging.errors_and_logging import ErrorsAndLogging
from DDS_main.errors_and_logging.errors import Errors


class DDSMain:

    def __init__(self):
        self._wrapper = None
        self._excel = None
        self._errors_and_logging = ErrorsAndLogging()

    def errors(self):
        return self._errors_and_logging.errors().dump(Errors.WARNING)

    def excel(self):
        return self._excel

    def from_excel(self, file_path, xltemplate):
        self._excel = DDSExcel(file_path,xltemplate)
        self._wrapper = self._excel.execute()
        return self._excel.errors()

