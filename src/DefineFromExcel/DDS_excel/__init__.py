from DDS_excel.errors_and_logging.errors import Errors
from DDS_excel.globals import Globals
import importlib



class DDSExcel:

    def __init__(self, file_path, xltemplate):
        self._globals = Globals()
        self._file_path = file_path
        self._plugin = importlib.import_module(f"DDS_excel.Templates.{xltemplate}.Process")

        self._template = {
            'OID': '',
            'name': '',
            'description': '',
            'fileOID': '',
            'creationDateTime': '',
            'odmVersion': '1.3.2',
            'fileType': 'Snapshot',
            'originator': 'Define-360i Processor',
            'context': 'Other',
            'defineVersion': '2.1.0',
            'studyOID': '',
            'studyName': '',
            'studyDescription': '',
            'protocolName': '',
            'itemGroups': [],
            'conditions': [],
            'whereClauses': [],
            'codeLists': [],
            'methods': [],
            'standards': [],
            'annotatedCRF': [],
            'concepts': [],
            'conceptProperties': []
        }        

    def execute(self):
        self._globals.create()
        return self._plugin.process(self._file_path,self._globals,self._template)

    def errors(self):
        return self._globals.errors_and_logging.errors().dump(Errors.WARNING)


