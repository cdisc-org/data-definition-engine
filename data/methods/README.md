# SDTM method library

Standard SDTM derivations that the methods loader (`src/loaders/methods`, pipeline stage G) attaches
to Derived items in a DDS, so the Define generator writes real MethodDefs instead of placeholders.
The format is defined by [`schemas/methods/methods.schema.json`](../../schemas/methods/methods.schema.json).
The design is in `Plan SDTM MethodDef Loader for the DDS.md`, and the DDS model changes it relies on
are in `DDS_FOR_METHODS.md`.

| File | Contents |
|---|---|
| `sdtm_methods.json` | The shared seed: 22 methods, each with a draft MethodSignature, and 22 assignments |

## Shape of the library

- **`methods`** holds finished, shared methods in the MSG v2 style: one method per algorithm
  (`MT.SEQ`, `MT.DAYCALC`, `MT.STRESN`), with generic `--` text and no domain in the OID. Each entry
  is a DDS Method in ODM v2.0 form, the shape proposed upstream as PR-DDS-3: `OID`, `name`, `type`
  (Computation or Imputation, Define-XML 2.1 rule 209), `description`, a `signature` of named, typed,
  ordered `parameters` and `returnValues`, and optionally `expressions` and `documents`. The loader
  copies an entry into the DDS unchanged, apart from `basis`, which stays in the library, and the
  OIDs it adds: the DDS model makes Parameter, ReturnValue and FormalExpression identifiable, so each
  gets a stable OID where the library gives none (`PA.DAYCALC.DTC`, `RV.DAYCALC.DY`, `FE.DAYCALC.1`).
  ODM v2.0 has no such OIDs, so an ODM v2.0 export drops them.
- **`assignments`** say which Derived items get each method. They are named the way defaults
  entries are: exact (`TSSEQ`), suffix (`--SEQ`), or `*` with `domains`, optionally narrowed by
  `domains`, `excludeDomains` and, at value level, `where` (`{"VSTESTCD": "BMI"}`).
- An **expression** carries a `context` and exactly one body: inline code (`expression`) or an
  `externalCodeLib` reference (`library`, `method`, `version`, `ref`, `href`). The seed ships none;
  the format is ready for automating SDTM transformations later.

```json
"expressions": [
  {"context": "R (sdtm.oak 0.2.0)",
   "externalCodeLib": {"library": "sdtm.oak", "method": "derive_study_day", "version": "0.2.0",
                       "href": "https://pharmaverse.github.io/sdtm.oak/reference/derive_study_day.html"}}
]
```

Define-XML 2.1 cannot carry a signature or an external code reference, so the Define generator drops
both and counts them in its method summary. Inline code becomes a `FormalExpression`.

## Methods attach only to Derived items

The loader never changes an origin. A method goes only on an item another loader or a person already
made Derived (CDISC rule 73 requires a MethodOID there; Pinnacle 21 reportedly flags one elsewhere).
That is why `--DY` can be a suffix entry: VISITDY is Protocol, so it never reaches the library.

## Provenance of the seed

Every method's `basis` says where its wording and signature come from:

| Basis | Methods | Meaning |
|---|---|---|
| SDTM-MSG v2.0 define.xml, verbatim | MT.SEQ, MT.DAYCALC, MT.STRESN, MT.LOBXFL, MT.EPOCH, MT.SEENDTC, MT.SVSTDTC, MT.SVENDTC, MT.RFSTDTC, MT.RFENDTC, MT.RFXSTDTC, MT.RFXENDTC, MT.RFPENDTC, MT.DTHFL | The MethodDef text in the MSG v2.0 sample submission define.xml (cdiscpilot01) |
| SDTM-MSG v2.0, corrected or generalized | MT.TSSEQ ("for per" corrected), MT.SESTDTC ("if set" corrected), MT.STRESC (MT.LBSTRESC generalized to `--`, as MSG did for STRESN) | MSG text with the change the basis names |
| CRF Specialization | MT.BMI | The BMI row's `derivation_description` in `data/crf_specializations/cdisc_crf_specializations_draft.csv` |
| **Draft** | MT.USUBJID, MT.RFICDTC, MT.AGE, MT.ISO8601 | New text. It must be checked against the SDTMIG CDISC Notes in the CDISC Library before the seed is treated as final. MT.USUBJID is a sponsor convention (STUDYID, SITEID, SUBJID) that matches the defaults dictionary's USUBJID length basis; SDTM-MSG v2.0 section 5.2.1 says the concatenation is not required. |

The **signatures** are drafts written for this seed: ODM v2.0 requires a MethodSignature on every
MethodDef, and MSG v2 has none. Parameter names follow the SDTM variables or CDASH fields they stand
for, without the domain prefix where a shared method serves many domains (`DTC`, `ORRES`). --DTC
values can be partial ISO 8601 dates, but the DDS DataType has no partial types until PR-DDS-3 adds
them, so date parameters use `datetime` for now.

**Considered but not seeded:** --BLFL (MSG v2 uses only --LOBXFL), VISITNUM and VISIT in SV,
IEORRES, --ENTPT and --TPT. Their MSG v2 and CDISC01 text is study-specific; add them in a study file.

## Changing and adding entries

- **Edit the shared file** to change a method for every study.
- **Add a study or sponsor file** listed after the shared one under `methods:` in the study's
  `pipeline.yaml`. A file that defines an OID again replaces the seed's entry as a whole; a new
  assignment can point an item at any method a loaded file defines, so re-pointing never needs a
  method copied. Later files outrank earlier ones at equal rank.

A study file needs only what it adds or changes:

```json
{
  "$schema": "../../../schemas/methods/methods.schema.json",
  "schemaVersion": "1.0",
  "methods": [
    {"OID": "MT.ENTPT", "name": "Algorithm to derive --ENTPT", "type": "Computation",
     "description": "If --ENRTPT is populated, --ENTPT is DM.RFPENDTC for the subject.",
     "signature": {"parameters": [{"name": "RFPENDTC", "dataType": "datetime", "orderNumber": 1}],
                   "returnValues": [{"name": "ENTPT", "dataType": "text", "orderNumber": 1}]},
     "basis": "SDTM-MSG v2.0 MT.AEENTPT, generalized"}
  ],
  "assignments": [{"name": "--ENTPT", "method": "MT.ENTPT"}]
}
```

The loader checks every file before it changes anything: the schema, one definition per OID and one
assignment per name and filter in each file, unique signature names and order numbers, and that every
assignment names a defined method. `src/loaders/methods/tests/test_seed_odm20.py` also builds every
seed method as an ODM v2.0 MethodDef and validates it against `schemas/odm/2.0/ODM.xsd`.

## How the seed was checked

The seed was run over a DDS built from the SDTM-MSG v2.0 sample define.xml, with the method
references stripped. On its own it gives 77 of MSG's 91 Derived items MSG's own method.
`src/loaders/methods/tests/fixtures/msg_v2_methods.json` is a worked study file: it adds MSG's 13
other methods and 13 assignments, and with it listed after the seed all 91 match. The CDISC 2019
Define-XML 2.1 SDTM example and a hand-built DM, BMI and ISO 8601 fixture are the other checks; see
[`src/loaders/methods/tests/fixtures/README.md`](../../src/loaders/methods/tests/fixtures/README.md).
