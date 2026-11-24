# pipeline — stages A-H from the study design to define.xml and the annotated CRF

```bash
cd src
python -m pipeline --study ../data/protocols/NCT01797120/pipeline.yaml [--from A] [--to H] [--strict] [--dry-run]
```

| Stage | Program (run in) | Reads | Writes |
|---|---|---|---|
| A | `create_define_json.py` (`define-xml/`) | USDM, CDISC Library, `define-patch.yaml` | DDS1 (`dds_define`), `define-patch-stageA.yaml` |
| B | `loaders.crf.crf_loader` (`src/`) | DDS1, USDM, CRF specializations | `dds-crf.json`, `crf-refinement.yaml` |
| C | `crf_generator.py` (`generators/crf/`) | `dds-crf.json` | `crf-2.0.xml` |
| D | crfutils `crfvalidate`, `crfpdf` | `crf-2.0.xml` | `acrf.pdf` (named by the DDS annotated CRF), `acrf.pagerefs.json` |
| E | `loaders.pagerefs` (`src/`) | `dds-crf.json`, pagerefs, CRF | `dds-origin.json`, `origin-review.yaml` |
| F | `loaders.defaults` (`src/`) | `dds-origin.json`, the defaults dictionaries, `define-patch.yaml` | `dds-defaults.json`, `defaults-report.yaml` |
| G | `loaders.methods` (`src/`) | `dds-defaults.json`, the method libraries, `define-patch.yaml` | `dds-methods.json`, `define-patch.yaml`, `methods-report.yaml` |
| H | `define_generator.py` (`generators/define/`), then `defineutils.validate` | `dds-methods.json` | `define.xml` |

- Paths in the study YAML are relative to it and made absolute, because each stage runs in its
  own folder (`define-xml/` and `generators/define/` use flat imports).
- A stage that exits non-zero stops the run. `--from`/`--to` re-run part of it:
  - `--from E` after answering `origin-review.yaml`;
  - `--from F` after answering `define-patch.yaml` or editing a defaults dictionary;
  - `--from G` after answering only the `methods` and `resources` sections of `define-patch.yaml`,
    or after editing a method library.
- A review file that exists is applied (`--apply_patch`) and written back with what is still
  open. They sit beside the study YAML, because they hold a person's answers; everything
  generated goes to `output_dir`.
- **The define patch has one writer, stage G.**
  - Stage A applies `define-patch.yaml` but writes its own full placeholder list to
    `output_dir/define-patch-stageA.yaml`.
  - Stage F applies the answers again, to values still unfilled, and fills the well-known
    defaults. It runs with `--patch_read_only`, so it does not write the file.
  - Stage G attaches a method to every Derived item and applies the `methods` and `resources`
    answers. It then rewrites `define-patch.yaml` with what is still open in every section plus
    every answered value, so answers survive the next run.

  A run that stops before G (`--to F`) leaves the define patch as it was.
- **Defaults** come from `defaults:` in the study YAML, a list of dictionaries where later files
  win (default `data/defaults/well_known_defaults.json`). See
  [`src/loaders/defaults`](../loaders/defaults/README.md) and [`data/defaults`](../../data/defaults/README.md).
- **Methods** come from `methods:` in the study YAML, a list of method libraries where later
  files win (default `data/methods/sdtm_methods.json`). A study file listed after the shared seed
  redefines a method or re-points an assignment. See
  [`src/loaders/methods`](../loaders/methods/README.md) and [`data/methods`](../../data/methods/README.md).
- crfutils is a separate install: `commands.crfvalidate` / `commands.crfpdf` in the YAML, or
  on `PATH`.
- **Open review items.** The run ends by listing what is still open, and `--strict` exits 1 while
  any item is open:
  - define patch open values: each `__PLACEHOLDER__` and null in `define-patch.yaml`, or in stage A's
    list before stage G has written the patch;
  - define patch open methods: the same count, for the `methods` and `resources` sections;
  - CRF `mappingReview`;
  - crfpdf's `sdtm_alias_disagrees` and `define_oid_unpaired`;
  - the `origin-review.yaml` sections;
  - the defaults report's `noPages`;
  - a define.xml that fails schema validation.
- `pipeline-run.json` in `output_dir` records each step's command, exit code, and the sha256 of its
  inputs and outputs.

Stages A and B need a CDISC Library API key (`CDISC_API_KEY`, or a `.env`).

## Tests

```bash
cd src/pipeline && pytest
```

The suite has 13 tests. Most run with the stages stubbed and cover:
- order, working folders and absolute paths;
- review files applied when present;
- the define patch paths of stages A, F and G;
- the defaults dictionaries and the method libraries;
- a failing stage stops the run, while a failed validation is only an open item;
- `--from`/`--to`, `--strict` and `--dry-run`;
- open methods counted separately.

One test runs stages G and H for real on a small DDS: it answers a placeholder method in the
define patch, runs `--from G`, and checks that the answer reaches define.xml.
