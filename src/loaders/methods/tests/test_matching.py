"""Matching an item to its best assignment: the shared ranking, value-level ``where`` and layering."""
from __future__ import annotations

import pytest

from loaders.common import ranking
from loaders.common.where_clauses import WhereIndex, admits
from loaders.methods.library import SEED_FILE, Library
from tests.conftest import method


def assignment_for(library: Library, name: str, domain: str, where: dict | None = None) -> str | None:
    found = library.best(name, domain, where)
    return found.method if found else None


class TestRanking:
    @pytest.mark.parametrize("pattern, name, kind", [
        ("TSSEQ", "TSSEQ", (3, 0)), ("--SEQ", "TSSEQ", (2, 3)), ("--Q", "TSSEQ", (2, 1)), ("*", "TSSEQ", (1, 0)),
        ("--SEQ", "SEQ", None), ("--SEQ", "AESTDY", None), ("AESEQ", "TSSEQ", None), ("--SEQ", None, None),
    ])
    def test_name_kinds(self, pattern, name, kind):
        assert ranking.name_kind(pattern, name) == kind

    def test_exact_before_longer_suffix_before_shorter_suffix_before_star(self):
        ranks = [ranking.rank(p, "AESTDY", "AE", domains={"AE"} if p == "*" else None)
                 for p in ("AESTDY", "--STDY", "--DY", "*")]
        assert ranks == sorted(ranks, reverse=True)

    def test_domain_filters_and_exclusions(self):
        assert ranking.rank("EPOCH", "EPOCH", "TA", exclude={"TA"}) is None
        assert ranking.rank("EPOCH", "EPOCH", "SE", exclude={"TA"}) > ranking.rank("EPOCH", "EPOCH", "SE")
        assert ranking.rank("*", "ETCD", "SE", domains={"TA"}) is None

    def test_extra_ranks_between_name_and_domain_filter(self):
        with_where = ranking.rank("VSORRES", "VSORRES", "VS", extra=(1,))
        filtered = ranking.rank("VSORRES", "VSORRES", "VS", domains={"VS"}, extra=(0,))
        assert with_where > filtered

    def test_later_file_and_later_entry_win_ties(self):
        assert ranking.rank("--SEQ", "AESEQ", "AE", order=1) > ranking.rank("--SEQ", "AESEQ", "AE", order=0, position=9)


class TestWhere:
    @pytest.mark.parametrize("comparator, values, value, expected", [
        ("EQ", ("BMI",), "BMI", True), ("EQ", ("BMI",), "WEIGHT", False),
        ("IN", ("TOTAL", "SUBTOTAL"), "SUBTOTAL", True), ("IN", ("TOTAL",), "SUB", False),
        ("NE", ("BMI",), "WEIGHT", True), ("LT", ("5",), "4", False),
    ])
    def test_admits(self, comparator, values, value, expected):
        assert admits(comparator, values, value) is expected

    def test_where_index_reads_an_items_where_clause(self, dds):
        bmi = dds["itemGroups"][5]["slices"][0]["items"][0]
        assert WhereIndex(dds).of(bmi) == {"VSTESTCD": ("EQ", ("BMI",))}
        assert WhereIndex(dds).of({"OID": "IT.X"}) == {}

    def test_where_matches_eq_and_in_at_value_level_only(self, library, write):
        lib = Library.load(write(library))
        assert assignment_for(lib, "VSORRES", "VS", {"VSTESTCD": ("EQ", ("BMI",))}) == "MT.BMI"
        assert assignment_for(lib, "VSORRES", "VS", {"VSTESTCD": ("IN", ("HEIGHT", "BMI"))}) == "MT.BMI"
        assert assignment_for(lib, "VSORRES", "VS", {"VSTESTCD": ("EQ", ("WEIGHT",))}) is None
        assert assignment_for(lib, "VSORRES", "VS", {}) is None              # variable level
        assert assignment_for(lib, "VSORRES", "VS", {"VSTESTCD": ("NE", ("WEIGHT",))}) is None

    def test_every_where_value_must_be_admitted(self, library, write):
        library["assignments"][2]["where"] = {"VSTESTCD": "BMI", "VSPOS": "STANDING"}
        lib = Library.load(write(library))
        assert assignment_for(lib, "VSORRES", "VS", {"VSTESTCD": ("EQ", ("BMI",))}) is None
        assert assignment_for(lib, "VSORRES", "VS", {"VSTESTCD": ("EQ", ("BMI",)),
                                                     "VSPOS": ("EQ", ("STANDING",))}) == "MT.BMI"

    def test_where_outranks_no_where_at_equal_name_rank(self, library, write):
        library["methods"].append(method("MT.VSORRES"))
        library["assignments"].append({"name": "VSORRES", "domains": ["VS"], "method": "MT.VSORRES"})
        lib = Library.load(write(library))
        assert assignment_for(lib, "VSORRES", "VS", {"VSTESTCD": ("EQ", ("BMI",))}) == "MT.BMI"
        assert assignment_for(lib, "VSORRES", "VS", {"VSTESTCD": ("EQ", ("WEIGHT",))}) == "MT.VSORRES"


class TestSeedMatching:
    @pytest.fixture(scope="class")
    def seed(self) -> Library:
        return Library.load([SEED_FILE])

    @pytest.mark.parametrize("name, domain, expected", [
        ("TSSEQ", "TS", "MT.TSSEQ"), ("AESEQ", "AE", "MT.SEQ"), ("AESTDY", "AE", "MT.DAYCALC"),
        ("CMENDY", "CM", "MT.DAYCALC"), ("LBSTRESC", "LB", "MT.STRESC"), ("USUBJID", "DM", "MT.USUBJID"),
        ("EPOCH", "SE", "MT.EPOCH"), ("EPOCH", "TA", None), ("SESTDTC", "SE", "MT.SESTDTC"),
        ("SVSTDTC", "SV", "MT.SVSTDTC"), ("RFSTDTC", "DM", "MT.RFSTDTC"), ("AEDTC", "AE", "MT.ISO8601"),
        ("RSLNKGRP", "RS", None), ("ETCD", "SE", None),
    ])
    def test_seed_assignment(self, seed, name, domain, expected):
        assert assignment_for(seed, name, domain) == expected

    def test_seed_bmi_is_value_level(self, seed):
        assert assignment_for(seed, "VSORRES", "VS", {"VSTESTCD": ("EQ", ("BMI",))}) == "MT.BMI"
        assert assignment_for(seed, "VSORRES", "VS") is None


class TestLayering:
    def test_a_later_file_outranks_at_equal_rank_and_reports_the_shadowed_one(self, library, write):
        study = {"schemaVersion": "1.0", "methods": [method("MT.SEQ2")],
                 "assignments": [{"name": "--SEQ", "method": "MT.SEQ2"}]}
        lib = Library.load(write(library, study))
        assert assignment_for(lib, "AESEQ", "AE") == "MT.SEQ2"
        assert assignment_for(lib, "TSSEQ", "TS") == "MT.TSSEQ"        # exact still beats the suffix
        unmatched = {(a.label, a.file) for a in lib.unmatched()}
        assert ("--SEQ", "methods-0.json") in unmatched and ("--SEQ", "methods-1.json") not in unmatched

    def test_a_study_assignment_can_point_at_a_seed_method(self, library, write):
        study = {"schemaVersion": "1.0", "assignments": [{"name": "DSSEQ", "method": "MT.TSSEQ"}]}
        lib = Library.load(write(library, study))
        assert assignment_for(lib, "DSSEQ", "DS") == "MT.TSSEQ"
