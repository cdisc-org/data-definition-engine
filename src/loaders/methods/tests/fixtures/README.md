# Methods loader validation fixtures

The fixtures behind `test_oracle.py` and `test_define_output.py` (methods plan M5). Two are oracles
built from CDISC define.xml files: the loader runs over a DDS with every method reference stripped,
and its result is compared with the source's `ItemRef/@MethodOID`. The third is hand-built and covers
what neither NCT01797120 nor MSG makes Derived.

| Files | Source | Derived items |
|---|---|---|
| `msg_v2_dds.json`, `msg_v2_expected.json` | SDTM-MSG v2.0 Sample Submission Package, `m5/datasets/cdiscpilot01/tabulations/sdtm/define.xml` (CDISC MSG v2 Team, 2021-01-24) | 91, each with a method |
| `msg_v2_methods.json` | The study file: the 13 MSG methods the seed does not ship, and the assignments for the 14 items the seed alone gets wrong | — |
| `cdisc2019_dds.json`, `cdisc2019_expected.json` | CDISC Define-XML 2.1 package (2019), `examples/DefineXML-2-1-SDTM/defineV21-SDTM.xml` | 49; 2 have no method in the source (EC.EXDOSE, EC.EXDOSU) |
| `dm_bmi_dates_dds.json` | Hand-built: DM with the RF\* dates, AGE, DTHFL and RFICDTC Derived; VS with value-level BMI and VSDTC Derived from collected date and time | 18 |

## Rebuilding an oracle

```bash
cd src/loaders/methods/tests/fixtures
python oracle_from_define.py <path>/define.xml msg_v2
python oracle_from_define.py <path>/defineV21-SDTM.xml cdisc2019
```

`oracle_from_define.py` keeps:
- the datasets;
- their variables (name, data type, length, description, origin type and source);
- the value lists that hold a Derived item or a method, with their where clauses;
- the standards.

It writes no method references. Two adjustments make the source look like a DDE DDS:
- **Shared items:** an ItemDef several datasets share (the 2019 example's `IT.USUBJID`) becomes one item per dataset, `IT.<dataset>.<name>`.
- **Value-level names:** a value-level item takes its variable's name. The 2019 example writes `VSSTRESN6` and `RACE1`.

## Results

**SDTM-MSG v2.0.**
- **The seed alone** gives 77 of the 91 Derived items MSG's own method.
  - **10 get a shared method:** FTSTRESN and QSSTRESN (MSG uses separate OIDs for the same algorithm), DISEQ, and the scoring-specific LBSTRESC, VSSTRESC, RSSTRESC and QSSTRESC ×3.
  - **4 become placeholders:** AEENTPT, CMENTPT, EXDOSE and IEORRES.
- **The seed plus `msg_v2_methods.json`** gives all 91, with MSG's 29 methods in MSG's wording. The exceptions are MT.TSSEQ and MT.SESTDTC, which the seed corrects (`data/methods/README.md`).
- **TA.EPOCH** is Protocol, so it gets no method, although MSG gives it MT.EPOCH.

**CDISC 2019 example.** The seed gives:
- **20 items the same method:** USUBJID ×9, --SEQ ×7, TSSEQ, RFSTDTC, RFENDTC and AGE. The example's MT.AGE anchors on the screening date where the seed's uses RFSTDTC.
- **14 the same algorithm under a shared OID:** per-domain --DY, --STRESC and --STRESN become MT.DAYCALC, MT.STRESC and MT.STRESN.
- **1 a different method:** VSSTRESN where VSTESTCD = BMI gets MT.STRESN. The example derives BMI there; the seed's MT.BMI is on VSORRES.
- **14 placeholders:** --BLFL ×4 (the seed follows MSG's --LOBXFL), EXTRT, EXDOSE and EXDOSU in EX and EC, RDOMAIN ×2, and QVAL for SAFETY and VSCLSIG.

**Hand-built.** All 18 Derived items get a seed method. Together with MSG, every one of the 22 seed methods is assigned at least once.

**define.xml.** Each fixture's result also goes through the Define generator, the Define-XML 2.1 XSD and the defineutils conformance rules (`test_define_output.py`).
- **The hand-built fixture** passes all 197 rules defineutils evaluates.
- **The MSG oracle** passes the XSD and every rule about methods and their leaves. Rules 55 and 155 fail because the value lists it leaves out are missing; rule 124 because MSG names its standard `STDTMIG`, which the generator does not write; and the extra check X4 because Predecessor descriptions are not carried.

**Found on the way.** QSPH and QSSL are both domain QS. Before M5 the loader matched a value list to its parent by domain, so it reported QSSL.QSSTRESC and QSPH's value-level QSSTRESC as one variable Derived at both levels. It now looks up the parent in the value list's own dataset.
