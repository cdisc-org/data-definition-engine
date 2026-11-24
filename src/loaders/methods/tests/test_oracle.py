"""The methods loader against CDISC define.xml files and a hand-built DDS (methods plan M5).

``fixtures/README.md`` says where each fixture comes from. The bar, from the plan:

* SDTM-MSG v2.0: the seed alone gives 77 of the 91 Derived items MSG's own method; the seed plus
  the study file ``msg_v2_methods.json`` gives all 91.
* CDISC 2019 Define-XML 2.1 SDTM example (the second oracle): what the seed gives each of its 49
  Derived items, pinned item by item.
* ``dm_bmi_dates_dds.json`` (hand-built): DM, value-level BMI and an ISO 8601 --DTC, which neither
  NCT01797120 nor MSG makes Derived, all from the seed.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from loaders.common import dds_io
from loaders.common.define_patch import is_derived, placeholder_oid
from loaders.methods.library import SEED_FILE

FIXTURES = Path(__file__).resolve().parent / "fixtures"
STUDY_FILE = str(FIXTURES / "msg_v2_methods.json")


def expected(prefix: str) -> dict:
    return json.loads((FIXTURES / f"{prefix}_expected.json").read_text(encoding="utf-8"))


def fixture(prefix: str) -> dict:
    return json.loads((FIXTURES / f"{prefix}_dds.json").read_text(encoding="utf-8"))


def methods_of(loader) -> dict[str, str | None]:
    """Item OID -> the method the loader gave it, for every Derived item."""
    return {oid: item.get("method") for oid, (_, _, item, _) in dds_io.define_items(loader.dds).items()
            if is_derived(item)}


def text(value: str) -> str:
    return " ".join(value.split())


# -- SDTM-MSG v2.0 ------------------------------------------------------------------
#: the 10 items the seed alone gives one of its shared methods: MSG -> seed
MSG_DIFFERENT = {
    "IT.FT.FTSTRESN": ("MT.FTSTRESN", "MT.STRESN"),          # same algorithm, separate MSG OID
    "IT.QSPH.QSSTRESN": ("MT.QSSTRESN", "MT.STRESN"),        # same algorithm, separate MSG OID
    "IT.QSSL.QSSTRESN": ("MT.QSSTRESN", "MT.STRESN"),
    "IT.DI.DISEQ": ("MT.DISEQ", "MT.SEQ"),                   # per device, not per subject
    "IT.LB.LBSTRESC": ("MT.LBSTRESC", "MT.STRESC"),          # the seed's MT.STRESC generalizes it
    "IT.VS.VSSTRESC": ("MT.VSSTRESC", "MT.STRESC"),          # conversion factors
    "IT.RS.RSSTRESC": ("MT.RSSTRESC", "MT.STRESC"),          # scoring
    "IT.QSSL.QSSTRESC": ("MT.QSSTRESC_SL", "MT.STRESC"),     # scoring
    "IT.QSPH.QSSTRESC.1": ("MT.QSSTRESC_PH", "MT.STRESC"),   # scoring
    "IT.QSPH.QSSTRESC.2": ("MT.QSSTRESC_PH_10_11", "MT.STRESC"),
}
#: study-specific: the seed alone leaves a placeholder
MSG_PLACEHOLDERS = {"IT.AE.AEENTPT", "IT.CM.CMENTPT", "IT.EX.EXDOSE", "IT.IE.IEORRES"}
#: the seed's wording differs from MSG's on purpose (data/methods/README.md: "corrected")
CORRECTED = {"MT.TSSEQ", "MT.SESTDTC"}


@pytest.fixture(scope="module")
def msg_seed(tmp_path_factory):
    return _process("msg_v2", None, tmp_path_factory.mktemp("seed"))


@pytest.fixture(scope="module")
def msg_study(tmp_path_factory):
    return _process("msg_v2", [str(SEED_FILE), STUDY_FILE], tmp_path_factory.mktemp("study"))


def _process(prefix: str, libraries, tmp: Path):
    from loaders.methods.methods_loader import MethodsLoader

    loader = MethodsLoader(str(FIXTURES / f"{prefix}_dds.json"), str(tmp / "dds-out.json"), libraries)
    loader.process()
    return loader


class TestMsgV2:
    def test_the_fixture_holds_msg_s_91_derived_items_with_their_methods_stripped(self):
        dds, msg = fixture("msg_v2"), expected("msg_v2")
        assert len(msg["derived"]) == 91 and all(msg["derived"].values())
        assert not any("method" in item for _, _, item, _ in dds_io.define_items(dds).values())
        assert dds["methods"] == []

    def test_the_seed_alone_matches_77_of_91(self, msg_seed):
        msg, got = expected("msg_v2")["derived"], methods_of(msg_seed)
        assert set(got) == set(msg)
        same = {oid for oid in msg if got[oid] == msg[oid]}
        assert len(same) == 77
        assert {oid: (msg[oid], got[oid]) for oid in MSG_DIFFERENT} == MSG_DIFFERENT
        assert {oid: got[oid] for oid in MSG_PLACEHOLDERS} == {oid: placeholder_oid(oid) for oid in MSG_PLACEHOLDERS}
        assert set(msg) - same == set(MSG_DIFFERENT) | MSG_PLACEHOLDERS
        assert set(msg_seed.report.placeholders) == {placeholder_oid(oid) for oid in MSG_PLACEHOLDERS}

    def test_the_seed_plus_the_study_file_matches_all_91(self, msg_study):
        msg, got = expected("msg_v2")["derived"], methods_of(msg_study)
        assert got == msg
        assert msg_study.report.placeholders == {}

    def test_the_methods_are_msg_s_29_with_msg_s_wording(self, msg_study):
        msg_methods = expected("msg_v2")["methods"]
        written = {m["OID"]: text(m["description"]) for m in msg_study.dds["methods"]}
        assert set(written) == set(msg_methods) and len(written) == 29
        differ = {oid for oid in written if written[oid] != msg_methods[oid]}
        assert differ == CORRECTED

    def test_a_method_msg_gives_an_item_that_is_not_derived_is_not_assigned(self, msg_study):
        assert expected("msg_v2")["notDerived"] == {"IT.TA.EPOCH": "MT.EPOCH"}
        _, _, ta_epoch, _ = dds_io.define_items(msg_study.dds)["IT.TA.EPOCH"]
        assert ta_epoch["origin"][0]["type"] == "Protocol" and "method" not in ta_epoch

    def test_two_datasets_of_one_domain_are_not_one_variable_at_two_levels(self, msg_study):
        """QSPH and QSSL are both domain QS: QSSL.QSSTRESC is not the parent of QSPH's value list."""
        assert msg_study.report.both_levels == {}

    def test_the_study_file_only_adds_to_the_seed(self):
        study = json.loads(Path(STUDY_FILE).read_text(encoding="utf-8"))
        seed = json.loads(SEED_FILE.read_text(encoding="utf-8"))
        assert not {m["OID"] for m in study["methods"]} & {m["OID"] for m in seed["methods"]}
        assert len(study["methods"]) == 13
        assert all(m.get("signature", {}).get("returnValues") for m in study["methods"])


# -- CDISC 2019 Define-XML 2.1 SDTM example -----------------------------------------------
#: the example's per-domain method -> the seed's shared method for the same algorithm
CDISC2019_SAME_ALGORITHM = {
    "MT.EXSTDY": "MT.DAYCALC", "MT.EXENDY": "MT.DAYCALC", "MT.ECENDY": "MT.DAYCALC",
    "MT.LBDY": "MT.DAYCALC", "MT.VSDY": "MT.DAYCALC", "MT.XSDY": "MT.DAYCALC", "MT.XXDY": "MT.DAYCALC",
    "MT.VSSTRESC": "MT.STRESC", "MT.XSSTRESC": "MT.STRESC", "MT.XXSTRESC": "MT.STRESC",
    "MT.VSSTRESN": "MT.STRESN", "MT.XSSTRESN": "MT.STRESN", "MT.XXSTRESN": "MT.STRESN",
}
#: a different algorithm: the example derives BMI in VSSTRESN; the seed's MT.BMI is on VSORRES
CDISC2019_DIFFERENT = {"IT.VS.VSSTRESN.BMI": ("MT.BMISN", "MT.STRESN")}
#: not in the seed: --BLFL (the seed follows MSG's --LOBXFL), treatment and dose, RDOMAIN, QVAL;
#: EC.EXDOSE and EC.EXDOSU are Derived without a method in the example itself
CDISC2019_PLACEHOLDERS = {
    "IT.EC.EXTRT", "IT.EC.EXDOSE", "IT.EC.EXDOSU", "IT.EX.EXTRT", "IT.EX.EXDOSE", "IT.EX.EXDOSU",
    "IT.LB.LBBLFL", "IT.VS.VSBLFL", "IT.XS.XSBLFL", "IT.XX.XXBLFL",
    "IT.SUPPDM.RDOMAIN", "IT.SUPPVS.RDOMAIN", "IT.SUPPDM.QVAL.SAFETY", "IT.SUPPVS.QVAL.VSCLSIG",
}


class TestCdisc2019:
    @pytest.fixture(scope="class")
    def loader(self, tmp_path_factory):
        return _process("cdisc2019", None, tmp_path_factory.mktemp("cdisc2019"))

    def test_the_seed_gives_each_derived_item_the_pinned_method(self, loader):
        source, got = expected("cdisc2019")["derived"], methods_of(loader)
        assert set(got) == set(source) and len(source) == 49
        want = {}
        for oid, method in source.items():
            if oid in CDISC2019_PLACEHOLDERS:
                want[oid] = placeholder_oid(oid)
            elif oid in CDISC2019_DIFFERENT:
                want[oid] = CDISC2019_DIFFERENT[oid][1]
            else:
                want[oid] = CDISC2019_SAME_ALGORITHM.get(method, method)
        assert got == want

    def test_20_same_14_same_algorithm_1_different_14_placeholders(self, loader):
        source, got = expected("cdisc2019")["derived"], methods_of(loader)
        same = [oid for oid in source if got[oid] == source[oid]]
        same_algorithm = [oid for oid in source if source[oid] in CDISC2019_SAME_ALGORITHM]
        assert (len(same), len(same_algorithm), len(CDISC2019_DIFFERENT), len(CDISC2019_PLACEHOLDERS)) \
            == (20, 14, 1, 14)
        assert sorted({source[oid] for oid in same}) == [
            "MT.AGE", "MT.RFENDTC", "MT.RFSTDTC", "MT.SEQ", "MT.TSSEQ", "MT.USUBJID"]

    def test_bmi_is_derived_at_both_levels(self, loader):
        assert loader.report.both_levels == {
            "VS.VSSTRESN": {"variable": "IT.VS.VSSTRESN", "valueLevel": ["IT.VS.VSSTRESN.BMI"]}}


# -- the hand-built fixture: DM, value-level BMI, an ISO 8601 --DTC ---------------------------
DM_BMI_DATES = {
    "IT.DM.USUBJID": "MT.USUBJID", "IT.DM.RFSTDTC": "MT.RFSTDTC", "IT.DM.RFENDTC": "MT.RFENDTC",
    "IT.DM.RFXSTDTC": "MT.RFXSTDTC", "IT.DM.RFXENDTC": "MT.RFXENDTC", "IT.DM.RFICDTC": "MT.RFICDTC",
    "IT.DM.RFPENDTC": "MT.RFPENDTC", "IT.DM.DTHFL": "MT.DTHFL", "IT.DM.AGE": "MT.AGE",
    "IT.VS.USUBJID": "MT.USUBJID", "IT.VS.VSSEQ": "MT.SEQ", "IT.VS.VSORRES.BMI": "MT.BMI",
    "IT.VS.VSSTRESC": "MT.STRESC", "IT.VS.VSSTRESN": "MT.STRESN", "IT.VS.VSLOBXFL": "MT.LOBXFL",
    "IT.VS.EPOCH": "MT.EPOCH", "IT.VS.VSDTC": "MT.ISO8601", "IT.VS.VSDY": "MT.DAYCALC",
}


class TestDmBmiDates:
    @pytest.fixture(scope="class")
    def loader(self, tmp_path_factory):
        return _process("dm_bmi_dates", None, tmp_path_factory.mktemp("dm_bmi_dates"))

    def test_every_derived_item_gets_its_seed_method(self, loader):
        assert methods_of(loader) == DM_BMI_DATES
        assert loader.report.placeholders == {}

    def test_bmi_attaches_at_value_level_only(self, loader):
        items = dds_io.define_items(loader.dds)
        assert "method" not in items["IT.VS.VSORRES"][2]
        assert "method" not in items["IT.VS.VSORRES.WEIGHT"][2]

    def test_with_msg_every_seed_method_is_assigned(self, loader, msg_seed):
        seed = {m["OID"] for m in json.loads(SEED_FILE.read_text(encoding="utf-8"))["methods"]}
        assigned = set(methods_of(loader).values()) | set(methods_of(msg_seed).values())
        assert seed - assigned == set()
