# USDM to Define-JSON Processor

This script transforms a [USDM](https://www.cdisc.org/standards/foundational/usdm) (Unified Study Data Model) JSON file into a Define-JSON structure. 

---

## Prerequisites

### Python version

Python 3.11 or later is required, because `requirements.txt` pins pandas 3.x. pandas is used only to write the Excel validation report (`--validation_report`).

### Required packages

Install dependencies with:

```bash
pip install -r requirements.txt
```

| Package | Purpose |
|---|---|
| `jmespath` | JMESPath queries for USDM navigation |
| `cdisc-library-client` | CDISC Library REST API client |
| `python-dotenv` | Load API key from a `.env` file |
| `pyyaml` | Read and write YAML patch files and the schema |
| `linkml`, `linkml-runtime`, `jsonschema` | Validate the output against the LinkML schema (`--validate`) |
| `pandas`, `openpyxl` | Write the Excel validation report |

### CDISC Library API key

The script requires a valid CDISC Library API key. Provide it in one of three ways:

1. **Environment variable** – set `CDISC_API_KEY` in your shell or system environment.
2. **`.env` file** – create a `.env` file containing the line below, either in this directory or in any directory above it, such as the repository root (the search starts at the script's directory and walks upward):
   ```
   CDISC_API_KEY=your_api_key_here
   ```
3. **Command-line argument** – pass `--cdisc_api_key <key>` at runtime.

---

Usage of a CDISC Library proxy with caching can significantly speed up
the development and testing process. Use `--base_api_url <http(s)://address:port/api>` to specify the proxy URL and port.


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
| `--base_api_url` | No | — | CDISC Library API base URL (overrides default value of CDISCLibraryClient) |
| `--cosmosversion` | No | `v2` | CDISC Cosmos API version |
| `--validate [schema]` | No | `define.yaml` | Validate output against a YAML schema file. If omitted the default `define.yaml` is used. Requires `--validation_report` when specified. |
| `--validation_report` | Conditional | — | Path to the Excel validation report (required when `--validate` is used) |
| `--patch_file` | Conditional | — | Path to a YAML patch file. On every run it is (re)written with every value still `__PLACEHOLDER__` or null, for you to fill in. Required when `--apply_patch` is used. |
| `--apply_patch` | No | — | Path to a completed patch file. Its values are merged into the freshly generated output; OIDs that no longer exist are ignored. Requires `--patch_file`, so the patch file is refreshed after applying. |
| `--debug` | No | `false` | Save intermediate dictionaries as JSON debug files |

---

## Examples

### Minimal run (no validation)

```bash
python create_define_json.py \
  --usdm_file ../../data/protocols/NCT01797120/NCT01797120-latest.json \
  --output_template define.json \
  --sdtmct 2026-03-27
```

### With schema validation and debug output

```bash
python create_define_json.py \
  --usdm_file ../../data/protocols/NCT01797120/NCT01797120-latest.json \
  --output_template define.json \
  --sdtmct 2026-03-27 \
  --validate \
  --validation_report validation_report.xlsx \
  --debug
```

### Filling in placeholders with a patch file

Values the script cannot derive from the USDM (for example variable `Length` and `Origin`) are written as `__PLACEHOLDER__`. Write them to a patch file, fill it in, then re-run with the completed file:

```bash
# 1. Generate, and write the remaining placeholders to patch.yaml
python create_define_json.py \
  --usdm_file ../../data/protocols/NCT01797120/NCT01797120-latest.json \
  --output_template define.json \
  --sdtmct 2026-03-27 \
  --patch_file patch.yaml

# 2. Edit patch.yaml, then apply it (patch.yaml is refreshed with whatever is still missing)
python create_define_json.py \
  --usdm_file ../../data/protocols/NCT01797120/NCT01797120-latest.json \
  --output_template define.json \
  --sdtmct 2026-03-27 \
  --apply_patch patch.yaml \
  --patch_file patch.yaml
```

In the pipeline (`src/pipeline`), stage A applies the study's `define-patch.yaml` but writes its
full placeholder list to `output_dir/define-patch-stageA.yaml`. The defaults loader (stage F)
then fills well-known defaults and rewrites `define-patch.yaml` with what is still open plus every
value already answered, so the file you edit lists only what the defaults could not supply and
keeps your answers. Run on its own, this script still drops an answered value from the patch it
rewrites (see `FIXES.md` §6.2).

### Specifying a custom SDTMIG version and API key

```bash
python create_define_json.py \
  --usdm_file ../../data/protocols/NCT01797120/NCT01797120-latest.json \
  --output_template define.json \
  --sdtmct 2026-03-27 \
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
