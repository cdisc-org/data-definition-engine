# loaders/methods: SDTM methods for the Derived items

An enrichment loader (DDS in, DDS out), planned as pipeline stage G, after the defaults loader and
before the Define generator. Every Define item with a Derived origin gets a `method`. It comes from a
**library of standard SDTM derivations** (`MT.SEQ`, `MT.DAYCALC`, `MT.STRESN` and so on), or, for a
study-specific derivation, from a placeholder for a person to write. Define-XML 2.1 rule 73 requires
a method on every Derived item. Once each one names a method in the DDS, the Define generator writes
MethodDefs from the DDS and no longer invents placeholders where nobody can review them.

The loader never changes an origin. A method goes only on an item another loader or a person already
made Derived, and an item that already names a method keeps it. The library belongs to the sponsor;
see [`data/methods/README.md`](../../../data/methods/README.md). The design is in
`Plan SDTM MethodDef Loader for the DDS.md`.

## Running it

From `src/`:

```bash
python -m loaders.methods \
  --dds_in  ../output/NCT01797120/dds-defaults.json \
  --dds_out ../output/NCT01797120/dds-methods.json \
  --methods ../data/methods/sdtm_methods.json [study-methods.json ...] \
  --report ../output/NCT01797120/methods-report.yaml [--validate]
```

| Option | Purpose |
|---|---|
| `--dds_in`, `--dds_out` | The defaults loader's DDS and the DDS to write. They must differ, so a re-run starts from the same input. |
| `--methods` | One or more libraries; later files win. Default: `data/methods/sdtm_methods.json`. |
| `--report` | The `methods-report.yaml` to write. |
| `--validate` | Validate the output against the CRF profile JSON Schema. That schema doesn't constrain methods; the loader's own conformance checks always run. |

A library that fails its checks, or a result that fails conformance, stops the loader with exit 1,
and nothing is written. Not yet built: the define patch `methods` section, the pipeline stage and
the open-item count for `--strict` (methods plan M3 and M4).

## What it does, per Derived item

1. **Keeps an existing method.** An item that already names one (anything but `__PLACEHOLDER__`)
   is listed under `kept`.
2. **Finds the best assignment** (`library.py`). Assignments are named the way defaults entries
   are, and ranked the same way (`loaders/common/ranking.py`):
   - an exact name, then a longer `--` suffix, then a shorter one, then `*`;
   - then a value-level `where` that the item's where clause admits (EQ equal to the value, or IN
     listing it; `loaders/common/where_clauses.py`);
   - then a domain filter;
   - then a later file, and a later entry.

   TSSEQ takes `MT.TSSEQ` before `--SEQ`, and SESTDTC takes `MT.SESTDTC` before `--DTC`. The BMI
   assignment (`where VSTESTCD=BMI`) reaches only the value-level VSORRES item for BMI.
3. **Copies the method into `methods` once**, however many items share it: 14 USUBJID items share
   one `MT.USUBJID`. `basis` stays in the library. The DDS requires OIDs that ODM v2.0 lacks, and
   the loader generates them: `PA.<method>.<name>`, `RV.<method>.<name>` and `FE.<method>.<n>`.
4. **Writes a placeholder** for an item no assignment matches: OID `MT.<DS>.<VAR>` (the Define
   generator's own convention, so the OID doesn't change; a value-level item keeps its suffix,
   `MT.VS.VSORRES.BMI`), name `Algorithm to derive <VAR>`, type Computation, description
   `__PLACEHOLDER__` and an empty signature.

A variable Derived both on its value-list parent and at value level gets a method at both levels
(rule 73), and is reported under `bothLevels`, because one level is usually enough.

## Conformance

`conformance.py` checks the DDS the loader is about to write against the Define-XML 2.1 rules that
concern methods, plus what ODM v2.0 needs:

| Rule | Check |
|---|---|
| 73 | Every Derived item has a `method` |
| 74 | Every `method` names an OID in `methods` |
| 56, 210 | Every method has a non-empty `description` (a placeholder is an open item, not a failure) |
| 208, 209 | Every method's `type` is Computation or Imputation |
| 221 | Every expression has a `context` |
| ODM v2.0 | Every method has a `signature`; every expression has exactly one of `expression` or `externalCodeLib` |

Each method OID must also appear only once. The checks cover methods already in the input DDS too,
so a method a person wrote with type Analysis stops the run.

## The report

`methods-report.yaml` is generated on every run, and nothing in it needs an answer:

| Section | Contents |
|---|---|
| `assigned` | Each library method attached, with the assignment that chose it and the items it serves |
| `placeholders` | Each method whose description is still `__PLACEHOLDER__`, with its items |
| `kept` | Derived items that already named a method |
| `bothLevels` | Variables Derived at both the value-list parent and value level |
| `unmatched` | Library assignments no item used: a typo, content the study doesn't have, or an assignment a later file outranks |
| `unreferenced` | Methods already in the input DDS that no item names |

## NCT01797120 (2026-11-20)

On `dds-defaults.json` rebuilt with the SE defaults (open item 1), 71 items are Derived. 52 get
12 library methods: USUBJID 14, --SEQ 13, --STRESC 7, --STRESN 6, --LOBXFL 5, and one each for
TSSEQ, AESTDY (`MT.DAYCALC`), EPOCH, SESTDTC, SEENDTC, SVSTDTC and SVENDTC. The other 19 get
placeholders:
- RSLNKGRP, TRLNKID and TRREFID, which are study-specific;
- 16 timing and dose variables in AE, CM, EC and MH (--ENRF, --STRF, --STRTPT, --ENRTPT, --STTPT,
  --ENTPT, --DOSE, --DOSTXT). They are Derived because the aCRF says Derived/Sponsor, and their
  pins in `origin-review.yaml` are still open. If a person pins them to another origin, the
  placeholders go back down to 3.

The Define generator then writes 31 MethodDefs and makes no placeholders of its own.

## Tests

```bash
cd src/loaders/methods && pytest    # 131 tests, no network
```

| File | Covers |
|---|---|
| `test_library.py` | Loading, layering and refusals; the DDS copy and its OIDs; the PR-DDS-3 slot names pinned |
| `test_seed_odm20.py` | Every seed method as an ODM v2.0 MethodDef, validated against `schemas/odm/2.0/ODM.xsd` |
| `test_matching.py` | The shared ranking, `where`, the seed's assignments, layering |
| `test_loader.py` | Who gets which method, placeholders, the report, the outputs |
| `test_conformance.py` | One failing case per rule; a failure stops the loader before it writes |
