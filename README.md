# Data Definition Engine

This repository contains an open-source tool for generating CDISC 360i study artifacts from a USDM study design. This
software is being developed as part of the CDISC 360i Program by the Define-XML Generation Project Team.

![under development](https://img.shields.io/badge/under-development-blue)

## Description
The Data Definition Engine (DDE) is a software tool being created as part of the CDISC 360i Define-XML generation 
project. The DDE software populates the Data Definition Specification (DDS) model as JSON to facilitate the generation 
of study artifacts, such as Define-XML, ODM CRFs, Dataset-JSON shells, and the Trial Design datasets. 

The DDE software will include multiple loaders and generators that use the DDS model. The loaders extract and load
metadata content into the DDS model. The generators use the DDS model to generate the study artifacts such as a 
define.xml of ODM-based CRFs.

Loaders will include the primary 360i loader that reads the USDM study design content, gets the Biomedical Concepts 
referenced in the SOA, retrieves the Dataset Specializations (DSSs), and uses the CDISC Library API to populate the 
DDS model. An alternative loader will be created to load the DDS model from an Excel metadata spreadsheet template that 
matches the metadata spreadsheets used by many organizations today.

## Contribution

We welcome contributions to this project. All contributions to this repository fall under the below licenses. 
Please checkout [Contribution](CONTRIBUTING.md) for additional information. All contributions must adhere to the 
following [Code of Conduct](CODE_OF_CONDUCT.md).

## License

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg) ![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-blue.svg)

### Code and Models

This project is using the [MIT](http://www.opensource.org/licenses/MIT "The MIT License | Open Source Initiative") license (see [`LICENSE`](LICENSE)) for 
code and models.

### Content

The content files, like documentation, are released under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). This does not include trademark permissions.

## Re-use

When you re-use the source, keep or copy the license information also in the source code files. When you re-use the 
source in proprietary software or distribute binaries (derived or underived), also copy the license text to a 
third-party-licenses file or similar.

When you want to re-use and refer to the content, please do so like the following:

> Content based on [Data Definition Engine (GitHub)](https://github.com/cdisc-org/data-definition-engine) used under the [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/) license.

## Limitations
This project is under active development, so there may be some rough edges, and you should expect changes. We are
entering Phase 2 of the CDISC 360i Program, so there will be some exploratory work to come as we learn more about the
new models used to generate an ADaM define.xml, for example.

This project is provided "as is" without any warranty or guarantee of suitability for any particular purpose.

## References
We are in the process of consolidating our project work into this repository. Today, our models and code are spread 
across multiple repositories.
- [DDS model (aka define.json)](https://github.com/TeMeta/define-json)
- [DDS documentation site](https://temeta.github.io/define-json/)
- [DDS USDM loader (create_define_json.py)](https://github.com/cdisc-org/360i)
- [Define-XML generator (define_generator.py)](https://github.com/swhume/template2define)
- [CRF generator (cdash_poc_odm132.py, cdash_poc_odm20.py)](https://github.com/lexjansen/cdisc360i-pocs)
- [Phase 1 metadata gaps](https://wiki.cdisc.org/spaces/360i/pages/319525446/360i+Phase+1+Metadata+Gaps)
- [DDS project repository (future)](https://github.com/cdisc-org/DataExchange-DDS)
- [DDS project charter](https://wiki.cdisc.org/display/XMLT/define.json+project+charter)

## Related Projects
Here are some related projects:
- [Data Definition Specification project](https://github.com/cdisc-org/DataExchange-DDS)
- [CDISC 360i Program repository](https://github.com/cdisc-org/360i)
