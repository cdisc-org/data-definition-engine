# Dataset-JSON Generator

Generates **CDISC Dataset-JSON v1.1** shell files from a CDISC Define-XML file.

For each dataset defined in the Define-XML, the tool produces a Dataset-JSON file containing the dataset metadata (columns, data types, labels) with an empty `rows` array — ready to be populated with actual study data.

## Files

| File | Description |
|---|---|
| `create_shells_dataset_json.py` | Main Python script |
| `extract-list-ds.xsl` | XSLT stylesheet — extracts dataset names from Define-XML |
| `transform-to-ds-json.xsl` | XSLT stylesheet — transforms a single dataset to Dataset-JSON |
| `dataset.schema.json` | CDISC Dataset-JSON v1.1 JSON schema (used for validation) |

## Prerequisites

- Python 3.8+
- [SaxonC HE](https://pypi.org/project/saxonche/) (XSLT 2.0 processor)

Install all dependencies:

```bash
pip install -r requirements.txt
```

> **Note:** `pandas` and `openpyxl` are only required when `--validation_report` is used.

## Usage

Run the script from the `src/dataset-json/` directory so that the XSL and schema files are found relative to the working directory.

### Minimal

```bash
python create_shells_dataset_json.py --define_file path/to/define.xml
```

### Full

```bash
python create_shells_dataset_json.py \
  --define_file path/to/define.xml \
  --output_dir path/to/output/ \
  --validate dataset.schema.json \
  --validation_report validation_report.xlsx \
  --debug
```

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `--define_file` | Yes | — | Path to the input Define-XML file |
| `--output_dir` | No | Same directory as `define_file` | Directory where Dataset-JSON files are written |
| `--validate` | No | `dataset.schema.json` (when flag is set) | Validate generated files against this JSON schema |
| `--validation_report` | Required when `--validate` is used | — | Path for the Excel validation report |
| `--debug` | No | Off | Enable verbose output |

## Output

One `<DATASET>.json` file per dataset defined in the Define-XML, written to `--output_dir`.  
Each file conforms to the [CDISC Dataset-JSON v1.1 specification](https://www.cdisc.org/standards/data-exchange/dataset-json) and contains:

- Dataset-level metadata (`name`, `label`, `itemGroupOID`, `studyOID`, etc.)
- Column-level metadata (`itemOID`, `name`, `label`, `dataType`, `length`, `keySequence`, etc.)
- An empty `rows` array (shell file — no data records)

## Validation

When `--validate` is used, every generated file is re-read and validated against the Dataset-JSON JSON schema.  
Results are written to an Excel workbook (`--validation_report`) with two sheets:

- **Summary** — run statistics (date, status, counts)
- **Validation Errors** — one row per error with dataset name and issue description

## Notes

- The script must be run from `src/dataset-json/` (or the XSL/schema paths must be on the working directory), as the XSLT and schema files are resolved relative to the current directory.
- Placeholder values (e.g. `__PLACEHOLDER__`) in the Define-XML are handled gracefully: numeric fields such as `length` and `keySequence` that contain non-numeric values are output as `null`.
