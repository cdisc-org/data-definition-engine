from odmlib.define_2_1 import model as DEFINE
import datetime
import uuid


class ODM:
    def __init__(self, file_oid: str | None = None):
        self.attrs = self._set_attributes(file_oid)

    def create_root(self):
        """Instantiate and return the odmlib ODM root element."""
        return DEFINE.ODM(**self.attrs)

    def _set_attributes(self, file_oid: str | None):
        return {
            "FileOID": file_oid or f"ODM.DEFINE21.{uuid.uuid4()}",
            "AsOfDateTime": self._set_datetime(),
            "CreationDateTime": self._set_datetime(),
            "ODMVersion": "1.3.2",
            "FileType": "Snapshot",
            "Originator": "360i Define-XML Team",
            "SourceSystem": "odmlib",
            "SourceSystemVersion": "0.2",
            "Context": "Other",
        }

    @staticmethod
    def _set_datetime():
        """return the current datetime in ISO 8601 format"""
        return datetime.datetime.now(datetime.timezone.utc).isoformat()
