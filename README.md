# Data Definition Engine

![under development](https://img.shields.io/badge/under-development-blue)
![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-blue.svg)

The **Data Definition Engine (DDE)** is an open-source tool that automatically generates CDISC regulatory submission artifacts from a structured clinical trial protocol, the famous **Unified Study Definitions Model (USDM)**. It is developed as part of the [CDISC 360i Program](https://github.com/cdisc-org/360i) by the Define-XML Generation Project Team.

**USDM** stands for **Unified Study Definitions Model** — a Transcelerate / CDISC standard that represents a clinical trial's complete protocol in a machine-readable JSON format. It captures things like study objectives, arms, visits, eligibility criteria, and assessments in a structured, vendor-neutral way. It's the input to this tool — the "source of truth" for the study. It was co-developed through a formal partnership between CDISC and TransCelerate BioPharma as part of **TransCelerate's Digital Data Flow (DDF)** initiative.

---

## Table of Contents

- [Background](#background)
- [How It Works](#how-it-works)
- [Study Artifacts](#study-artifacts)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
  - [Step 1 — Run the USDM Loader](#step-1--run-the-usdm-loader)
  - [Step 2 — Run the Define-XML Generator](#step-2--run-the-define-xml-generator)
  - [Full Pipeline Example](#full-pipeline-example)
- [Project Structure](#project-structure)
- [Key Concepts](#key-concepts)
- [Current Status & Roadmap](#current-status--roadmap)
- [Contributing](#contributing)
- [License](#license)
- [References](#references)

---

## Background

Clinical trials submitted to regulatory agencies (such as the FDA) must include standardized metadata files that describe the structure, content, and meaning of all datasets. Producing these files — most notably **Define-XML** — has traditionally been a manual, error-prone, and time-consuming process.

The CDISC 360i program aims to automate this process end-to-end: starting from a machine-readable study protocol (**USDM**), the DDE derives all the metadata needed to generate regulatory submission artifacts automatically. It eliminates the gap between protocol design and data submission by using the same source of truth throughout the study lifecycle.

---

## How It Works

The DDE implements a three-stage pipeline:

```
USDM Study Design JSON
        │
        ▼
┌───────────────────┐
│      LOADER       │  create_define_json.py
│                   │  • Reads the USDM protocol
│                   │  • Fetches Biomedical Concepts
│                   │  • Retrieves Dataset Specializations
│                   │  • Calls the CDISC Library API
└────────┬──────────┘
         │
         ▼  DDS JSON (define.json)  ◄── central intermediate model
         │
┌────────┴──────────┐
│     GENERATOR     │  define_generator.py
│                   │  • Reads the DDS JSON
│                   │  • Builds Define-XML v2.1 elements
│                   │  • Writes the output XML
└────────┬──────────┘
         │
         ▼
  Define-XML v2.1 (.xml)
  HTML rendering  (.html)
```

**Loaders** extract metadata from various sources and populate the central **Data Definition Specification (DDS)** model (a JSON file). **Generators** consume that DDS JSON and produce the final submission artifacts.

> **Why a central JSON model?**
> No single source has all the metadata needed for a full submission. The DDS acts as an aggregation layer, combining protocol content, biomedical concept definitions, controlled terminology, and any manually filled gaps into one validated model.

---

## Study Artifacts

| Artifact | Format | Description | Status |
|---|---|---|---|
| SDTM Define-XML | `.xml` | Metadata file describing SDTM dataset structure, variables, and controlled terminology for FDA submission | ✅ Implemented |
| ADaM Define-XML | `.xml` | Same for Analysis Datasets (ADaM) | 🔜 Planned |
| ODM CRFs | `.xml` | Case Report Form definitions in ODM format for data collection | 🔜 Planned |
| Trial Design Datasets | `.json` | TA, TD, TE, TI, TM, TS, TV datasets describing study design | 🔜 Planned |
| Dataset-JSON shells | `.json` | Empty dataset templates in Dataset-JSON format | 🔜 Planned |

---

## Prerequisites

- **Python 3.8+**
- A **CDISC Library API key** — required to fetch Biomedical Concepts and Dataset Specializations during loading. Request one at [CDISC Library](https://library.cdisc.org/).
- Git (to clone the repository)

---

## Installation

```bash
# Clone the repository
git clone https://github.com/cdisc-org/data-definition-engine.git
cd data-definition-engine

# Install loader dependencies
pip install -r src/define-xml/requirements.txt

# Install generator dependencies
pip install -r src/generators/define/requirements.txt
```

**Set your CDISC Library API key** — create a `.env` file in `src/define-xml/`:

```bash
# src/define-xml/.env
CDISC_API_KEY=your_api_key_here
```

Or pass it directly on the command line with `--cdisc_api_key`.

---

## Usage

### Step 1 — Run the USDM Loader

The loader reads a USDM protocol JSON file, enriches it with metadata from the CDISC Library, and writes a DDS JSON file.

> **Windows (PowerShell):** use a backtick `` ` `` for line continuation instead of `\`.

```bash
# bash / macOS / Linux
cd src/define-xml

python create_define_json.py \
  --usdm_file ../../data/protocol/LZZT/usdm/pilot_LLZT_protocol.json \
  --output_template ./output/define.json \
  --sdtmct 2024-09-27
```

```powershell
# Windows PowerShell
cd src/define-xml

python create_define_json.py `
  --usdm_file ..\..\data\protocol\LZZT\usdm\pilot_LLZT_protocol.json `
  --output_template .\output\define.json `
  --sdtmct 2024-09-27
```

**All arguments:**

| Argument | Required | Default | Description |
|---|---|---|---|
| `--usdm_file` | Yes | — | Path to the USDM input JSON file |
| `--output_template` | Yes | — | Path for the output DDS JSON file |
| `--sdtmct` | Yes | — | SDTM Controlled Terminology date (`yyyy-mm-dd`) |
| `--sdtmig` | No | `3.4` | SDTM Implementation Guide version |
| `--studyversion` | No | `0` | Study version index in the USDM file (0-based) |
| `--studydesign` | No | `0` | Study design index (0-based) |
| `--docversion` | No | `0` | Document version index (0-based) |
| `--cdisc_api_key` | No | env var | CDISC Library API key (falls back to `CDISC_API_KEY`) |
| `--cosmosversion` | No | `v2` | CDISC Cosmos API version |
| `--validate` | No | — | Validate output against a LinkML YAML schema (uses `define.yaml` if no path given) |
| `--validation_report` | No | — | Path to write an Excel validation report (required with `--validate`) |
| `--patch_file` | No | — | Generate a YAML patch file listing all placeholder/null fields |
| `--apply_patch` | No | — | Apply a completed patch file to fill in placeholder values |
| `--debug` | No | `False` | Save intermediate dictionaries as JSON files for inspection |
| `--cacert` | No | — | Path to a CA bundle (`.pem`) for SSL verification — use when behind a corporate proxy |
| `--no_ssl_verify` | No | `False` | Disable SSL certificate verification (use only in trusted environments) |

**Tip:** On the first run, use `--patch_file gaps.yaml` to generate a list of all fields that could not be derived automatically. Fill in the values, then re-run with `--apply_patch gaps.yaml`.

---

### Step 2 — Run the Define-XML Generator

The generator reads the DDS JSON file and produces a Define-XML v2.1 file.

```bash
# bash / macOS / Linux
cd src/generators/define

python define_generator.py \
  --template ../../define-xml/output/define.json \
  --define ./output/define.xml
```

```powershell
# Windows PowerShell
cd src\generators\define

python define_generator.py `
  --template ..\..\define-xml\output\define.json `
  --define .\output\define.xml
```

**All arguments:**

| Argument | Short | Required | Default | Description |
|---|---|---|---|---|
| `--template` | `-t` | Yes | — | Path to the DDS JSON input file |
| `--define` | `-d` | No | (built-in default) | Path for the output Define-XML `.xml` file |
| `--validate` | `-s` | No | `False` | Schema-validate the generated XML after writing |
| `--log-level` | `-l` | No | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |

Processing is logged to `define_generator.log`.

---

### Full Pipeline Example

```bash
# bash / macOS / Linux — from the repository root

# 1. Load: USDM → DDS JSON
cd src/define-xml
python create_define_json.py \
  --usdm_file ../../data/protocol/LZZT/usdm/pilot_LLZT_protocol.json \
  --output_template ../../output/define.json \
  --sdtmct 2024-09-27 \
  --validate \
  --validation_report ../../output/validation_report.xlsx

# 2. Generate: DDS JSON → Define-XML
cd ../generators/define
python define_generator.py \
  --template ../../output/define.json \
  --define ../../output/define.xml \
  --validate
```

```powershell
# Windows PowerShell — from the repository root

# 1. Load: USDM → DDS JSON
cd src\define-xml
python create_define_json.py `
  --usdm_file ..\..\data\protocol\LZZT\usdm\pilot_LLZT_protocol.json `
  --output_template ..\..\output\define.json `
  --sdtmct 2024-09-27 `
  --validate `
  --validation_report ..\..\output\validation_report.xlsx

# 2. Generate: DDS JSON → Define-XML
cd ..\generators\define
python define_generator.py `
  --template ..\..\output\define.json `
  --define ..\..\output\define.xml `
  --validate
```

The resulting `output/define.xml` is your SDTM Define-XML v2.1 submission file.
To render it as HTML for human review, apply the bundled XSL stylesheet:

```bash
# Using xsltproc (Linux/macOS) or Saxon (Windows)
xsltproc src/generators/define/define2-1.xsl output/define.xml > output/define.html
```

---

## Project Structure

```
data-definition-engine/
│
├── data/                         # Sample study data for development and testing
│   ├── protocol/LZZT/usdm/       # CDISC pilot study LZZT in USDM format
│   └── metadata_xlsx/LZZT/       # SDTM and ADaM metadata spreadsheets (LZZT)
│
├── documents/
│   ├── Solution_Overview.md      # Architecture design document
│   └── glossary.md               # Definitions of key terms
│
├── HowTos/                       # Guides and GIF walkthroughs
│
└── src/
    ├── define-xml/               # LOADER: USDM → DDS JSON
    │   ├── create_define_json.py # Main loader script
    │   ├── define.yaml           # LinkML schema for the DDS model
    │   └── requirements.txt
    │
    └── generators/
        └── define/               # GENERATOR: DDS JSON → Define-XML
            ├── define_generator.py
            ├── define2-1.xsl     # XSL stylesheet for HTML rendering
            ├── requirements.txt
            └── tests/
                └── fixtures/     # Sample DDS JSON and expected XML/HTML outputs
```

---

## Key Concepts

| Term | Definition |
|---|---|
| **USDM** (Unified Study Definitions Model) | A TransCelerate / CDISC standard that represents a complete clinical trial protocol as structured, machine-readable JSON. It is the primary input to the DDE. |
| **CDISC 360i** | A CDISC initiative to make the full clinical trial lifecycle — from protocol to submission — machine-readable and interoperable. |
| **DDS** (Data Definition Specification) | The central intermediate JSON model in the DDE pipeline. It aggregates metadata from all sources and acts as the single input for all generators. |
| **Define-XML** | An XML file submitted alongside clinical trial datasets that describes their structure, variables, permitted values, and controlled terminology. Required by the FDA. It is based on the ODM version 2.0 |
| **Biomedical Concepts (BCs)** | Standardized, reusable definitions of clinical observations (e.g., "Heart Rate") maintained in the CDISC Library. |
| **Dataset Specializations (DSSs)** | CDISC Library mappings that describe how a Biomedical Concept is represented in a specific SDTM domain. |
| **CDISC Library** | CDISC's REST API providing access to controlled terminology, SDTM variables, Biomedical Concepts, and Dataset Specializations. |
| **odmlib** | A Python library for creating and parsing CDISC ODM and Define-XML documents, used internally by the generator. |
| **LinkML** | A modeling language used to define and validate the DDS JSON schema (`define.yaml`). |
| **VLM** (Variable Level Metadata) | Metadata that applies to specific values within a variable (e.g., rules that only apply when `VSTEST = "SYSBP"`). |

---

## Current Status & Roadmap

The project is in **active development**, currently completing Phase 2 of the CDISC 360i Program.

**Phase 1 (complete):**
- USDM loader (`create_define_json.py`)
- SDTM Define-XML generator (`define_generator.py`)
- DDS JSON schema (`define.yaml`)

**Phase 2 (in progress):**
- ADaM Define-XML generator
- ODM CRF generator
- Trial Design dataset generator
- Dataset-JSON shell generator
- Spreadsheet-based loader (alternative to USDM)
- Incremental loading with metadata provenance tracking
- Quality and conformance checks

> This project is provided "as is" without warranty or guarantee of suitability for any particular purpose. Expect breaking changes as the new ADaM models and additional generators are developed.

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting pull requests. All contributions must follow the [Code of Conduct](CODE_OF_CONDUCT.md) and will fall under the project licenses below.

---

## License

### Code and Models
Licensed under the [MIT License](LICENSE).

### Content (documentation, etc.)
Licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).

When re-using content, please cite as:
> Content based on [Data Definition Engine (GitHub)](https://github.com/cdisc-org/data-definition-engine) used under the [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/) license.

---

## References

- [DDS model (define.json)](https://github.com/TeMeta/define-json) — The Define-JSON data model specification
- [DDS documentation site](https://temeta.github.io/define-json/)
- [CDISC 360i Program repository](https://github.com/cdisc-org/360i)
- [Data Definition Specification project](https://github.com/cdisc-org/DataExchange-DDS)
- [Define-XML generator (template2define)](https://github.com/swhume/template2define)
- [CRF generator POCs](https://github.com/lexjansen/cdisc360i-pocs)
- [Phase 1 metadata gaps](https://wiki.cdisc.org/spaces/360i/pages/319525446/360i+Phase+1+Metadata+Gaps)
- [DDS project charter](https://wiki.cdisc.org/display/XMLT/define.json+project+charter)
