# pipeline — stages A-F from the study design to define.xml and the annotated CRF

```bash
cd src
python -m pipeline --study ../data/protocols/NCT01797120/pipeline.yaml [--from A] [--to F] [--strict] [--dry-run]
```

| Stage | Program (run in) | Reads | Writes |
|---|---|---|---|
| A | `create_define_json.py` (`define-xml/`) | USDM, CDISC Library | DDS1 (`dds_define`), `define-patch.yaml` |
| B | `loaders.crf.crf_loader` (`src/`) | DDS1, USDM, CRF specializations | `dds-crf.json`, `crf-refinement.yaml` |
| C | `crf_generator.py` (`generators/crf/`) | `dds-crf.json` | `crf-2.0.xml` |
| D | crfutils `crfvalidate`, `crfpdf` | `crf-2.0.xml` | `acrf.pdf` (named by the DDS annotated CRF), `acrf.pagerefs.json` |
| E | `loaders.pagerefs` (`src/`) | `dds-crf.json`, pagerefs, CRF | `dds-origin.json`, `origin-review.yaml` |
| F | `define_generator.py` (`generators/define/`), then `defineutils.validate` | `dds-origin.json` | `define.xml` |

- Paths in the study YAML are relative to it and made absolute, because each stage runs in its
  own folder (`define-xml/` and `generators/define/` use flat imports).
- A stage that exits non-zero stops the run. `--from`/`--to` re-run part of it, e.g.
  `--from E` after answering `origin-review.yaml`.
- A review file that exists is applied (`--apply_patch`) and written back with what is still
  open. They sit beside the study YAML, because they hold a person's answers; everything
  generated goes to `output_dir`.
- crfutils is a separate install: `commands.crfvalidate` / `commands.crfpdf` in the YAML, or
  on `PATH`.
- The run ends with the open review items: define patch placeholders, CRF `mappingReview`,
  crfpdf's `sdtm_alias_disagrees` / `define_oid_unpaired`, the `origin-review.yaml`
  sections, and a define.xml that fails schema validation. `--strict` exits 1 while any is
  open. `pipeline-run.json` in `output_dir` records each step's command, exit code, and the
  sha256 of its inputs and outputs.

Stages A and B need a CDISC Library API key (`CDISC_API_KEY`, or a `.env`).

## Tests

```bash
cd src/pipeline && pytest
```

8 tests with the stages stubbed: order, working folders, absolute paths, review files
applied when present, a failing stage stops the run, a failed validation is an open item,
`--from`/`--to`, `--strict`, `--dry-run`.
