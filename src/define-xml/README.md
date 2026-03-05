# USDM to Define-JSON Processor

This script transforms a [USDM](https://www.cdisc.org/standards/foundational/usdm) (Unified Study Data Model) JSON file into a Define-JSON structure. 

---

## Prerequisites

### Python version

Python 3.9 or later is recommended.

### Required packages

Install dependencies with:

```bash
pip install jsonata cdisc-library-client python-dotenv pyyaml openpyxl
```

| Package | Purpose |
|---|---|
| `jsonata` | JSONata expression evaluation for USDM navigation |
| `cdisc-library-client` | CDISC Library REST API client |
| `python-dotenv` | Load API key from a `.env` file |
| `pyyaml` | Parse the Define-JSON YAML schema for validation |
| `openpyxl` | Write the Excel validation report |

### CDISC Library API key

The script requires a valid CDISC Library API key. Provide it in one of two ways:

1. **Environment variable** – set `CDISC_API_KEY` in your shell or system environment.
2. **`.env` file** – create a `.env` file in the working directory containing:
   ```
   CDISC_API_KEY=your_api_key_here
   ```
3. **Command-line argument** – pass `--cdisc_api_key <key>` at runtime.

---

## Usage

Run the script from the `src/define-xml/` directory:

```
python create_define_json.py --usdm_file <path> --output_template <path> --sdtmct <date> [options]
```

### Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `--usdm_file` | **Yes** | — | Path to the input USDM JSON file |
| `--output_template` | **Yes** | — | Path for the output Define-JSON file |
| `--sdtmct` | **Yes** | — | SDTM Controlled Terminology date (`yyyy-mm-dd`) |
| `--sdtmig` | No | `3.4` | SDTM Implementation Guide version |
| `--studyversion` | No | `0` | Index of the study version within the USDM file |
| `--studydesign` | No | `0` | Index of the study design within the USDM file |
| `--docversion` | No | `0` | Index of the document version within the USDM file |
| `--cdisc_api_key` | No | env var | CDISC Library API key (overrides `CDISC_API_KEY` env var) |
| `--cosmosversion` | No | `v2` | CDISC Cosmos API version |
| `--validate [schema]` | No | `define.yaml` | Validate output against a YAML schema file. If omitted the default `define.yaml` is used. Requires `--validation_report` when specified. |
| `--validation_report` | Conditional | — | Path to the Excel validation report (required when `--validate` is used) |
| `--debug` | No | `false` | Save intermediate dictionaries as JSON debug files |

---

## Examples

### Minimal run (no validation)

```bash
python create_define_json.py \
  --usdm_file ..\..\data\protocol\LZZT\usdm\pilot_LLZT_protocol.json \
  --output_template define.json \
  --sdtmct 2025-03-28
```

### With schema validation and debug output

```bash
python create_define_json.py \
  --usdm_file ..\..\data\protocol\LZZT\usdm\pilot_LLZT_protocol.json \
  --output_template define.json \
  --sdtmct 2025-03-28 \
  --validate \
  --validation_report validation_report.xlsx \
  --debug
```

### Specifying a custom SDTMIG version and API key

```bash
python create_define_json.py \
  --usdm_file ..\..\data\protocol\LZZT\usdm\pilot_LLZT_protocol.json \
  --output_template define.json \
  --sdtmct 2025-03-28 \
  --sdtmig 3.3 \
  --cdisc_api_key <your_api_key> \
  --validate \
  --validation_report validation_report.xlsx
```

---

## Output files

| File | Description |
|---|---|
| `<output_template>` (e.g. `define.json`) | Define-JSON with itemGroups, slices, conditions, whereClauses, and codeLists |
| `<validation_report>` (e.g. `validation_report.xlsx`) | Excel report listing schema validation results (pass/fail per field) |

### Debug files (created with `--debug`)

When `--debug` is enabled the following intermediate JSON files are written to the working directory:

| File | Contents |
|---|---|
| `debug_datasets_dict.json` | Variable metadata per dataset |
| `debug_bc_dict.json` | Biomedical concept VLM metadata |
| `debug_vlm_lookup.json` | VLM entries keyed by variable name |
| `debug_vlm_items_by_variable.json` | VLM items grouped for slice creation |
| `debug_test_dict.json` | TEST/TESTCD concept mappings |
| `debug_code_lists_map.json` | Deduplicated codelists by short name |
| `debug_condition_lookup.json` | Condition deduplication cache |
| `debug_dataset_data.json` | Raw dataset data accumulated during processing |

---

## Schema validation

The `--validate` flag runs the output JSON against the `define.yaml` schema (or a custom schema file you provide). The validation results are written to the Excel file specified by `--validation_report`. The script exits with code `1` if validation fails, making it suitable for use in CI pipelines.

---

## Notes

- The script requires an active internet connection to call the CDISC Library API.
- Windows terminals that default to `cp1252` encoding are handled automatically; Unicode status symbols are displayed correctly.
- The `--studyversion`, `--studydesign`, and `--docversion` arguments are zero-based indices into the corresponding arrays in the USDM JSON. Most studies use the default value of `0`.
