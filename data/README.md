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
        │   ├── NCT01797120-{YYYYMMDDTHHmm}.json         # USDM 4.0 protocol export
        │   └── NCT01797120-define-{YYYYMMDDTHHmm}.json  # ODM 1.3.2 Define-XML export
        └── LZZT/                   # Study H2Q-MC-LZZT (CDISC Pilot)
            ├── H2Q-MC-LZZT-{YYYYMMDDTHHmm}.json         # USDM 4.0 protocol export
            └── H2Q-MC-LZZT-define-{YYYYMMDDTHHmm}.json  # ODM 1.3.2 Define-XML export
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
| `{studyId}-define-{timestamp}.json` | ODM 1.3.2 | Dataset/variable definitions in Define-XML format |

Filenames include an ISO 8601 timestamp (`YYYYMMDDTHHMM`) recording when the export was generated. When multiple exports exist for the same study, the most recent timestamp is the current working version.
