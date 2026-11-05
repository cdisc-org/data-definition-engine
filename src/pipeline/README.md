# pipeline — stages A-G from the study design to define.xml and the annotated CRF

```bash
cd src
python -m pipeline --study ../data/protocols/NCT01797120/pipeline.yaml [--from A] [--to G] [--strict] [--dry-run]
```

| Stage | Program (run in) | Reads | Writes |
|---|---|---|---|
| A | `create_define_json.py` (`define-xml/`) | USDM, CDISC Library, `define-patch.yaml` | DDS1 (`dds_define`), `define-patch-stageA.yaml` |
| B | `loaders.crf.crf_loader` (`src/`) | DDS1, USDM, CRF specializations | `dds-crf.json`, `crf-refinement.yaml` |
| C | `crf_generator.py` (`generators/crf/`) | `dds-crf.json` | `crf-2.0.xml` |
| D | crfutils `crfvalidate`, `crfpdf` | `crf-2.0.xml` | `acrf.pdf` (named by the DDS annotated CRF), `acrf.pagerefs.json` |
| E | `loaders.pagerefs` (`src/`) | `dds-crf.json`, pagerefs, CRF | `dds-origin.json`, `origin-review.yaml` |
| F | `loaders.defaults` (`src/`) | `dds-origin.json`, the defaults dictionaries, `define-patch.yaml` | `dds-defaults.json`, `define-patch.yaml`, `defaults-report.yaml` |
| G | `define_generator.py` (`generators/define/`), then `defineutils.validate` | `dds-defaults.json` | `define.xml` |

- Paths in the study YAML are relative to it and made absolute, because each stage runs in its
  own folder (`define-xml/` and `generators/define/` use flat imports).
- A stage that exits non-zero stops the run. `--from`/`--to` re-run part of it, e.g.
  `--from E` after answering `origin-review.yaml`, or `--from F` after answering
  `define-patch.yaml` or editing a defaults dictionary.
- A review file that exists is applied (`--apply_patch`) and written back with what is still
  open. They sit beside the study YAML, because they hold a person's answers; everything
  generated goes to `output_dir`.
- **The define patch has one writer.** Stage A applies `define-patch.yaml` but writes its own
  full placeholder list to `output_dir/define-patch-stageA.yaml`. Stage F applies the answers
  again, fills the well-known defaults, and rewrites `define-patch.yaml` with what is still open
  plus every answered value, so answers survive the next run.
- **Defaults** come from `defaults:` in the study YAML, a list of dictionaries where later files
  win (default `data/defaults/well_known_defaults.json`). See
  [`src/loaders/defaults`](../loaders/defaults/README.md) and [`data/defaults`](../../data/defaults/README.md).
- crfutils is a separate install: `commands.crfvalidate` / `commands.crfpdf` in the YAML, or
  on `PATH`.
- The run ends with the open review items: define patch open values (each `__PLACEHOLDER__` and
  null in `define-patch.yaml`, or in stage A's list before stage F has run), CRF
  `mappingReview`, crfpdf's `sdtm_alias_disagrees` / `define_oid_unpaired`, the
  `origin-review.yaml` sections, the defaults report's `noPages`, and a define.xml that fails
  schema validation. `--strict` exits 1 while any is open. `pipeline-run.json` in `output_dir`
  records each step's command, exit code, and the sha256 of its inputs and outputs.

Stages A and B need a CDISC Library API key (`CDISC_API_KEY`, or a `.env`).

## Tests

```bash
cd src/pipeline && pytest
```

10 tests with the stages stubbed: order, working folders, absolute paths, review files
applied when present, stage A's and stage F's define patch paths, the defaults dictionaries,
a failing stage stops the run, a failed validation is an open item, `--from`/`--to`,
`--strict`, `--dry-run`.
