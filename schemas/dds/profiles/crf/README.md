# DDS CRF Profile

Validation schema for a DDS instance carrying CRF metadata — the authoring contract for
`crf_loader.py` and the validation overlay for `crf_generator.py`.

## Two files, two different roles

| File | Role | Usable today |
|---|---|---|
| `crf.schema.json` | what `crf_loader.py --validate` actually runs | **yes** |
| `profile.yaml` | the LinkML differential to upstream into DataExchange-DDS | not yet — see below |

### `crf.schema.json` — hand-written and self-contained

A JSON Schema (2020-12) that constrains the CRF-owned content and tolerates the
Define-XML content sharing the same instance, so a **combined** DDS validates without
being stripped first. It is deliberately not generated: it has no dependency on a
DataExchange-DDS release, so `--validate` works now.

What it enforces: OID patterns per group type (`IG.FORM.`/`IG.SEC.`/`IG.CON.`, `IT.CRF.`,
`CL.`, `SE.`), required attributes on each CRF group type, `repeating` from the ODM value
set, the CRF data-type and origin subsets, that every item shows a question or a prompt,
that study events reference only Form OIDs, and that a CDASHIG standard is present.

### `profile.yaml` — the upstream differential, blocked on PR-DDS-1

Authored against `dds.yaml` **plus** the base-model additions listed as PR-DDS-1 in
`CRF_GEN_PLAN.md` §3.1, which have not landed upstream. It relies on slots and enum values
that do not exist in the current `DataExchange-DDS/model/dds.yaml`:

```
IsODMItem.question, .prompt, .definition, .mappingInstructions, .unitsItem
ItemGroup.repeating
Alias class, Labelled.aliases widening
ItemGroupType permissible value  Concept
StandardName permissible value   CDASHIG
StudyEvent class + MetaDataVersion.studyEvents, StudyEventType enum
```

A LinkML profile may only **tighten** a base model, never add to it, so this file cannot
be snapshotted or used to generate a JSON Schema until PR-DDS-1 merges. It is committed
here as the authoring record and as the thing to open upstream.

Once PR-DDS-1 lands, in `~/src/DataExchange-DDS`:

```bash
python profiles/dds_profile_snapshot.py --base model/dds.yaml \
    --differential profiles/crf/profile.yaml --output profiles/crf/snapshot.yaml
gen-json-schema --closed --top-class MetaDataVersion \
    profiles/crf/snapshot.yaml > profiles/crf/crf.schema.json
```

and the generated schema replaces the hand-written one here.

## Why these files live in the DDE for now

`schemas/dds/dds.yaml` is a **generated mirror** — DataExchange-DDS copies `model/dds.yaml`
into it via the `copy-define.yml` GitHub Action, and profiles are not part of that copy.
These two files were authored here so the CRF work is not blocked on an upstream release.
When PR-DDS-1 and the CRF profile merge upstream, extend that action to copy
`profiles/*/snapshot.yaml` and `profiles/*/*.schema.json` into `schemas/dds/profiles/`, and
delete the local copies.

## Extension slots

Slots annotated `dds.profile.extension: true` in `profile.yaml` are CRF-specific
additions, not part of the base model:

`crfSpecializationRef`, `crfImplementationOption`, `crfScenario`, `crfSectionInstructions`,
`crfActivityRef`, `crfRenderingHint` (on ItemGroup); `crfSelectionType`, `crfDisplayHidden`,
`crfDerived`, `crfPrepopulatedCoding`, `crfSdtmTarget` (on Item); `crfEncounterRef`
(on StudyEvent).

## Validating a combined Define-XML + CRF instance

Each profile's generated schema is closed, so neither validates a combined instance
directly. The rule is **strip-and-validate**: validate against each profile after removing
the *other* profile's extension slots. There is no union profile.

`loaders.common.profiles` implements it:

```python
from loaders.common.profiles import (profile_extension_slots, strip_extensions,
                                     validate_against_profile)

errors = validate_against_profile(instance, "crf.schema.json")
stripped = strip_extensions(instance, profile_extension_slots("profile.yaml"))
```

The hand-written `crf.schema.json` is open enough that stripping is not required for it
today; the helper exists because the generated, closed schema will require it.

The two profiles' constraints on shared classes are designed to be compatible: CRF groups
keep the `IG.` prefix, CRF items keep `IT.`, carry `mandatory`, a Define-compatible
`dataType`, and `origin.type`/`origin.source`, and add no range checks.
