"""Constants for the CRF generator.

The Alias ``@Context`` vocabulary here is the single contract shared by both ODM emitters
and both stylesheets: whatever ODM 2.0 expresses with a native element, ODM 1.3.2
expresses as an ``Alias`` with the matching context.
"""
from __future__ import annotations

DEFAULT_LANGUAGE = "en"
PLACEHOLDER = "__PLACEHOLDER__"
DEFAULT_ORIGINATOR = "CDISC 360i DDE"
DEFAULT_SOURCE_SYSTEM = "odmlib"

ACRF_LEAF_ID = "LF.acrf"
ACRF_HREF = "acrf.html"

ODM_VERSIONS = ("1.3.2", "2.0")

NS_URI = {
    "odm_1_3_2": "http://www.cdisc.org/ns/odm/v1.3",
    "odm_2_0": "http://www.cdisc.org/ns/odm/v2.0",
}
MODEL_PACKAGE = {"1.3.2": "odm_1_3_2", "2.0": "odm_2_0"}

# --- Alias contexts ---------------------------------------------------------------
CTX_SDTM = "SDTM"
CTX_CDASH = "CDASH"
CTX_PROMPT = "prompt"
CTX_DEFINITION = "definition"
CTX_COMPLETION = "completionInstructions"
CTX_IMPLEMENTATION = "implementationNotes"
CTX_CDISC_NOTES = "cdiscNotes"
CTX_MAPPING = "mappingInstructions"
CTX_PRESPECIFIED = "preSpecifiedValue"
CTX_SELECTION = "selectionType"
CTX_RENDERING = "renderingHint"
CTX_SUBSET_OF = "subsetOf"
CTX_TIMING = "timing"
CTX_SECTION = "section"
CTX_SECTION_ORDER = "sectionOrder"
CTX_BC = "BC"
CTX_SDTM_SPEC = "SDTMSpecialization"
CTX_CRF_SPEC = "CRFSpecialization"
CTX_USDM = "USDM"
CTX_NCI = "nci:ExtCodeID"
CTX_STANDARD = "Standard"

# --- Value maps -------------------------------------------------------------------
#: ODM 1.3.2 ItemGroupDef/@Repeating and FormDef/@Repeating are Yes/No only.
REPEATING_TO_132 = {"No": "No", "Simple": "Yes", "Static": "Yes", "Dynamic": "Yes"}

#: ODM 1.3.2 has no ``decimal``; the DDS canonical type is already ``float``.
DATATYPE_TO_ODM = {
    "text": "text", "integer": "integer", "float": "float", "decimal": "float",
    "date": "date", "time": "time", "datetime": "datetime", "boolean": "boolean",
    "string": "string",
}

#: ODM 2.0 ODM/@Context is a closed set that has no "Other" - the DDS default.
ODM20_CONTEXT = {"Other": "Exchange", "Submission": "Submission",
                 "Archive": "Archive", "Exchange": "Exchange"}

#: ODM 2.0 Standard/@Status is title-case; the DDS writes "FINAL".
STANDARD_STATUS = {"FINAL": "Final", "DRAFT": "Draft", "PROVISIONAL": "Provisional"}

#: ODM 2.0 Standard/@Name is a closed enumeration that has NO ``CDASHIG`` value, so a
#: CDASHIG standard cannot be emitted as a native ``Standard`` element there. Standards
#: whose name is outside this set become ``Protocol/Alias Context=Standard`` instead.
#: Source: schemas/odm/2.0/ODM-enumerations.xsd, simpleType ``StandardName``.
ODM20_STANDARD_NAMES = frozenset({
    "ADaMIG", "CDISC/NCI", "SDTMIG", "SDTMIG-AP", "SDTMIG-MD",
    "SENDIG", "SENDIG-AR", "SENDIG-DART",
})

CRF_GROUP_TYPES = frozenset({"Form", "Section", "Concept"})
