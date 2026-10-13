# define_generator.py

## Introduction
The `define_generator.py` program takes a Data Definition Specification (DDS) model JSON file (e.g.
`dds.json` or `define.json`) as input and generates a [Define-XML v2.1](https://www.cdisc.org/standards/data-exchange/define-xml)
file from that metadata. The DDS model captures the metadata needed to describe study datasets, variables,
codelists, methods, comments, and documents.

The DDS JSON is produced by a companion loader, `create_define_json.py`, located in
[`src/define-xml/`](../../define-xml/README.md), which reads a USDM study design and enriches it using the
CDISC Library. Together the two programs form the **loaders → DDS JSON → generators** pipeline described in the
[Solution Overview](../../../documents/Solution_Overview.md): the DDS JSON file is the contract between the two
halves. `define_generator.py` uses the [odmlib](https://github.com/swhume/odmlib) library to build and serialize
the Define-XML output.

Both applications are command-line tools and can be run in sequence to produce a Define-XML v2.1 file. Once
generated, the Define-XML file can be schema-validated and rendered as HTML using the Define-XML style sheet
(see [Working with the Generated Define-XML File](#working-with-the-generated-define-xml-file)).

> **Note:** `define_generator.py` and `create_define_json.py` are under active development and are not yet
> feature-complete. The DDS model is still evolving and will continue to change.

## What it generates
For each run, `define_generator.py` assembles an `ODM → Study → MetaDataVersion` document tree and emits the
following Define-XML element types under `MetaDataVersion`:

- `ItemGroupDef` — dataset-level metadata (one per dataset), including `leaf` file references
- `ItemDef` / `ItemRef` — variable-level metadata, origins, and key sequences
- `ValueListDef` / `WhereClauseDef` — value-level metadata derived from itemGroup `slices`
- `CodeList` — enumerated and external codelists
- `MethodDef` — derivation methods (auto-created for `Derived` origins during post-processing)
- `CommentDef` — comments
- `def:leaf` / Documents — supporting document references, including the annotated CRF

## Prerequisites
- **Python 3.10 or higher** (the code uses `X | None` union type hints).
- The [odmlib](https://github.com/swhume/odmlib) package (installed via `requirements.txt` below).
- A DDS JSON input file. A canonical sample is provided at `tests/fixtures/dds.json` or `tests/fixtures/define.json`.

## Setup
The generator half lives in `src/generators/define/` and has its **own** `requirements.txt`, independent of the
loader half in `src/define-xml/`. Run all commands from the `src/generators/define/` directory.

1. **Clone the repository and change into the generator directory:**

   ```commandline
   git clone https://github.com/cdisc-org/data-definition-engine.git
   cd data-definition-engine/src/generators/define
   ```

2. **Create and activate a virtual environment** (recommended):

   ```commandline
   python3 -m venv venv
   source venv/bin/activate        # Windows: venv\Scripts\activate
   ```

3. **Install the dependencies:**

   ```commandline
   pip install -r requirements.txt
   ```

   This installs `odmlib`, `xmlschema`, `defineutils`, and `pytest`. To pick up the latest odmlib features,
   you can instead install odmlib from source — see the
   [odmlib repository](https://github.com/swhume/odmlib). The PyPI package is functional but may lag the
   repository:

   ```commandline
   pip install odmlib
   ```

4. **Verify the installation** by generating Define-XML from the sample fixture:

   ```commandline
   python define_generator.py -t ./tests/fixtures/define-360i.json -d ./tests/fixtures/define-360i.xml
   ```

> **Important — run from the package directory.** The generator uses flat top-level imports
> (`import items`, `import codeLists`, ...) rather than package-relative imports, so it (and its test suite)
> must be run with `src/generators/define/` as the working directory. Running from anywhere else will fail with
> `ModuleNotFoundError`.

## Usage
Basic invocation requires only the input DDS JSON file (`-t`); the output path (`-d`) defaults to
`tests/fixtures/define-360i.xml`:

```commandline
python define_generator.py -t ./tests/fixtures/define-360i.json -d ./tests/fixtures/define-360i.xml
```

Generate and schema-validate in a single step:

```commandline
python define_generator.py -t ./tests/fixtures/define-360i.json -d out.xml --validate
```

## Command-line arguments
| Short | Long           | Argument         | Required | Default                          | Description |
|-------|----------------|------------------|----------|----------------------------------|-------------|
| `-t`  | `--template`   | path             | **Yes**  | —                                | Path and file name of the DDS JSON file to load. Despite the name, this is the DDS/Define-JSON input, not an XML template. The program exits with an error if the file does not exist. |
| `-d`  | `--define`     | path             | No       | `tests/fixtures/define-360i.xml` | Path and file name of the Define-XML v2.1 file to create. Parent directories are created automatically if they do not exist. |
| `-v`  | `--validate`   | flag             | No       | off                              | Schema-validate the generated Define-XML against the Define-XML v2.1 schema after writing it. The program exits with status `1` if validation fails. |
| `-s`  | `--submission` | flag             | No       | off (`Other`)                    | Set the Define-XML `def:Context` attribute to `Submission`. When omitted, the context is `Other`. |
| `-x`  | `--sas_xpt`    | flag             | No       | off (`.ndjson`)                  | Set dataset file extensions in the `def:leaf` references to `.xpt` instead of the default `.ndjson`. |
| `-l`  | `--log-level`  | level            | No       | `INFO`                           | Logging verbosity. One of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Log output is written to `define_generator.log` in the working directory. |
| `-h`  | `--help`       | —                | No       | —                                | Show the argument help and exit. |

The `-v`, `-s`, and `-x` options are boolean flags: include the flag to turn the behavior on; omit it to keep
the default.

### Examples for each argument

**`-t` / `--template` — required DDS JSON input:**
```commandline
python define_generator.py -t ./tests/fixtures/define-360i.json
```
With `-t` alone, the output is written to the default path (`tests/fixtures/define-360i.xml`).

**`-d` / `--define` — choose the output path:**
```commandline
python define_generator.py -t ./tests/fixtures/define-360i.json -d ./output/define.xml
```
The `./output/` directory is created automatically if it does not already exist.

**`-v` / `--validate` — schema-validate after generating:**
```commandline
python define_generator.py -t ./tests/fixtures/define-360i.json -d out.xml --validate
```
On success the program exits `0`; on a schema violation it logs the error and exits `1`.

**`-s` / `--submission` — mark the file as a submission:**
```commandline
python define_generator.py -t ./tests/fixtures/define-360i.json -d out.xml --submission
```
Sets `def:Context="Submission"` (the default is `def:Context="Other"`).

**`-x` / `--sas_xpt` — emit SAS XPORT (`.xpt`) dataset extensions:**
```commandline
python define_generator.py -t ./tests/fixtures/define-360i.json -d out.xml --sas_xpt
```
Dataset `def:leaf` references use `.xpt` (e.g. `dm.xpt`) instead of `.ndjson` (e.g. `dm.ndjson`).

**`-l` / `--log-level` — increase logging detail:**
```commandline
python define_generator.py -t ./tests/fixtures/define-360i.json -d out.xml --log-level DEBUG
```
Diagnostic detail is written to `define_generator.log`.

**Combining options:**
```commandline
python define_generator.py -t ./tests/fixtures/define-360i.json -d ./output/define.xml \
    --submission --sas_xpt --validate --log-level DEBUG
```

## Input and output
- **Input:** a DDS JSON file whose top-level lists (`itemGroups`, `conditions`, `whereClauses`, `codeLists`,
  `methods`, `standards`, `annotatedCRF`, `concepts`, `conceptProperties`, `dictionaries`, `comments`,
  `documents`) are dispatched to dedicated loaders, and whose scalar fields populate the Study/MetaDataVersion
  attributes. See `tests/fixtures/define-360i.json` for the canonical example.
- **Output:** a Define-XML v2.1 XML file at the path given by `-d`.
- **Log file:** `define_generator.log` is written to the working directory on every run.

## Running the tests
The test suite uses `pytest` (configured in `pytest.ini`, with `testpaths = tests`). Run it from the package
directory:

```commandline
cd src/generators/define
pytest
```

Run a single test module or test:

```commandline
pytest tests/test_define_generator.py
pytest tests/test_define_generator.py::TestDefineGeneratorIntegration::test_generate_xml_from_main_sample
```

The tests `chdir` into `src/generators/define/` so the flat top-level imports resolve — see the note in
[Setup](#setup).

## Working with the Generated Define-XML File
### defineutils package
The `defineutils` package (installed with `requirements.txt`) can validate a Define-XML file and render it as
HTML using the Define-XML style sheet. It can also be used as a library in your own Python application. From the
command line:

```commandline
python3 -m defineutils.validate -d define-360i.xml
python3 -m defineutils.definehtml -d define-360i.xml -o define-360i.html
```

### xmllint command-line tool
`xmllint` can validate the Define-XML file against the schema (adjust the schema path for your environment):

```commandline
xmllint --schema ~/src/schemas/DefineV219/schema/cdisc-define-2.1/define2-1-0.xsd ./tests/fixtures/define-360i.xml --noout
```

`xmllint` can also pretty-print the Define-XML file:

```commandline
xmllint --format ./tests/fixtures/define-360i.xml | less
```

## Troubleshooting
- **`ModuleNotFoundError` (e.g. `No module named 'items'`)** — you are not running from
  `src/generators/define/`. Change into that directory first (see [Setup](#setup)).
- **"The template file specified on the command-line cannot be found."** — the path passed to `-t` does not
  point to an existing file. Check the path and working directory.
- **`ERROR: Invalid JSON in <file> ...`** — the DDS JSON input is malformed; the program logs the line number
  and exits `1`. Validate the JSON and re-run.
- **`ERROR: Schema validation failed: ...` (with `--validate`)** — the generated Define-XML did not pass schema
  validation; the program exits `1`. Inspect `define_generator.log` (use `--log-level DEBUG` for more detail).

## Architecture overview
`DefineGenerator.create()` runs a fixed pipeline: load the DDS JSON → initialize per-element containers →
dispatch each section to its loader (via the `LOADERS` registry) → post-process (auto-create derived `MethodDef`
placeholders, wire `MethodOID` onto `ItemRef`s, assign key sequences) → build the odmlib document tree → write
the XML. For a deeper description of the loaders/DDS/generators design, see:

- [`../../../documents/Solution_Overview.md`](../../../documents/Solution_Overview.md) — full architecture and rationale
- [`../../../documents/glossary.md`](../../../documents/glossary.md) — CDISC and DDE terminology
- [`../../define-xml/README.md`](../../define-xml/README.md) — the companion loader (`create_define_json.py`)
- [`../../../README.md`](../../../README.md) — links to related external repositories

## Limitations
`define_generator.py` is still under development and the DDS JSON model continues to evolve, so expect changes.
Features are added on an ongoing basis and both the generator and the DDS model may change without notice.
