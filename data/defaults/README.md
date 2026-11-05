# Defaults dictionaries

Dictionaries of well-known default values that the defaults loader
([`src/loaders/defaults`](../../src/loaders/defaults/README.md), pipeline stage F) writes into a
DDS where no other loader supplied a value. The format is defined by
[`schemas/defaults/defaults.schema.json`](../../schemas/defaults/defaults.schema.json).

| File | Contents |
|---|---|
| `well_known_defaults.json` | The shared seed: 95 `items` entries for SDTM variables most studies share |

## Specification values, not submission values

The define.xml the pipeline generates is a specification built from the study design, before any
data exist; it can help drive the SDTM programming. These defaults are therefore specification
values. A length is an estimate of the room a variable needs, chosen from the standard where it
sets a limit and estimated otherwise. When the study is complete and the sponsor prepares a
submission, each length should be set to the longest value in the data, as FDA's Study Data
Technical Conformance Guide asks.

The dictionary belongs to the sponsor implementing the DDE: any entry, including the seed, can be
changed, overridden or removed.

## Provenance of the seed

The seed starts from a list of 23 defaults given on 2026-10-26, revised against SDTMIG, controlled
terminology and common practice, and extended to content most studies share. Every entry's
`description` states its basis:

| Basis | Meaning |
|---|---|
| SDTMIG | A data type, a length limit or a derivation that SDTMIG or the SDTM model states. Holds in every study. |
| CT | The longest term in the controlled terminology codelist. |
| MedDRA | The MedDRA format: term names of up to 100 characters, 8-digit codes. |
| Convention | Common practice for the origin. Sponsors differ. |
| Best guess | Lab content assumes a central lab (Collected/Vendor). A default fills only an origin the CRF did not supply: stage E already gives lab variables collected on the CRF Collected/Investigator with their pages, so lab content still unfilled after stage E most likely arrives in a vendor transfer. Change it for a study with local labs. |
| Estimate | A specification length chosen before data exist. |
| Computed | Worked out from the DDS when the loader runs: STUDYID is the length of the study name, USUBJID that plus 9 (two separators, a 3-character site, a 4-character subject). |

The main changes from the original list:

- STUDYID and USUBJID lengths are computed (7 and 14 were too short for NCT01797120's study name);
- --TESTCD length 20 → 8 and --TEST 24 → 40, the SDTMIG limits; --TEST gained an origin;
- --STDY is removed: study days are Derived, and `--DY` covers them;
- the lab range entries have no `dataType` (LBORNRLO is Char in SDTMIG), so their lengths apply to
  the type the CDISC Library gives; LBNRIND is Collected/Vendor;
- REFID became `--REFID`, XSDTC became `--DTC`, and LBDTC and VSDTC merged into `--DTC` entries;
- the duplicate LBSTNRHI (#12) is dropped and the two VISITNUM entries are merged.

The full tables, with each entry's origin in the list, are in
[`DEFAULT_METADATA_LOADER.md`](../../DEFAULT_METADATA_LOADER.md).

## Changing and adding entries

- **Edit the shared file** to change a default for every study.
- **Add a study file** to change it for one study: list it after the shared one under `defaults:`
  in the study's `pipeline.yaml`. Later files win, so an entry with the same name overrides the
  shared one; a field the study entry leaves out still comes from the shared entry.
- **Choose the section** by the kind of object (`items`, `itemGroups`, `crfItems`, `crfSections`),
  name it exactly, by suffix (`--SEQ`) or with `*` plus `domains`, and use DDS attribute names in
  `values` (Length → `length`, def:DisplayFormat → `displayFormat`, def:Origin → `origin: [{type, source}]`).

A study file needs only what it changes:

```json
{
  "$schema": "../../../schemas/defaults/defaults.schema.json",
  "schemaVersion": "1.0",
  "items": [
    { "name": "--DTC", "domains": ["LB"], "description": "Local labs: collected on the CRF.",
      "values": { "origin": [{ "type": "Collected", "source": "Investigator" }] } },
    { "name": "USUBJID", "values": { "length": 18 } }
  ]
}
```

The loader validates every dictionary before it changes anything, and its report lists entries
that matched nothing in the study (`unmatched`), which is where a misspelt name shows up.
