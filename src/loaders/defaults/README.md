# loaders/defaults — Stage F: well-known defaults for the values no other loader supplied

An enrichment loader (DDS in, DDS out), run after the pagerefs loader and before the Define
generator. It fills the values that are still unfilled once every other source has had its turn
from a **dictionary of well-known defaults**: STUDYID is Protocol/Sponsor, --SEQ is Derived/Sponsor
with length 3, --TESTCD has at most 8 characters. Content another loader wrote is never changed.
It then rewrites `define-patch.yaml` so the file lists only what is still open.

The define.xml at this stage is a **specification**, built from the study design before any data
exist, and it can help drive the SDTM programming. The defaults are specification values: a
length is an estimate of the room a variable needs. When the study is complete, the sponsor sets
each length to the longest value in the data for the submission. The dictionary belongs to the
sponsor; see [`data/defaults/README.md`](../../../data/defaults/README.md).

## Running it

From `src/`:

```bash
python -m loaders.defaults \
  --dds_in  ../output/NCT01797120/dds-origin.json \
  --dds_out ../output/NCT01797120/dds-defaults.json \
  --defaults ../data/defaults/well_known_defaults.json [study-defaults.json ...] \
  --patch_file ../data/protocols/NCT01797120/define-patch.yaml \
  --report ../output/NCT01797120/defaults-report.yaml [--validate]
```

| Option | Purpose |
|---|---|
| `--dds_in`, `--dds_out` | The pagerefs loader's DDS and the DDS to write. They must differ, so a re-run starts from the same input. |
| `--defaults` | One or more dictionaries; later files win. Default: `data/defaults/well_known_defaults.json`. |
| `--patch_file` | The `define-patch.yaml`: its answers are applied, then it is rewritten with what is still open plus every answered value. |
| `--report` | The `defaults-report.yaml` to write. |
| `--validate` | Validate the output against the CRF profile JSON Schema. |

The pipeline (`src/pipeline`) runs it as stage F. A dictionary that fails its schema stops the
run with exit 1, and nothing is written.

## The dictionary

A JSON file validated by [`schemas/defaults/defaults.schema.json`](../../../schemas/defaults/defaults.schema.json),
with one section per kind of DDS object, because a name alone is ambiguous: a CRF item and a
Define item are both an `ItemDef` and often share a name (AETERM), with different lengths.

| Section | DDS objects | Allowed `values` |
|---|---|---|
| `items` | Define items: tabulation itemGroups' `items` and their `ValueList` slices' items | `dataType`, `length`, `significantDigits`, `displayFormat`, `origin` |
| `itemGroups` | tabulation itemGroups | `keySequence`, `structure`, `purpose`, `description` |
| `crfItems` | items in the Form's `Concept` slices | `dataType`, `length`, `origin`, `question`, `prompt`, `crfCompletionInstructions` |
| `crfSections` | the Form's `Section` slices | `crfSectionInstructions` |

```json
{ "name": "--DTC", "domains": ["SE", "SV"], "description": "Convention: SE and SV are derived.",
  "values": { "origin": [{ "type": "Derived", "source": "Sponsor" }] } }
```

- `name` is the object's name; `--SEQ` matches any longer name ending in `SEQ`; `*` matches every
  object in the datasets `domains` lists (the schema requires `domains` with it).
- `domains` / `excludeDomains` limit an entry to datasets (a CRF object's dataset is its Form's
  `domain`).
- `length` is an integer or `{"lengthOf": "studyName", "plus": 9}`: the length of a DDS study-level
  string (`studyName` or `protocolName`) plus a constant. The seed uses it for STUDYID and USUBJID.
- Two entries in one section of one file with the same name and domain filters are an error, and
  so is an unknown `schemaVersion` major version.

## Which values it fills

For each object:

1. an answer in `define-patch.yaml` for its OID (Stage A applied the earlier ones; this catches
   answers given since, so `--from F` is enough after answering);
2. the dictionary entries that apply, best first: an exact name, then a longer suffix before a
   shorter one, then `*`; at equal rank an entry with domain filters, then a later file. Each field
   takes its value from the best entry that sets it, and falls through to the next one otherwise
   (LBSCAT: length from `--SCAT`, origin from `--CAT`).

Rules:

- **Only unfilled values**: missing, null, `""` or `__PLACEHOLDER__`. An origin is unfilled only
  when an entry's type or source is `__PLACEHOLDER__`; a missing origin is left alone, because the
  pagerefs loader removes a value-list parent's origin on purpose.
- An origin whose type is a placeholder is replaced with the default's. One with a real type and a
  placeholder source takes the source the default gives that type, and keeps its pages.
- `length` goes only on text, integer and float items; `significantDigits` only on float ones.
- An entry whose `dataType` differs from the item's real dataType contributes no `dataType`,
  `length`, `significantDigits` or `displayFormat` (reported as a conflict); its origin still applies.
- A Collected/Investigator origin filled without aCRF pages is reported under `noPages`: the Define
  generator writes `PageRefs="__PLACEHOLDER__"` for it. Each Derived origin gets a MethodDef
  placeholder from the Define generator's post-processing.

## define-patch.yaml

Stage A applies the define patch but, in the pipeline, writes its full placeholder list to
`output_dir/define-patch-stageA.yaml`. Stage F applies the answers again (to values still
unfilled), fills the defaults, and rewrites the define patch beside `pipeline.yaml` in Stage A's
format, so Stage A's `--apply_patch` keeps reading it. The rewritten file lists what is still open
and carries every answered value, so answers survive the next run; answers for OIDs the DDS no
longer has are dropped. Two differences from Stage A's list: `length` is listed only for text,
integer and float items, and `standard` is not listed when the group has a `standardOID`. The
shared code is `loaders/common/define_patch.py`.

## defaults-report.yaml

Generated on every run; nothing in it needs an answer.

| Section | Lists |
|---|---|
| `applied` | each OID with, for every field filled, its source: the dictionary entry and file, or `answer` |
| `conflicts` | entries whose dataType differs from the item's |
| `noPages` | Collected/Investigator origins filled without aCRF pages |
| `unmatched` | entries that matched nothing: a typo, or content this study does not have |
| `remainingCrf` | CRF fields still `__PLACEHOLDER__` (`crf-refinement.yaml` belongs to stage B) |

CRF defaults reach `dds-defaults.json` but not `crf-2.0.xml` or `acrf.pdf`, which stages C and D
rendered earlier.

## Tests

```bash
cd src/loaders/defaults && pytest
```

58 tests, no network: the schema and the seed, duplicates, the ranking, the fill rules, origins,
computed lengths, the four sections, define-patch answers and the rewritten patch, an identical
second run, that the seed changes only unfilled values in a committed combined DDS, and the command.
