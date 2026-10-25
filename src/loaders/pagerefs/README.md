# loaders/pagerefs — Stage E: aCRF page references into Define-XML Origin

An enrichment loader (DDS in, DDS out), run after the CRF loader, the CRF generator and
crfutils `crfpdf`. It reads the `acrf.pagerefs.json` crfpdf writes beside the annotated CRF
and writes each Define item's `origin` — type, source and the aCRF pages — into a new DDS,
which the Define generator turns into `def:Origin` with `def:DocumentRef/def:PDFPageRef`.

Origin with pages cannot exist earlier: the Define loader has no CRF and the CRF loader has
no PDF. Keeping it a loader keeps the generators reading only the DDS.

## Running it

From `src/`:

```bash
python -m loaders.pagerefs \
  --dds_in   ../output/NCT01797120/dds-crf.json \
  --pagerefs ../output/NCT01797120/acrf.pagerefs.json \
  --crf      ../output/NCT01797120/crf-2.0.xml \
  --dds_out  ../output/NCT01797120/dds-origin.json \
  --patch_file ../data/protocols/NCT01797120/origin-review.yaml \
  [--apply_patch ../data/protocols/NCT01797120/origin-review.yaml] [--validate]
```

`--dds_in` is the CRF-enriched DDS the CRF was generated from; `--dds_out` must be a new
file, so a re-run starts from the same input and replaces the CRF origins rather than
stacking them. The pipeline (`src/pipeline`) runs it as stage E.

## Identity checks

The run stops (exit 1, nothing written) unless the pagerefs file belongs to this DDS and CRF:

- `schema_version` is at least 2.1 (crfutils with `define_items`);
- `study.oid` / `study.mdv_oid` equal the DDS `studyOID` / `OID`;
- `file_oid` / `creation_datetime` equal the DDS `fileOID` / `creationDateTime` (the CRF
  generator copies them from the DDS header);
- `crf_sha256` equals the sha256 of `--crf`. A CRF regenerated after a refinement change keeps
  its FileOID and CreationDateTime, so only the hash shows the pagerefs file is stale;
- the PDF name equals the DDS `annotatedCRFs[0].href` (`acrf.pdf`).

## Which origin an item gets

1. a pin in `origin-review.yaml`, by item OID, ValueListDef OID (`VL.LB.LBORRES`) or
   `DATASET.VARIABLE`;
2. the CRF evidence crfpdf files under the item's OID (`define_items`, from the CRF's
   `SDTMItemOIDs` aliases): it replaces the Define loader's origin. A replaced origin that was
   not a placeholder is listed under `replaced`; a placeholder or a missing origin is filled;
3. for an item the CRF names no OID for, the key recipe of the crfutils README: the
   variable-level roll-up (`origins["VS.VSPOS"]`), or for a value-level item the CRF targets
   whose conditions its where clause admits (EQ equal, IN listed, NE different);
4. otherwise the Define loader's origin stays.

Origins are written as `{type, source, documents: [{leafID, pages}]}` (DDS schema
`Origin.documents` / `DocumentReference.pages`; a DocumentReference needs no OID). Pages go on
every CRF-evidenced origin: Collected, Protocol (test codes, prefilled values) and Derived.
Derived origins get no description, so the Define generator's post-processing adds its
MethodDef placeholder. A variable whose value-level items carry origins keeps none of its own.

## origin-review.yaml

| Section | Lists |
|---|---|
| `replaced` | Define-loader origins the CRF replaced (LBORRES Collected/Vendor -> Collected/Investigator) |
| `noPages` | Collected/Investigator Define items with no aCRF pages |
| `unknownOids` | pagerefs OIDs the DDS does not have |
| `unpaired` | crfpdf's `define_oid_unpaired` warnings |
| `pins` | extra pins by item OID, ValueListDef OID or `DATASET.VARIABLE` |

A `pin` is `crf` (accept the CRF origin), `stageA` (keep the Define loader's), `ack`
(acknowledged), or `{type, source}` (that origin, with the CRF pages when the CRF gives the
same type and source). Unanswered pins are open items; answers survive regeneration.

## Tests

```bash
cd src/loaders/pagerefs && pytest
```

22 tests, no network: the identity checks, the precedence, the key recipe with IN lists,
value-list pins, the review file round trip, an identical second run, and the command.
