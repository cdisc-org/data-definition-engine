# dta2sdtm — Digital DTA Logical Data Model (LinkML)

A [LinkML](https://linkml.io/) logical data model for the CDISC 360i lab data flow: it
makes the lab **Data Transfer Agreement (DTA)** a typed, validatable contract and keeps
it traceable from the upstream **USDM** protocol all the way down to **SDTM-LB**.

The token *DTA* is overloaded. This model holds both senses — the governance
**Agreement** and the data **Transfer** that fulfils it — and joins them through a
single hub, the **BiomedicalConcept**.

**Schema version 0.2.0.** Built from the DTA MVP Inventory, which the workstream
confirmed as the DTA User Requirements. See [What changed in v0.2.0](#what-changed-in-v020).

## The three layers

| Layer | Purpose | Key classes |
|-------|---------|-------------|
| **Agreement** | The governance contract: what data, by whom, in what format, mapped to which visits, comprising **which tests**, in **which dataset structure**. | `DataTransferAgreement`, `Study`, `BcSelection`, `TestSpecification`, `TransferDataset`, `Party`, `TransferRequirements`, `VisitMapping` |
| **Semantic** | The bridge from a biomedical concept to concrete SDTM-LB variables, anchored to a real, citable CDISC COSMoS specialization. | `BiomedicalConcept`, `DatasetSpecialization`, `VariableSpecialization` |
| **Instance** | The delivered payload: one flat record per lab result, typed from the inventory's agreed data structure. | `Transmission`, `TransferRecord` |

`BiomedicalConcept` is the hub: USDM references it (`Activity.biomedicalConceptIds`), the
Agreement scopes it in (`BcSelection.bc_id` + the `is_used_by_dta` facet, and per-test via
`TestSpecification.bc_id`), and the payload delivers it en route to SDTM-LB.

## Agreement ↔ instance

Contract-vs-fulfilment is modelled explicitly rather than merely asserted, at two levels:

- **File level** — `Transmission.dta_version_ref` names the DTA document version a
  delivery fulfils, so a received file traces back to the contract that authorised it.
- **Test level** — a **natural-key join**: `TestSpecification` (`test_panel_name` +
  `data_provider_test_code`, falling back to `data_provider_test_name`) ↔ `TransferRecord`
  (`lbpanel` + `ctestcd` / `ctest`).

No surrogate key is used, deliberately: no real transfer file carries one, so a
`spec_id` slot would exist in the model and in no actual data. The name fallback is
needed because tests are not always coded — in the source inventory's own examples, the
flow-cytometry and IHC rows identify tests by name only.

**Why both layers exist.** The SDTM-LB derivation is a function of
`(TransferRecord × TestSpecification)`. The payload carries the value; the agreement
carries the per-test facts no payload can — the unit conversion basis, the result form,
and the BC identity. `TestSpecification.data_type` in particular is what tells the
transform whether `LBORRES` may be cast to `LBSTRESN`; without it, a categorical result
such as a urinalysis colour is attempted as a number.

## Design rule — permissive payload, strict agreement

Enumerations bind on the **agreement** side, where the sponsor controls the values.
Payload slots a vendor populates (units, status, dates) stay unconstrained strings, so a
conformant-but-unanticipated file is not rejected at ingest. Discrepancies surface in the
transform, by comparing payload against agreement, rather than as a load failure.

Two consequences worth knowing:

- `UnitEnum` and `LbTestCdEnum` are **documented reference vocabularies, bound to no
  slot**. Real transfers legitimately carry units outside any fixed subset.
- Only the variables the source structure types as numeric are typed numerically. That
  is what keeps a categorical result from being coerced.

## Lineage annotations

`labtx:` `exact_mappings` point at LAB Transmission Model v2.0 variables (identity — same
element, renamed). `sdtm_lb_target` annotations point at SDTM-LB variables (transformation
target — deliberately *not* identity, because a derivation happens). `usdm_property`
annotations carry the upstream USDM attribute for agreement fields. That distinction keeps
the lineage honest in all three directions.

LAB v2 is no longer the transfer structure, but the `labtx:` mappings are retained: it
remains the vocabulary the inventory's test specification maps every column back to, so it
is still a valid mapping target.

Slots that are **project-defined rather than CDISC-registered** say so in their own
annotations (`transfer_structure_version`, `dta_version_ref`). Nothing is presented as
standard terminology unless it is.

## Files

| File | Contents |
|------|----------|
| `dta.linkml.yaml` | The schema — 19 classes, 191 slots, 15 enums. |
| `agreement.example.yaml` | Agreement-layer instance, incl. test specification and data structure. Validates with `-C DataTransferAgreement`. |
| `dataset_specialization.example.yaml` | Semantic-layer instance. Validates with `-C DatasetSpecialization`. |
| `transmission.example.yaml` | Full payload (2 subjects, hematology + chemistry, plus a categorical result and a not-done test). Validates with `-C Transmission`. |
| `transmission_minimal.example.yaml` | Minimal payload showing an agreed test and one absent from the agreement (gap case). |
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

## What changed in v0.2.0

| | v0.1.0 | v0.2.0 |
|---|---|---|
| Test-level agreement | *(none)* | `TestSpecification` |
| Declared file structure | *(none)* | `TransferDataset` / `TransferVariable` |
| Instance shape | nested LAB v2 graph: `Subject > Collection > Specimen > Panel > LabTestResult > Result` | flat `TransferRecord` (60 variables) |
| Agreement ↔ instance | asserted in prose | file-level ref + test-level natural-key join |
| USDM traceability | class-level on `Study` only | per-field on study, party, visit slots |
| Classes / enums | 21 / 19 | 19 / 15 |

The instance change is a change of **transfer vocabulary**, not merely of shape: the
removed graph modelled LAB v2 variables (`LTVRSN`, `ACCSNID`, `SPECID`, `PLBTID`,
`PLRCRS`…), while `TransferRecord` models SDTM-shaped columns plus vendor passthrough
(`CTESTCD`, `CTEST`, `CUNIT`, `CSPEC`, `CMETHOD`, `CPANEL`) and ten `AUX` escape hatches.
The two share essentially only `STUDYID`.

### Known limitations of the agreed transfer structure

Two properties of the transfer structure itself — not of this model — constrain what SDTM
can be produced. Neither is worked around here, because inventing columns would
misrepresent the agreed structure:

1. **No standardised result or unit.** Only the original result (`LBORRES` / `LBORRESU`)
   is carried. `LBSTRESC` / `LBSTRESN` / `LBSTRESU` must therefore be derived from
   `TestSpecification`, which makes a complete test specification load-bearing rather
   than merely useful.
2. **No reference ranges.** There is no equivalent of `LBORNRLO`, `LBORNRHI` or
   `LBNRIND`, so those SDTM variables are not derivable from a transfer alone.

## License

MIT, per this repository.
