# CRF Specializations — provenance

## `cdisc_crf_specializations_draft.csv`

**⚠️ DRAFT DATA — NOT FOR PRODUCTION USE.**

| | |
|---|---|
| Source repository | https://github.com/lexjansen/cdisc360i-pocs |
| Source path | `metadata/cdisc_crf_specializations_draft.csv` |
| Source commit | `8f9e16f3d9af052206edd1bf6c180b470948976c` |
| File last changed upstream | 2025-11-26 |
| Copied into this repo | 2026-08-31 |
| Size / rows | 514,085 bytes; 2,073 data rows + header |
| `package_date` column | `2025-12-31` |

## Why a file and not the CDISC Library

There is no CDISC Library endpoint for CRF Specializations today — the COSMoS OpenAPI
exposes only Biomedical Concept and SDTM Dataset Specialization paths. This CSV is the
COSMoS curation team's draft export and is the only machine-readable source available.

`src/loaders/crf/sources/crf_specializations.py` therefore defines a
`CrfSpecializationSource` abstract base with `CsvCrfSpecializationSource` and
`XlsxCrfSpecializationSource` implementations plus a `LibraryCrfSpecializationSource`
stub. When the Library publishes the endpoint, swapping the source is a
`--crf_spec_source library` config change, not a code change.

## Shape

One row per CRF item. Rows group into CRF groups by `crf_group_id`; group-level columns
(`bc_id`, `vlm_group_id`, `standard`, `domain`, `implementation_option`, `scenario`,
`short_name`, `package_date`, `categories`) repeat on every row of the group.

303 distinct `crf_group_id`, 190 distinct `bc_id`; 71 of the 190 BCs have more than one
group (a Normalized and a Denormalized variant, sometimes several scenarios) — which is
why `crf_loader.py` takes `--implementation_option` and records unresolved ties in the
refinement YAML under `crfGroupChoices`.

`standard` is `CDASHIG` throughout; `standard_start_version` is `2-1` (1,014 rows) or
`2-3` (1,059 rows).

## Known coverage gap on NCT01797120

48 of the study's 82 C-coded Biomedical Concepts are covered by a `bc_id` in this file.
The 34 uncovered ones (RECIST TR/TU/RS, PFT/RE, some LB, ECOG, PE, Randomization,
HBV/HCV/MB) are reported by the loader under `uncoveredConcepts` in the refinement YAML.
ECOG and similar instruments are QRS-backed and are out of scope for the automatic path.

## Not copied

`cdisc_crf_specializations_draft.xlsx` (the same data) and
`cdisc_crf_specializations_forms.xlsx` (form/section layout metadata used by the Phase 1
POCs) were deliberately not copied. `crf_loader.py` derives form composition from USDM
Activities and the CRF refinement YAML rather than from the forms workbook.
