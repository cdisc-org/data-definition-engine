# Provenance — vendored COSMoS specialization

This folder vendors a **real, citable** CDISC artifact so the semantic layer of the
DTA logical data model is anchored to a published source, not a fabrication.

## What was vendored

| | |
|---|---|
| Artifact | CDISC SDTM Dataset Specialization — *Hemoglobin Concentration in Blood* |
| `vlm_group_id` | `HGBBLD` |
| `bc_id` (NCI C-code) | `C64848` |
| SDTMIG start version | `3-2` |
| Variables | 12 (`LBTESTCD, LBTEST, LBCAT, LBORRES, LBORRESU, LBSTRESC, LBSTRESN, LBSTRESU, LBLOINC, LBSPEC, LBFAST, LBDTC`) |

## System of record

- Repository: <https://github.com/cdisc-org/COSMoS>
- File: `export/cdisc_sdtm_dataset_specializations_latest.csv`
- Raw URL: <https://raw.githubusercontent.com/cdisc-org/COSMoS/main/export/cdisc_sdtm_dataset_specializations_latest.csv>
- COSMoS `package_date`: **2026-05-26**
- Retrieved: **2026-06-04**

## How to re-derive (verification)

```bash
curl -sL -o /tmp/cosmos_dss.csv \
  https://raw.githubusercontent.com/cdisc-org/COSMoS/main/export/cdisc_sdtm_dataset_specializations_latest.csv

python3 - <<'PY'
import csv
rows = [r for r in csv.DictReader(open('/tmp/cosmos_dss.csv'))
        if r['domain'] == 'LB' and r['vlm_group_id'] == 'HGBBLD']
for r in rows:
    print(r['sdtm_variable'], r['role'], r['assigned_value'] or r['assigned_term'],
          r['codelist'], r['codelist_submission_value'], r['value_list'], r['origin_type'])
PY
```

The 12 rows printed must match `hgbbld.specialization.yaml`. If COSMoS publishes a newer
`package_date`, re-vendor and bump the `packageDate` field in the spec file.

## Why only one specialization (for v0)

The model is a *start*. One real specialization (Hemoglobin) is enough to prove the
linkage pattern end-to-end (USDM BC → DatasetSpecialization → DTA `LabTestResult`).
Adding the rest of the LZZT hematology/chemistry panel is mechanical: append more
`*.spec.yaml` files here, each selected by its `vlm_group_id` from the same export.
