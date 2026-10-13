# crf_generator.py — ODM CRF and aCRF generator

Generates CRFs and annotated CRFs from a DDS JSON file, in **ODM v1.3.2** or **ODM v2.0**.

The SDTM dataset mapping annotations are **always** embedded in the ODM output, so one
file serves as both the blank CRF and the aCRF — which of the two a reader sees is a
rendering choice (`displayAnnotations`), not a different document.

Built on **odmlib 0.2.1**.

## Requirements

```bash
pip install -r requirements.txt
```

`odmlib>=0.2.1` is a hard floor. It is the first release whose `odm_2_0` model matches the
ODM 2.0 XSD (`Protocol/StudyEventGroupRef → StudyEventGroupDef/StudyEventRef`, required
`Standard/@Status` and `TranslatedText/@Type`) and whose `to_xml_string()` declares
namespaces. On 0.2.0 the ODM 2.0 output is not schema-valid.

## Running it

```bash
cd src/generators/crf

python crf_generator.py -t ../../../output/NCT01797120-dds-crf.json \
    -o ../../../output/crf-2.0.xml   --odm-version 2.0   --validate

python crf_generator.py -t ../../../output/NCT01797120-dds-crf.json \
    -o ../../../output/crf-1.3.2.xml --odm-version 1.3.2 --validate
```

It also runs as a module from `src/`: `python -m generators.crf.crf_generator ...`.

| Flag | Notes |
|---|---|
| `-t/--template` | DDS JSON file (required) |
| `-o/--odm` | output path (default `crf.xml`) |
| `--odm-version` | `1.3.2` or `2.0` (required) |
| `-v/--validate` | odmlib validation + the ODM XSD odmlib bundles |
| `--xsd` | validate against a specific XSD instead |
| `--html [dir]` | render the blank CRF and the aCRF (needs `saxonche` and a stylesheet) |
| `--stylesheet` | XSLT to use with `--html` |
| `--include-hidden` | emit items flagged `crfDisplayHidden` |
| `--forms A,B` | emit only these Form OIDs |
| `--no-prune-codelists` | keep codelists no CRF item references |
| `-l/--log-level` | log file `crf_generator.log` |

## Architecture

`CrfGenerator.create()` mirrors `DefineGenerator.create()`: load JSON → initialize the
shared `crf_objects` dict of lists → dispatch each DDS section through the `LOADERS`
registry in `SECTION_ORDER` → post-process → assemble → write.

The difference is `targets/`. Every structural difference between the two ODM versions
lives behind the `OdmTarget` surface, so the loader classes are written once:

| | ODM 1.3.2 | ODM 2.0 |
|---|---|---|
| Form | `FormDef` | `ItemGroupDef @Type="Form"` |
| Section | **flattened** — an `Alias Context=section` on each Concept, plus `Alias Context=sectionOrder` on the Form | `ItemGroupDef @Type="Section"` |
| Concept | `ItemGroupDef` | `ItemGroupDef @Type="Concept"` |
| Prompt, definition, instructions, notes | `Alias` with the matching context | native `Prompt`, `Definition`, `CRFCompletionInstructions`, `ImplementationNotes`, `CDISCNotes` |
| Provenance | `Alias Context=BC / SDTMSpecialization / CRFSpecialization` | `Coding` |
| Units | `MeasurementUnitRef` + `BasicDefinitions/MeasurementUnit` | `ItemRef/@UnitsItemOID` |
| Visits reach forms via | `Protocol/StudyEventRef → StudyEventDef/FormRef` | `Protocol/StudyEventGroupRef → StudyEventGroupDef/StudyEventRef → StudyEventDef/ItemGroupRef` |
| Standards | `Protocol/Alias Context=Standard` | native `Standards/Standard`, plus an alias for names the XSD forbids |

### Alias context vocabulary

One contract for both emitters and both stylesheets:

`SDTM`, `CDASH`, `prompt`, `definition`, `completionInstructions`, `implementationNotes`,
`cdiscNotes`, `mappingInstructions`, `preSpecifiedValue`, `selectionType`, `subsetOf`,
`timing`, `section`, `sectionOrder`, `BC`, `SDTMSpecialization`, `CRFSpecialization`,
`USDM`, `nci:ExtCodeID`, `Standard`.

The Phase 1 POC contexts `formAnnotation`, `formSectionAnnotation` and
`formSectionCompletionInstruction` are retired in favour of `SDTM` on the form and
`completionInstructions` on the section.

## Things that will bite you

Three odmlib behaviours this package works around. All are pinned by tests.

**The namespace registry is process-global and the last model import wins.** Importing
both `odm_1_3_2` and `odm_2_0` — which a dual-version generator must — leaves whichever
was imported second owning the `odm` prefix, so an ODM 2.0 document silently serializes in
the 1.3.2 namespace and fails schema validation. `OdmTarget.bind_namespaces()` re-registers
the URI it means before every serialization.

**`getattr` on an unset list-valued child mutates the document.** odmlib materializes the
empty list *at the end* of the object's `__dict__`, and element order is derived from that
dict — so a read-only inspection pass like `getattr(event, "ItemGroupRef", None)` makes
`validate()` fail with an element-order error. Use `post_processing.peek()`, which reads
`vars()` and cannot create anything.

**`Leaf/@xlink:href` is emitted without `xmlns:xlink`.** The result is not well-formed
XML. `OdmTarget.to_xml_string()` repairs the declaration; see `FIXES.md` at the repository
root.

## Known gaps

- **Stylesheets are not here yet.** `--html` and `render.py` are wired up, but the two
  XSLT 2.0 stylesheets are milestone M6. Until they land, `--html` needs `--stylesheet`
  pointing at your own. The ODM output is the deliverable; the HTML is a view of it.
- **`CrfObject` duplicates ~40 lines of `define_object.DefineObject`.** Extracting a
  shared base would mean converting the Define generator away from flat top-level imports
  (`import items`), which is out of scope. Unlike that package, this one is a real Python
  package with absolute imports and needs no working-directory juggling.

## Tests

```bash
cd src/generators/crf && pytest
```

70 tests over `tests/fixtures/dds-360i-crf.json`, a trimmed real combined DDS (two forms,
three visits, one Define-side tabulation dataset). They assert the structure and native
elements of both versions, the 1.3.2 flattening and measurement units, XSD validity of
both outputs, namespace isolation when both are built in one process, and — in
`test_coexistence.py` — that the Define generator reading the same file emits identical
dataset content and no CRF OIDs.
