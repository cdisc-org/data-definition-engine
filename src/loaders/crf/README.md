# crf_loader.py — the DDE's CRF loader

Adds CRF metadata to a DDS JSON file. It is an **enrichment loader**: it reads the
Define DDS that `create_define_json.py` produced plus the USDM study design, and writes a
**combined DDS** carrying both Define-XML and CRF metadata.

```
USDM ──┬─► create_define_json.py ─► Define DDS ──┐
       │                                          ├─► crf_loader.py ─► combined DDS
       └──────────────────────────────────────────┘        ▲
   CRF Specializations (CSV) ───────────────────────────────┤
   CDISC Library (CDASHIG + CDASH CT) ───────────────────────┘
```

The combined DDS is the contract: `define_generator.py` and `crf_generator.py` each read
it and ignore the sections they do not own.

## Requirements

```bash
pip install -r requirements.txt
```

A CDISC Library API key is required, from `--cdisc_api_key`, the `CDISC_API_KEY`
environment variable, or a `.env` file. `.env` is looked for beside this module, at the
repository root, and in `src/define-xml/` — so a key already set up for the Define loader
is found without copying it.

## Running it

```bash
cd src/loaders/crf

python crf_loader.py \
  --dds_in   ../../../output/NCT01797120-dds.json \
  --usdm_file ../../../data/protocols/NCT01797120/NCT01797120-latest.json \
  --dds_out  ../../../output/NCT01797120-dds-crf.json \
  --crf_spec_file ../../../data/crf_specializations/cdisc_crf_specializations_draft.csv \
  --cdashig 2.3 --cdashct 2026-03-27 \
  --patch_file ../../../output/crf-refinement.yaml \
  --validate --validation_report ../../../output/crf-validation.xlsx --debug
```

It also runs as a module from `src/`: `python -m loaders.crf.crf_loader ...`.

### Options

| Flag | Default | Notes |
|---|---|---|
| `--dds_in`, `--usdm_file`, `--dds_out` | required | |
| `--crf_spec_file` | required | `.csv`/`.xlsx`; override detection with `--crf_spec_source` |
| `--crf_spec_source` | `auto` | `csv`, `xlsx`, or `library` (not implemented — no endpoint exists yet) |
| `--cdashig` | `2.3` | CDASHIG version |
| `--cdashct` | required | CDASH CT package date, `yyyy-mm-dd` |
| `--sdtmct` | from `--dds_in` | fallback CT for codelists absent from CDASH CT |
| `--implementation_option` | `Denormalized` | preferred variant when a concept has several CRF groups |
| `--studyversion` / `--studydesign` / `--timeline` | `0` / `0` / `mainTimeline` | |
| `--patch_file` / `--apply_patch` | — | `--apply_patch` requires `--patch_file` |
| `--validate [schema]` / `--validation_report` | CRF profile schema | xlsx report |
| `--cache_dir` / `--no_cache` | `.cache/cdisc_library` | disk cache of Library responses |
| `--include_uncovered` | off | placeholder concepts for BCs with no CRF specialization |
| `--debug` | off | writes `debug_crf_*.json` beside `--dds_out` |

## What it does

`CrfLoader.process()` runs:

1. **Normalize the input DDS** — repairs `origin` written as a dict, `length: null`, and
   the legacy `annotatedCRF` key. If `studyName` is null (which puts the literal string
   `None` into every OID) the header is recomputed from the USDM and the OIDs rewritten.
2. **Read the SoA** — activities and encounters ordered by their `previousId`/`nextId`
   chains, epochs and timings resolved.
3. **Resolve Biomedical Concepts** — reusing the `concepts` the Define loader already
   wrote; no BC is re-fetched.
4. **Select one CRF group per concept**, in priority order: the USDM `crf` extension
   attribute, then the SDTM dataset specialization id, then the concept's own C-code.
   Ties break on `--implementation_option`, then a blank scenario, and are recorded in
   the refinement file either way.
5. **Enrich with CDASHIG** — definitions, completion instructions, implementation and
   mapping notes for whatever the specialization leaves blank.
6. **Build codelists** from CDASH CT (falling back to SDTM CT), as full lists, subsets,
   or value-list-only lists.
7. **Build items, forms and study events**, then assemble and validate.

### OID conventions

Chosen so a combined DDS has no collisions with the Define-side OIDs.

| Object | Pattern | Example |
|---|---|---|
| Form / Section / Concept | `IG.FORM.<ACTIVITY>` / `IG.SEC.<FORM>.<n>` / `IG.CON.<crf_group_id>` | `IG.FORM.VITAL-SIGNS` |
| CRF item | `IT.CRF.<crf_item>` | `IT.CRF.SYSBP_VSORRES` |
| Codelist | `CL.CDASH.<C>[.<crf_group_id>]` / `CL.CRF.<crf_group_id>.<var>` | `CL.CDASH.C66770` |
| Study event | `SE.<ENCOUNTER>` | `SE.C1D1` |
| Standards | `STD.CDASHIG`, `STD.CDASHCT` | |

## The refinement file

`--patch_file` writes a YAML file holding everything the loader could not derive:
`__PLACEHOLDER__` values, concepts that matched several CRF groups, concepts with no CRF
specialization at all, and visits with no forms bound. Fill it in and re-run with
`--apply_patch` to fold the answers back.

```yaml
forms:
  IG.FORM.VITAL-SIGNS: {label: Vital Signs, repeating: "No", sections: [IG.SEC.VITAL-SIGNS.1]}
sections:
  IG.SEC.VITAL-SIGNS.1: {label: Vital Signs, crfSectionInstructions: __PLACEHOLDER__,
                         concepts: [IG.CON.SYSBP_DENORMALIZED, IG.CON.DIABP_DENORMALIZED]}
studyEvents:
  SE.C1D1: {itemGroups: [], candidates: [IG.FORM.VITAL-SIGNS, IG.FORM.CBC]}
crfGroupChoices:
  C25298: {selected: SYSBP_DENORMALIZED, candidates: [SYSBP_DENORMALIZED, SYSBP_NORMALIZED]}
uncoveredConcepts:
  - {code: C102408, name: ECOG Performance Status, activity: ECOG PERFORMANCE STATUS}
```

Values left as `__PLACEHOLDER__` are ignored on apply, so a partly completed file is safe.
The file is regenerated on every run; answers survive because applying them removes the
placeholder first. Patches may also move concepts between sections and bind forms to
visits, which is how "one form per activity" becomes a sponsor's real layout.

**`studyEvents` is the section that matters most today.** Every SoA Workbench export seen
so far leaves `ScheduledActivityInstance.activityIds` empty, so no activity-to-visit edge
exists and every study event comes out unbound. The loader warns once and lists candidate
forms for each visit.

## Design notes

- **Branch on shape, never on `usdmVersion`.** Both known USDM producers declare 4.0.
  Specializations resolve through `loaders.common.usdm_bc.usdm_specialization_ids`, which
  reads the extension attribute first and falls back to `reference`.
- **Items are inlined per concept.** `ItemGroup.items` is `inlined_as_list` in the DDS
  model, so an item several concepts collect (`IT.CRF.VSDAT`) appears once per concept —
  as the *same object*, so a later merge is visible everywhere. The generator emits one
  `ItemDef` per OID.
- **Two definitions of one item merge rather than split**, because rows commonly differ
  only in which column a source filled in. They split into a concept-scoped OID only on a
  real disagreement: a different data type, codelist, or two questions both authored in
  the specialization. A differing *prompt* never splits an item.
- **The CDASHIG domain endpoint is `/domains/{D}`, not `/domains/{D}/fields`.** The latter
  returns only `_links` href stubs and would cost one request per field.
- **Scenario paths are discovered, not guessed** — they are published as
  `/scenarios/<DOMAIN>.<Name>` with spaces removed and inconsistent casing.

## Tests

```bash
cd src/loaders/crf && pytest
```

100 tests, no network access — the Library client is a `MagicMock` throughout. Fixtures
in `tests/fixtures/` cover the four group-selection priorities, CDASHIG class-level
fallback, codelist subsetting, form/section/concept nesting and order, timing mapping,
the empty-`activityIds` warning, patch round-tripping, and profile validation.
