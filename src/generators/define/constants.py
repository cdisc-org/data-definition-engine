"""
Constants used throughout the template2define codebase.

This module centralizes magic strings and values to improve maintainability
and make the codebase easier to understand.
"""

# Trial design domains - datasets with IsReferenceData = "Yes"
TRIAL_DESIGN_DOMAINS: frozenset[str] = frozenset(["TA", "TD", "TE", "TI", "TM", "TS", "TV"])

# Non-repeating domains - datasets with Repeating = "No" (subject-level fixtures)
NON_REPEATING_DOMAINS: frozenset[str] = frozenset(["DM", "APDM", "ADSL", "DI", "OI"])

# def:Standard/@Name values the Define-XML 2.1 schema allows (define-enumerations.xsd StandardName).
# A combined DDS also carries the CRF's CDASHIG standard, which has no Define-XML 2.1 name.
DEFINE_STANDARD_NAMES: frozenset[str] = frozenset([
    "ADaM-OCCDSIG", "ADaMIG", "ADaMIG-MD", "ADaMIG-NCA", "ADaMIG-popPK", "BIMO", "CDISC/NCI", "SDTMIG",
    "SDTMIG-AP", "SDTMIG-MD", "SENDIG", "SENDIG-AR", "SENDIG-DART", "SENDIG-GENETOX",
])

# Default values
DEFAULT_PURPOSE: str = "Tabulation"
DEFAULT_LANGUAGE: str = "en"

# OID prefixes used in generate_oid()
LEAF_PREFIX: str = "LF."
ACRF_LEAF_ID: str = "LF.acrf"

# Default file names
DEFAULT_ACRF_FILENAME: str = "acrf.pdf"
DEFAULT_OUTPUT_FILE: str = "tests/fixtures/define-360i.xml"
