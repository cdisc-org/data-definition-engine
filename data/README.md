# Data Directory

Input and reference data for the data-definition-engine. Files are organized by source and study.

## Directory Structure

```
data/
├── archive/                        # Superseded files kept for reference
│   └── protocol/
│       └── LZZT/
│           └── usdm/
│               └── pilot_LLZT_protocol.json   # Earlier USDM draft for LZZT pilot
├── metadata_xlsx/                  # Excel-based metadata specifications
│   ├── LZZT/
│   │   ├── CDISCPILOT01-ADaM-2026-02-23.xlsx  # ADaM metadata for CDISC Pilot 01 (LZZT)
│   │   └── CDISCPILOT01-SDTM-2026-02-23.xlsx  # SDTM metadata for CDISC Pilot 01 (LZZT)
│   └── templates/
│       └── Define-Excel-Spec.xlsx             # Template for the Define-XML Excel spec format
└── soa_workbench/                  # Exports from the SOA Workbench tool
    └── protocols/
        ├── HCT01797120/            # Study NCT01797120
        │   ├── NCT01797120-latest.json         # USDM 4.0 protocol export
        │   └── NCT01797120-define-latest.json  # Define-JSON export
        └── LZZT/                   # Study H2Q-MC-LZZT (CDISC Pilot)
            ├── H2Q-MC-LZZT-latest.json         # USDM 4.0 protocol export
            └── H2Q-MC-LZZT-define-latest.json  # Define-JSON export
```

## Subdirectories

### `archive/`

Older or superseded files retained for historical reference. Not used as active inputs.

### `metadata_xlsx/`

Excel workbooks containing SDTM and ADaM dataset/variable metadata in the Define-XML Excel spec format. The `templates/` subfolder holds the blank template used as a starting point for new studies.

### `soa_workbench/`

JSON exports from the [SOA Workbench](https://soa-workbench.cdisc.org) tool, organized by study identifier. Each study folder contains two file types:

| Suffix | Format | Description |
|---|---|---|
| `{studyId}-{timestamp}.json` | USDM 4.0 | Protocol-level study definition (schedule of activities, visits, arms) |
| `{studyId}-define-{timestamp}.json` | Define-JSON | Dataset/variable definitions in Define-JSON format |

Filenames include an ISO 8601 timestamp (`YYYYMMDDTHHMM`) recording when the export was generated. When multiple exports exist for the same study, the most recent timestamp is the current working version.


## USDM Version Identification

There is a new `extensionAttribute` that can be used ot determine the date of USDM JSON generation.  Check in tteh `study.versions` class entity:

```JSON
"extensionAttributes": [
    {
    "id": "ExtensionAttribute_44",
    "url": "http://www.cdisc.org/usdm/extensions/studyDesignSolution",
    "valueExtensionClass": {
        "id": "ExtensionClass_1",
        "url": "http://www.cdisc.org/usdm/extensions/StudyDesignSolution",
        "extensionAttributes": [
        {
            "id": "ExtensionAttribute_45",
            "url": "tool-name",
            "valueString": "SoA Workbench",
            "instanceType": "ExtensionAttribute"
        },
        {
            "id": "ExtensionAttribute_46",
            "url": "tool-version",
            "valueString": "1.4.0",
            "instanceType": "ExtensionAttribute"
        },
        {
            "id": "ExtensionAttribute_47",
            "url": "usdm-creation-date",
            "valueString": "20260618T15:11",
            "instanceType": "ExtensionAttribute"
        }
        ],
        "instanceType": "ExtensionClass"
    },
    "instanceType": "ExtensionAttribute"
    }
]
```

This `extensionAttribute` identifies the USDM was generated using the SoA Workbench, version 1.4 on 2026-06-18 at 15:11.

If raising issues with the USDM JSON file, include all of this information to make support easier.