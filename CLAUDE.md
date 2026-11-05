# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project purpose

The Data Definition Engine (DDE) is part of the CDISC 360i program. It populates the Data Definition Specification (DDS) JSON model with study metadata, then uses that model to generate study artifacts (Define-XML v2.1, ODM CRFs, Dataset-JSON shells, Trial Design datasets). The architecture is **loaders → DDS JSON → generators**: the DDS JSON file is the contract between the two halves of the system.

## Repository layout

Six programs live in `src/` — four loaders and two generators — plus the driver that runs them in order:

- `src/define-xml/` — **Define loader**. `create_define_json.py` reads a USDM JSON study design, calls the CDISC Library API for Biomedical Concepts and Dataset Specializations, and writes a Define-JSON file. Validation is against `define.yaml` (a LinkML/YAML schema). Unique structural feature: variable-level metadata is stored as `slices` *inside* each itemGroup, rather than as separate `DataSpecialization` itemGroups.
- `src/loaders/crf/` — **CRF loader**. `crf_loader.py` is an *enrichment* loader: DDS in → DDS out. It reads the Define DDS plus the USDM, resolves each Biomedical Concept to a CRF Specialization, enriches it from CDASHIG and CDASH CT, and writes a **combined DDS** carrying both Define-XML and CRF metadata. Shared utilities live in `src/loaders/common/`.
- `src/loaders/pagerefs/` — **Pagerefs loader** (Stage E). Another enrichment loader: it reads the `acrf.pagerefs.json` crfutils `crfpdf` writes beside the annotated CRF and writes each Define item's `origin` with its aCRF pages (`origin[].documents[].pages`). It refuses a pagerefs file that does not belong to its DDS and CRF (crf sha256, header OIDs, PDF name) and writes `origin-review.yaml`.
- `src/loaders/defaults/` — **Defaults loader** (Stage F). The last enrichment loader: it fills what is still unfilled from a dictionary of well-known defaults (`data/defaults/well_known_defaults.json`, schema `schemas/defaults/defaults.schema.json`; sponsor-editable, later files win), never changes a value another loader wrote, rewrites `define-patch.yaml` with what is still open plus every answered value, and writes `defaults-report.yaml`.
- `src/pipeline/` — **the driver**. `python -m pipeline --study data/protocols/<study>/pipeline.yaml` runs stages A (Define loader) → B (CRF loader) → C (CRF generator) → D (crfutils crfvalidate/crfpdf) → E (pagerefs loader) → F (defaults loader) → G (Define generator + defineutils), each as a subprocess in its own folder, and ends with the open review items (`--strict` fails while any is open).
- `src/generators/define/` — **Define generator**. `define_generator.py` reads a DDS JSON file and emits Define-XML v2.1 using `odmlib`.
- `src/generators/crf/` — **CRF generator**. `crf_generator.py` reads a DDS JSON file and emits ODM v1.3.2 or v2.0 CRFs. SDTM mapping annotations are always embedded, so one file is both the blank CRF and the aCRF; which you see is a rendering choice, not a different document. Requires **odmlib >= 0.2.1**.

Each has an **independent `requirements.txt`** and is run from its own directory.

The **combined DDS is the contract**: each generator reads the whole file and ignores the sections it does not own. The Define generator skips `Form`/`Section`/`Concept` item groups and `studyEvents`; the CRF generator skips tabulation datasets, conditions, whereClauses and methods.

Import style differs between the older and newer packages, and this matters when running them. `src/define-xml/` and `src/generators/define/` use **flat top-level imports** (`import items`) and only work with their own directory as the working directory. `src/loaders/` and `src/generators/crf/` are **real packages** with absolute imports; their entry points put `src/` on `sys.path`, so they run either as a script from their own directory or as `python -m loaders.crf.crf_loader` from `src/`.

## Common commands

### Generator (`src/generators/define/`)

```bash
# Run the generator
python define_generator.py -t ./tests/fixtures/define-360i.json -d ./tests/fixtures/define-360i.xml

# Generate and schema-validate in one step
python define_generator.py -t ./tests/fixtures/define-360i.json -d out.xml --validate

# Run all tests (pytest config in pytest.ini, testpaths=tests)
cd src/generators/define && pytest

# Run a single test
cd src/generators/define && pytest tests/test_define_generator.py::TestDefineGeneratorIntegration::test_generate_xml_from_main_sample

# Validate Define-XML output externally
python3 -m defineutils.validate -d define-360i.xml
xmllint --schema ~/src/schemas/DefineV219/schema/cdisc-define-2.1/define2-1-0.xsd ./tests/fixtures/define-360i.xml --noout
```

Tests `chdir` to `src/generators/define/` because the package uses **flat top-level imports** (`import items`, `import codeLists`, ...) rather than package-relative imports — running pytest from any other directory will fail to import.

### CRF generator (`src/generators/crf/`)

```bash
cd src/generators/crf

# ODM 2.0 and ODM 1.3.2 from the same combined DDS
python crf_generator.py -t ../../../output/NCT01797120-dds-crf.json \
    -o ../../../output/crf-2.0.xml   --odm-version 2.0   --validate
python crf_generator.py -t ../../../output/NCT01797120-dds-crf.json \
    -o ../../../output/crf-1.3.2.xml --odm-version 1.3.2 --validate

cd src/generators/crf && pytest        # 77 tests

# Independent schema check against the vendored XSDs
xmllint --noout --schema schemas/odm/2.0/ODM.xsd        output/crf-2.0.xml
xmllint --noout --schema schemas/odm/1.3.2/ODM1-3-2.xsd output/crf-1.3.2.xml
```

`--validate` runs odmlib validation (element order, OID integrity, conformance) *and* the ODM XSD that odmlib bundles — they catch different classes of defect, so both run.

### CRF loader (`src/loaders/crf/`)

Requires `CDISC_API_KEY`. Runs *after* `create_define_json.py`, taking its output as input.

```bash
cd src/loaders/crf

python crf_loader.py \
  --dds_in   ../../../output/NCT01797120-dds.json \
  --usdm_file ../../../data/protocols/NCT01797120/NCT01797120-latest.json \
  --dds_out  ../../../output/NCT01797120-dds-crf.json \
  --crf_spec_file ../../../data/crf_specializations/cdisc_crf_specializations_draft.csv \
  --cdashig 2.3 --cdashct 2026-03-27 \
  --patch_file ../../../output/crf-refinement.yaml --validate --debug

cd src/loaders/crf && pytest           # 147 tests, no network
```

Library responses are cached on disk under `.cache/cdisc_library/` (`--no_cache` to bypass), which makes the refinement loop free after the first run.

### Pipeline (`src/pipeline/`), pagerefs loader (`src/loaders/pagerefs/`) and defaults loader (`src/loaders/defaults/`)

```bash
cd src
python -m pipeline --study ../data/protocols/NCT01797120/pipeline.yaml            # stages A-G
python -m pipeline --study ../data/protocols/NCT01797120/pipeline.yaml --from E   # after answering origin-review.yaml
python -m pipeline --study ../data/protocols/NCT01797120/pipeline.yaml --from F   # after answering define-patch.yaml or editing a defaults dictionary
python -m loaders.defaults --dds_in ../output/NCT01797120/dds-origin.json --dds_out /tmp/dds-defaults.json \
    --report /tmp/defaults-report.yaml   # standalone; add --patch_file to rewrite a define patch
cd src/pipeline && pytest           # 10 tests, stages stubbed
cd src/loaders/pagerefs && pytest   # 22 tests, no network
cd src/loaders/defaults && pytest   # 58 tests, no network
```

Stage D needs crfutils (`crfvalidate`, `crfpdf`) on `PATH` or named under `commands:` in the study YAML. The review files (`define-patch.yaml`, `crf-refinement.yaml`, `origin-review.yaml`) sit beside the study YAML; generated files go to `output_dir`. The define patch has one writer: stage A applies it but writes its full list to `output_dir/define-patch-stageA.yaml`, and stage F rewrites it. `defaults:` in the study YAML lists the defaults dictionaries (default: the shared one).

### Loader (`src/define-xml/`)

Requires `CDISC_API_KEY` (env var, `.env` file, or `--cdisc_api_key`).

```bash
python create_define_json.py \
  --usdm_file ../../data/protocols/NCT01797120/NCT01797120-latest.json \
  --output_template define.json \
  --sdtmct 2025-09-26 \
  --validate --validation_report validation_report.xlsx
```

`--debug` writes intermediate dictionaries (`debug_*.json`) to the working directory. They are the fastest way to tell a USDM parsing miss from a CDISC Library miss: an empty `debug_bc_dict.json` or `debug_test_dict.json` alongside a large `debug_dataset_data.json` means specializations were fetched but no value-level metadata was derived from them.

Note the loader uses **jmespath**, not JSONata — only four expressions, all inline in `_extract_usdm_data()` and `populate_study_elements()`. Everything else is hand-chained `dict.get()` traversal.

## Loader architecture

`USDMDefineJSONProcessor.process()` runs: `process_biomedical_concepts` → `build_vlm_lookup` → `update_datasets_dict` → `_build_global_codelist_terms` → `populate_study_elements` → `process_datasets` → `_update_subset_codelist_names` → `add_standards` → `save_output`.

### USDM producer differences

The loader must accept USDM 4.0 from more than one producing tool, and **the `usdmVersion` field does not distinguish them** — both known producers declare 4.0. Branch on the *shape* of the data, never on the version.

The two producers seen so far:

| | CDISC USDM E2J | SoA Workbench |
|---|---|---|
| Dataset specialization | in `BiomedicalConcept.reference`, package-dated | in an `extensionAttributes` entry (`url` = `SDTM_SPECIALIZATION_EXT_URL`), no package date |
| `xxTESTCD` discriminator | listed as a BC property (177/209) | never listed as a BC property (0/84) |
| Study Acronym title | present | absent — only Official Study Title |
| Timeline label | literally `"Main Timeline"` | study-specific; use the `mainTimeline` flag |

Three rules follow, and breaking any of them silently produces a structurally valid but hollow Define-JSON rather than an error:

1. **Resolve specializations through `_usdm_dataset_specialization_ids()`**, which reads the extension attribute first and falls back to `reference`. Only when it returns nothing does the CDISC Library get asked — and that fallback fans out to *every* specialization of the concept, which is why it must stay a fallback rather than the default path.
2. **Drive `_build_where_clause()` from the specialization's `comparator` variables, not from BC properties.** The specialization is the authority on what discriminates a value list. Iterating BC properties drops `WHERE xxTESTCD EQ ...` for any producer that omits the discriminator, leaving value lists keyed on their qualifier variables — output that looks complete and is wrong.
3. **Never assume a field the USDM merely *usually* fills.** `studyType`, `studyPhase`, `blindingSchema`, `plannedAge`, and `plannedEnrollmentNumber` are all `null` in SoA Workbench exports; `eligibilityCriteria`, `characteristics`, `administrations`, and `dictionaries` are all empty. Absent a Study Acronym title, `populate_study_elements()` falls back to `study.name`, then the first study identifier, then `"STUDY"` — without it the literal string `None` is interpolated into every OID.

## Defaults loader architecture

`DefaultsLoader.process()` (`src/loaders/defaults/defaults_loader.py`) applies `define-patch.yaml` answers to values still unfilled → fills each tabulation itemGroup, Define item (variable and value level), CRF Section and CRF item from the dictionary → collects what is still open. The define.xml it feeds is a **specification** made before any data exist, so the defaults are specification values (lengths are estimates the sponsor sets from the data at submission); the seed's entries each state their basis in `description`.

- **Only unfilled values change**: missing, null, `""` or `__PLACEHOLDER__`. An origin counts as unfilled only when an entry's type or source is `__PLACEHOLDER__`; a missing origin is never filled, because the pagerefs loader removes a value-list parent's origin on purpose. `length` goes only on text/integer/float items, `significantDigits` only on float, and an entry whose `dataType` disagrees with a real one contributes no type-dependent field (a reported conflict).
- **The dictionary has one section per kind of object** (`items`, `itemGroups`, `crfItems`, `crfSections`): Define-XML and ODM both call items `ItemDef`, and 33 NCT01797120 CRF item names are also Define item names. Names are exact, a suffix (`--SEQ`), or `*` (which needs `domains`). Ranking (`dictionary.py`): exact > longer suffix > shorter suffix > `*`; then domain-filtered; then later file. Each field cascades to the next entry that sets it.
- **`loaders/common/define_patch.py`** reads, applies, collects and writes the define patch in Stage A's format, so Stage A's `--apply_patch` reads the rewritten file. It lists `length` only for text/integer/float items and skips `standard` when `standardOID` is set (both differ from Stage A, see `FIXES.md` §6.2). Answered values are carried over; answers for OIDs no longer in the DDS are dropped.
- Each Derived origin it fills gets a MethodDef placeholder from the Define generator, and a Collected/Investigator origin without aCRF pages is reported under `noPages` (the generator writes a page placeholder for it). CRF defaults land in `dds-defaults.json` but not in the CRF, which stage C rendered earlier.

## Generator architecture

`DefineGenerator.create()` runs a fixed pipeline:

1. **Load JSON** — fail fast with `sys.exit(1)` on `JSONDecodeError`.
2. **Initialize `define_objects`** — a dict of lists, one per Define-XML element type (`ItemDef`, `ItemGroupDef`, `CodeList`, `MethodDef`, `WhereClauseDef`, `ValueListDef`, `CommentDef`, `leaf`). Every loader writes into this shared dict.
3. **Dispatch sections to loaders** via the `LOADERS` registry in `define_generator.py`, in `SECTION_ORDER`. Each top-level list in the DDS JSON (`itemGroups`, `conditions`, `whereClauses`, `codeLists`, `methods`, `standards`, `annotatedCRFs`, `concepts`, `conceptProperties`, `dictionaries`, `comments`, `documents`) maps to a loader class. Study-level scalars are not dispatched: `study.Study` receives the *whole* template dict and writes `define_objects["Study"]` and `["MetaDataVersion"]`. Adding a new section means adding both a loader class and a `LOADERS` entry.
4. **Post-process** — `post_processing.PostProcessing` walks finished `define_objects` to add cross-cutting content. Currently it auto-creates `MethodDef` placeholders and wires `MethodOID` onto `ItemRef`s for any `ItemDef` whose `Origin.Type == "Derived"`.
5. **Build the odmlib document tree** — `_build_doc()` assembles `ODM → Study → MetaDataVersion`, attaches Standards, AnnotatedCRF, and appends each element list under `MetaDataVersion`.
6. **Write XML** via `odm.write_xml()`.

### Loader contract

All loader classes inherit from `define_object.DefineObject` (in `define_object.py`) and expose:

```python
def create_define_objects(self, template, define_objects, lang, acrf) -> None
```

`DefineObject` provides shared helpers: `require_key()` (raise `ValueError` with context for missing JSON keys), `generate_oid()` (joins descriptors with `.`, uppercases, replaces spaces with `-`), `find_object()`, and `create_external_codelist()`. Use these instead of re-implementing — error messages and OID conventions must stay consistent.

`ItemGroups` is the most complex loader: it owns the `slices` extension. For each dataset it creates an `ItemGroupDef`, delegates to `ItemRefs` and `Items` for variable details, and if the dataset has `slices` of type `ValueList`, hands them to `valueLevel.ValueLevel` to emit `ValueListDef` + `WhereClauseDef`. Domain behavior is data-driven from `constants.py` (`TRIAL_DESIGN_DOMAINS`, `NON_REPEATING_DOMAINS`).

### When the JSON model and generator drift

Both `define.yaml` (loader's schema) and the generator's loader classes encode assumptions about the DDS JSON shape. When the DDS model changes, both sides must move together — `README.md` notes the model "is still evolving." Validate generator changes against `tests/fixtures/define-360i.json` (the canonical fixture) and re-run the integration tests in `tests/test_define_generator.py`.

**The known drift cases are closed (2026-10-24)**: the current Define loader writes a real `studyName`; `concepts`/`conceptProperties` are ReifiedConcept/ConceptProperty per the DDS schema, and the generator's loaders skip them (a legacy dictionary-shaped entry still becomes an external CodeList); a combined DDS's CDASHIG standard is skipped because Define-XML 2.1 has no `Standard/@Name` for it (`constants.DEFINE_STANDARD_NAMES`). `tests/test_combined_dds.py` pins this. A combined DDS still carries placeholders (`Length`, `Origin`) until the define patch is answered, so its define.xml fails XSD validation until then. See `FIXES.md` §2.2.

**Origin pages** come from `origin[].documents[].pages` (integers; the pagerefs loader writes them): one contiguous run becomes `FirstPage`/`LastPage`, otherwise space-separated `PageRefs`. The `__PLACEHOLDER__` `PDFPageRef` is written only for a Collected/Investigator origin with no pages. Every `def:DocumentRef` uses the DDS `annotatedCRFs[0].leafID`.

## CRF architecture

### Loader (`crf_loader.py`)

`CrfLoader.process()` runs: normalize the input DDS → read the SoA → resolve Biomedical Concepts → select one CRF group per concept → build forms/items/codelists → build study events → assemble → validate.

Three things to know before changing it:

- **Group selection is a priority chain**, not a lookup: the USDM `crf` extension attribute, then the SDTM dataset specialization id, then the concept's C-code. Ties break on `--implementation_option` and are always recorded in the refinement file.
- **Items are inlined per concept and shared by object identity.** `ItemGroup.items` is `inlined_as_list` in the DDS model, so an item several concepts collect appears once per concept — as the *same dict*, so a later merge is visible from all of them. Two definitions of one OID merge rather than split; they split into a concept-scoped OID only on a real disagreement (different data type, codelist, prefilled value, Define links, or two questions both authored in the specialization). A differing *prompt* never splits an item.
- **Every SDTM target is linked to a Define item** (`builders/sdtm_links.py`, built from the input DDS before any CRF group is added): `crfSdtmTarget.links` (value-level by the concept's specialization id, then by where clause with "admits" semantics — EQ equal, IN listed, NE different), `crfSdtmTarget.mapping`, CDASHIG corrections (AESTDAT -> AESTDTC), and Concept `aliases` for the concept's fixed values. What cannot be linked goes to the refinement file's `mappingReview`. Stage B never creates Define items: a CRF variable the Define lacks (the Define loader only knows the dataset specializations' variables, so LBNAM, LBCLSIG, LBSCAT, MHSTRF... are missing for NCT01797120) is a review entry, not a new ItemDef.
- **Every SoA Workbench export so far has empty `activityIds`**, so no activity↔visit edge exists and every StudyEvent comes out unbound. The loader warns once and lists candidate forms per visit in the refinement YAML. Do not treat unbound events as a bug in the loader.

### Generator (`crf_generator.py`)

Mirrors `DefineGenerator.create()` — `LOADERS` + `SECTION_ORDER` + post-processing + assemble — with one addition: **`targets/`**. Every difference between ODM 1.3.2 and 2.0 lives behind the `OdmTarget` surface, so loader classes are written once. The largest is that 1.3.2 has no Section level: the tree is flattened and the section survives as `Alias Context=section`, with `Alias Context=sectionOrder` on the form.

Three odmlib behaviours the package works around, all pinned by tests — read `src/generators/crf/README.md` before touching serialization:

1. **The namespace registry is process-global and the last model import wins.** A generator that can emit both versions must re-register the URI it means before serializing, or ODM 2.0 output silently carries the 1.3.2 namespace.
2. **`getattr` on an unset list-valued odmlib child mutates element order** — it materializes the empty list at the end of `__dict__`, and order derives from that dict. Use `post_processing.peek()` for any read-only inspection.
3. **`Leaf/@xlink:href` is emitted without `xmlns:xlink`**, so the document is not well-formed until `OdmTarget.to_xml_string()` repairs it.

ODM 2.0's `Standard/@Name` enumeration has no `CDASHIG` value, so the CDASHIG standard is emitted as `Protocol/Alias Context=Standard` in both versions rather than as a native `Standard` element. `MetaDataVersion` has no `Alias` in either version; `Protocol` does.

`CodeList/@DataType` is a closed set per version (2.0: integer, decimal, text, string; 1.3.2: integer, float, text, string) and every DDS codelist — Define-side ones too — is built before pruning, so the Define loader's `float` is mapped (`constants.CODELIST_DATATYPE_20/_132`). Items emit `SDTMItemOIDs` (space-separated `DATASET.VARIABLE=OID`) and `SDTMMappingType` aliases from `crfSdtmTarget.links`/`.mapping`; `targets/base.require_unique_alias_contexts` fails on an element with two Aliases of one Context (XSD UC-ID-1/UC-IGD-4). A study event's form reference carries the form's own `mandatory`.

## For Planning and Research

For research and codebase exploration, use parallel Explore subagents by default.

## Reference docs

- `documents/Solution_Overview.md` — full architecture diagram (loaders/DDS/generators) and rationale.
- `documents/glossary.md` — CDISC and DDE terminology.
- `src/generators/define/README.md`, `src/define-xml/README.md`, `src/loaders/crf/README.md`, `src/generators/crf/README.md` — per-program usage notes.
- `DEFAULT_METADATA_LOADER.md` — the defaults loader plan: decisions, dictionary format, the seed tables with each entry's basis, and what it leaves for a person.
- `data/defaults/README.md`, `src/loaders/defaults/README.md` — the defaults dictionary (provenance, how to change it) and the loader.
- `FIXES.md` — issues found while implementing CRF generation: what was fixed, what is pre-existing and still open (including the loader/generator drift above), and what to report upstream to odmlib and the CDISC ODM team.
- `CRF_GEN_PLAN.md` — the CRF generation plan (milestones, DDS model additions, mapping tables). M0 and M2–M5 are implemented; M1 (upstream DDS PRs) and M6 (XSLT stylesheets) are not.
- `schemas/dds/profiles/crf/README.md` — the CRF profile: why the hand-written JSON Schema is what `--validate` uses today, and what unblocks the LinkML one.
- `data/crf_specializations/PROVENANCE.md` — where the draft CRF Specializations CSV came from and its known coverage gaps.
- `data/README.md` — which protocol files exist, their USDM version, and the producing tool.
- `README.md` — links to related external repos (DDS model definition, USDM loader origins, CRF generators, project wiki).
