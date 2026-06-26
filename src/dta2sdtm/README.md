# dta2sdtm — Digital DTA Logical Data Model (LinkML)

A [LinkML](https://linkml.io/) logical data model for the CDISC 360i lab data flow: it
makes the lab **Data Transfer Agreement (DTA)** a typed, validatable contract and keeps
it traceable from the upstream **USDM** protocol all the way down to **SDTM-LB**.

The token *DTA* is overloaded. This model holds both senses — the governance
**Agreement** and the data **Transmission** that fulfils it — and joins them through a
single hub, the **BiomedicalConcept**.

## The three layers

| Layer | Purpose | Key classes |
|-------|---------|-------------|
| **Agreement** | The governance contract (what data, by whom, in what format, mapped to which visits). Slot names mirror the DTA app's JSON keys so a serialized agreement validates as-is. | `DataTransferAgreement`, `Study`, `Party`, `TransferRequirements`, `VisitMapping`, `BcSelection` |
| **Semantic** | The bridge from a biomedical concept to concrete SDTM-LB variables, anchored to a real, citable CDISC COSMoS specialization. | `BiomedicalConcept`, `DatasetSpecialization`, `VariableSpecialization` |
| **Instance** | The nested lab transmission payload that fulfils the agreement. The LAB Tx Model's three parallel unit blocks (`PLR*`/`CVU*`/`SIU*`) collapse into one `Result` keyed by `unitSystem`. | `Transmission`, `Subject`, `Collection`, `Specimen`, `Panel`, `LabTestResult`, `Result` |

`BiomedicalConcept` is the hub: USDM references it (`Activity.biomedicalConceptIds`), the
Agreement scopes it in (`BcSelection.bc_id` + the `is_used_by_dta` facet), and the payload
delivers it (`LabTestResult.specialization.biomedicalConcept`) en route to SDTM-LB.

Every instance slot carries **`exact_mappings`** to its LAB Transmission Model variable
(identity — same element, renamed) and an **`sdtm_lb_target`** annotation to its SDTM-LB
variable (transformation target — deliberately *not* modeled as identity, because a
derivation happens). That distinction keeps the lineage honest in both directions.

## Files

| File | Contents |
|------|----------|
| `dta.linkml.yaml` | The schema — 20 classes, slots, and CT-bound enums (NCI EVS). |
| `agreement.example.yaml` | Agreement-layer instance. Validates with `-C DataTransferAgreement`. |
| `dataset_specialization.example.yaml` | Semantic-layer instance. Validates with `-C DatasetSpecialization`. |
| `transmission.example.yaml` | Full instance payload (2 subjects, hematology + chemistry). Validates with `-C Transmission`. |
| `transmission_minimal.example.yaml` | Minimal instance payload showing a linked (HGB) and an unlinked (RBC, gap-case) analyte. |
| `cosmos/hgbbld.specialization.yaml` | Vendored CDISC COSMoS Dataset Specialization for Hemoglobin (HGBBLD / C64848). |
| `cosmos/PROVENANCE.md` | Source, retrieval, and re-derivation instructions for the vendored spec. |
| `index.html` | The DTA app — a browser-only demo that derives an agreement from USDM + MVP metadata and exports the JSON the Agreement layer types. |
| `digital_dta_flow.png` | The Digital DTA Flow diagram this model implements. |
| `discovery_questions.md` | The discovery questions that scoped the model. |

## Validate

```bash
pip install linkml

linkml-validate -s dta.linkml.yaml -C DataTransferAgreement agreement.example.yaml
linkml-validate -s dta.linkml.yaml -C DatasetSpecialization  dataset_specialization.example.yaml
linkml-validate -s dta.linkml.yaml -C Transmission           transmission.example.yaml
linkml-validate -s dta.linkml.yaml -C Transmission           transmission_minimal.example.yaml
```

## License

MIT, per this repository.
