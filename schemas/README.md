# Schemas Directory

Schemas to be used by the data-definition-engine. These schema files reflect the latest versions. Updates to the schemas should not be made in this repo, with the exception of `dds/profiles/`, which is maintained here until it lands upstream.

## Directory Structure

```structure
schemas/
├── dds/                        # LinkML schema from https://github.com/cdisc-org/DataExchange-DDS/model
│   ├── dds.yaml                # DDS model (mirrored from DataExchange-DDS)
│   ├── define.yaml             # Same model under its earlier name
│   └── profiles/crf/           # CRF profile of the DDS model, used by crf_loader.py --validate
├── define/
│   ├── 2.0/                    # Define-XML 2.0 schema (define2-0-0.xsd)
│   └── 2.1/                    # Define-XML 2.1.11 schema (define2-1-0.xsd)
└── odm/
    ├── 1.3.2/                  # ODM 1.3.2 schema (ODM1-3-2.xsd)
    └── 2.0/                    # ODM 2.0 schema (ODM.xsd)
```

## Notes

- **CRF profile.** [`dds/profiles/crf/`](dds/profiles/crf/README.md) holds the CRF additions to the DDS model. `crf.schema.json` is what `src/loaders/crf/crf_loader.py --validate` uses today; `profile.yaml` is the LinkML version, waiting on the matching upstream DDS model change.
- **Define loader validation.** `src/define-xml/create_define_json.py --validate` does not read `dds/` here. Run from `src/define-xml/`, its default `define.yaml` resolves to the older copy in that directory.
- **XSDs.** The Define-XML and ODM XSDs are for independent checks with `xmllint`. The generators' own `--validate` options use the schemas bundled with `defineutils` and `odmlib`.
