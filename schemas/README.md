# Schemas Directory

Schemas to be used by the data-definition-engine. These schema files reflect the latest versions. Updates to the schemas should not be made in this repo, with three exceptions: `dds/profiles/`, which is maintained here until it lands upstream, and `defaults/` and `methods/`, which the DDE owns.

## Directory Structure

```structure
schemas/
├── dds/                        # LinkML schema from https://github.com/cdisc-org/DataExchange-DDS/model
│   ├── dds.yaml                # DDS model (mirrored from DataExchange-DDS)
│   ├── define.yaml             # Same model under its earlier name
│   └── profiles/crf/           # CRF profile of the DDS model, used by crf_loader.py --validate
├── defaults/
│   └── defaults.schema.json    # The defaults dictionary format (DDE-owned), used by loaders/defaults
├── methods/
│   └── methods.schema.json     # The SDTM method library format (DDE-owned), used by loaders/methods
├── define/
│   ├── 2.0/                    # Define-XML 2.0 schema (define2-0-0.xsd)
│   └── 2.1/                    # Define-XML 2.1.11 schema (define2-1-0.xsd)
└── odm/
    ├── 1.3.2/                  # ODM 1.3.2 schema (ODM1-3-2.xsd)
    └── 2.0/                    # ODM 2.0 schema (ODM.xsd)
```

## Notes

- **CRF profile.** [`dds/profiles/crf/`](dds/profiles/crf/README.md) holds the CRF additions to the DDS model. `crf.schema.json` is what `src/loaders/crf/crf_loader.py --validate` uses today; `profile.yaml` is the LinkML version, waiting on the matching upstream DDS model change.
- **Defaults dictionary.** [`defaults/defaults.schema.json`](defaults/defaults.schema.json) is the JSON Schema (2020-12) for the dictionaries in `data/defaults/` that `src/loaders/defaults` reads. It is not a DDS schema: it describes an input to the DDE, with one section per kind of DDS object and values in DDS attribute names. Its DataType enum is a hand copy of the DDS one plus the seven ISO 8601 types PR-DDS-3 adds.
- **Method library.** [`methods/methods.schema.json`](methods/methods.schema.json) is the JSON Schema (2020-12) for the SDTM method libraries in `data/methods/` that `src/loaders/methods` reads. Its method entries are DDS Methods in the ODM v2.0 shape proposed upstream as PR-DDS-3 (`MethodSignature`, `ExternalCodeLib`, `orderNumber`). The slot names are frozen to that proposal and pinned by `src/loaders/methods/tests/test_library.py`; until `dds/dds.yaml` arrives with them through the upstream copy action, this schema is the DDE's check on the Method shape (do not edit `dds/dds.yaml` locally).
- **Define loader validation.** `src/define-xml/create_define_json.py --validate` does not read `dds/` here. Run from `src/define-xml/`, its default `define.yaml` resolves to the older copy in that directory.
- **XSDs.** The Define-XML and ODM XSDs are for independent checks with `xmllint`. The generators' own `--validate` options use the schemas bundled with `defineutils` and `odmlib`.
