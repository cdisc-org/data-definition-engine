"""Constants for the CRF loader: OID conventions, defaults, and vocabularies.

The OID prefixes here are the contract the CRF generator reads back, and they are chosen
so a combined Define-XML + CRF DDS has no OID collisions: Define item groups are
``IG.<DOMAIN>`` and Define items are ``IT.<DOMAIN>.<VAR>``, while CRF groups take the
``IG.FORM.`` / ``IG.SEC.`` / ``IG.CON.`` sub-namespaces and CRF items take ``IT.CRF.``.
"""
from __future__ import annotations

PLACEHOLDER = "__PLACEHOLDER__"

# --- OID prefixes -----------------------------------------------------------------
FORM_OID_PREFIX = "IG.FORM"
SECTION_OID_PREFIX = "IG.SEC"
CONCEPT_OID_PREFIX = "IG.CON"
CRF_ITEM_OID_PREFIX = "IT.CRF"
CDASH_CODELIST_OID_PREFIX = "CL.CDASH"
CRF_CODELIST_OID_PREFIX = "CL.CRF"
STUDY_EVENT_OID_PREFIX = "SE"
CONCEPT_REF_OID_PREFIX = "CONC"

STD_CDASHIG_OID = "STD.CDASHIG"
STD_CDASHCT_OID = "STD.CDASHCT"
ACRF_LEAF_ID = "LF.acrf"
ACRF_HREF = "acrf.html"

CRF_PROFILE_URI = "https://cdisc.org/dds/profiles/crf/1.0"
DEFINE_PROFILE_URI = "https://cdisc.org/dds/profiles/define-xml/1.0"

# --- CDISC Library ----------------------------------------------------------------
CDISC_ORG_SYSTEM = "http://www.cdisc.org"
LIBRARY_BASE = "https://library.cdisc.org/api"
BC_SYSTEM = f"{LIBRARY_BASE}/mdr/bc/biomedicalconcepts"
SDTM_DSS_SYSTEM = f"{LIBRARY_BASE}/mdr/specializations/sdtm/datasetspecializations"
CRF_SPEC_SYSTEM = f"{LIBRARY_BASE}/mdr/specializations/crf/specializations"

DEFAULT_CDASHIG_VERSION = "2.3"
DEFAULT_IMPLEMENTATION_OPTION = "Denormalized"
DEFAULT_LANGUAGE = "en"

# --- Value maps -------------------------------------------------------------------
#: CRF-specialization data types -> DDS/ODM data types. ODM 1.3.2 has no ``decimal``,
#: so ``decimal`` canonicalizes to ``float``, which both ODM versions accept.
DATATYPE_MAP = {
    "text": "text",
    "integer": "integer",
    "decimal": "float",
    "float": "float",
    "date": "date",
    "time": "time",
    "datetime": "datetime",
    "boolean": "boolean",
}

YES_NO = {"Y": True, "YES": True, "N": False, "NO": False, "": False}

#: USDM timing type C-codes -> DDS timing types.
TIMING_TYPE_MAP = {
    "C201358": "Fixed",    # Fixed Reference
    "C201356": "After",    # After
    "C201357": "Before",   # Before
    "C201359": "Fixed",    # Fixed
}

#: Alias @Context vocabulary (CRF_GEN_PLAN.md §5.5). One contract for both ODM
#: emitters and both stylesheets.
ALIAS_CONTEXTS = frozenset({
    "SDTM", "CDASH", "prompt", "completionInstructions", "implementationNotes",
    "cdiscNotes", "definition", "mappingInstructions", "preSpecifiedValue",
    "selectionType", "renderingHint", "subsetOf", "timing", "section", "sectionOrder",
    "BC", "SDTMSpecialization", "CRFSpecialization", "USDM", "nci:ExtCodeID", "Standard",
})

#: Origins assigned to CRF items by how the item is populated.
ORIGIN_COLLECTED = {"type": "Collected", "source": "Investigator"}
ORIGIN_PROTOCOL = {"type": "Protocol", "source": "Sponsor"}
ORIGIN_ASSIGNED = {"type": "Assigned", "source": "Sponsor"}


def generate_oid(descriptors: list[str]) -> str:
    """Join OID descriptors the way ``DefineObject.generate_oid`` does.

    Uppercases, replaces spaces with hyphens, and avoids doubling a prefix that the
    caller already prepended.
    """
    parts = [str(d) for d in descriptors if d not in (None, "")]
    if len(parts) > 1 and parts[1].startswith(parts[0] + "."):
        oid = ".".join(parts[1:])
    else:
        oid = ".".join(parts)
    return oid.upper().replace(" ", "-")
