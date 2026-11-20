# dta2sdtm — Digital DTA Logical Data Model (LinkML)

A [LinkML](https://linkml.io/) logical data model for the CDISC 360i data transfer flow:
it makes the **Data Transfer Agreement (DTA)** a typed, validatable contract and keeps it
traceable from the upstream **USDM** protocol all the way down to **SDTM**. The model is
dataset-agnostic: a DTA may cover lab (LB), ECG (EG), imaging (TU / TR / RS), PK/PD or
other externally provided data. Lab is the first worked example, not the scope.

The token *DTA* is overloaded. This model holds both senses — the governance
**Agreement** and the data **Transfer** that fulfils it — and joins them through a
single hub, the **BiomedicalConcept**.

**Schema version 0.4.0.** Based on the November DTA MVP Inventory review.
The agreement schema records USDM mapping notes and workbook cells for study,
party, visit and test fields. A test can reference its configured concept within
the study version (usdm_bc_id) separately from its terminology code (bc_id).
Proposed extensions and derived values are distinguished from direct mappings.

**Migration:** dta_version and transfer are now lists. Keep format and delimiter
with the file, use a boolean for file blinding, and group folders by environment.
Do not convert partial blinding to a boolean without reviewing the file definition.
Rename variable_format to variable_data_type; significant_digits is now test-level.
The file/folder cardinalities remain subject to review. Inventory rows 39-47
are optional proposals under suggested_controls, not required MVP checks.

## The three layers

| Layer | Purpose | Key classes |
|-------|---------|-------------|
| **Agreement** | The governance contract: what data, by whom, in what format, mapped to which visits, comprising **which tests**, in **which dataset structure**. | `DataTransferAgreement`, `Study`, `BcSelection`, `TestSpecification`, `TransferDataset`, `Party`, `TransferRequirements`, `VisitMapping` |
| **Semantic** | The bridge from a biomedical concept to concrete SDTM variables, anchored to a real, citable CDISC COSMoS specialization; plus the BC groups (data types) an agreement selects. | `BiomedicalConcept`, `BcGroup`, `DatasetSpecialization`, `VariableSpecialization` |
| **Instance** | The delivered payload: one flat record per result, typed from the inventory's agreed data structure (the LB structure, the only one agreed so far). | `Transmission`, `TransferRecord` |

`BiomedicalConcept` is the hub: USDM references it (`Activity.biomedicalConceptIds`), the
Agreement scopes it in (`BcSelection.bc_id` + the `is_used_by_dta` facet, and per-test via
`TestSpecification.bc_id`), and the payload delivers it en route to SDTM.

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

**Why both layers exist.** The SDTM derivation is a function of
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
element, renamed). `sdtm_target` annotations point at SDTM variables (transformation
target — deliberately *not* identity, because a derivation happens). On `TestSpecification`
they use the generic `--` prefix (`--TESTCD`, `--ORRESU`), resolved per domain by
`sdtm_domain`; on `TransferRecord` they name the concrete LB variables. `usdm_property`
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
| `dta.linkml.yaml` | The schema — 20 classes, 203 slots, 15 enums. |
| `agreement.example.yaml` | Agreement-layer instance, incl. data-type groups, a test specification spanning lab, ECG and imaging tests, and the data structure. Validates with `-C DataTransferAgreement`. |
| `bc_group.example.yaml` | The PK/PD data-type group from the inventory's BC_Groups sheet. Validates with `-C BcGroup`. |
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
linkml-validate -s dta.linkml.yaml -C BcGroup                bc_group.example.yaml
linkml-validate -s dta.linkml.yaml -C DatasetSpecialization  dataset_specialization.example.yaml
linkml-validate -s dta.linkml.yaml -C Transmission           transmission.example.yaml
linkml-validate -s dta.linkml.yaml -C Transmission           transmission_minimal.example.yaml
```

## What changed in v0.3.0

Built from version 2 of the DTA MVP Inventory. **Breaking:** `TestSpecification.agreement_status`
is renamed `test_tracking_status`; v0.2.0 agreements that populate it must rename the key.

| | v0.2.0 | v0.3.0 |
|---|---|---|
| Scope | lab (SDTM-LB) | dataset-agnostic: LB, EG, TU / TR / RS, PK/PD |
| Test status | `agreement_status` (provisional) | `test_tracking_status`, LAB v2 `PLBTTS` — the lab's tracking status, not a negotiation state |
| Reference ranges | *(none)* | six `TestSpecification` fields: reported low/high (text), conventional and SI low/high (numeric) |
| Test domain | implicit LB | `TestSpecification.sdtm_domain`; SDTM targets in generic `--` form |
| Data types | flat labels (`data_types`) | + `BcGroup` and `data_type_groups`: groups of BCs with sub-groups and members, shaped like USDM `BiomedicalConceptCategory` |
| LAB v2 mappings on test fields | codes, names, category | + panel (`TSTPNL`), reported / conventional / SI unit (`PLRU`, `CVU`, `SIU`) |
| Timepoint mapping | optional ("nice to have") | MVP scope |
| Classes / enums / slots | 19 / 15 / 191 | 20 / 15 / 203 |

Not applied, deliberately: **DTA Status** (MVP = N in the inventory); **BC ID stays
unenforced** although the inventory marks it mandatory, because most ECG and imaging tests
in the inventory's own sheets have no BC; no fixed value list for the tracking status,
because LAB v2 marks its list "for illustrative purposes only".

Of the two known limitations below, reference ranges are now **partly** addressed — they
can be agreed per test, but the transfer structure still carries none, and a per-test range
cannot express sex- or age-specific ranges. The standardised result is unchanged.

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
