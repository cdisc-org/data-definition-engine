"""The methods loader over a small DDS with the seed library: who gets which method, placeholders,
the report, and the outputs."""
from __future__ import annotations

import json

import pytest
import yaml

from loaders.common.patch import PLACEHOLDER
from loaders.methods.methods_loader import MethodsError, MethodsLoader, placeholder_oid
from tests.conftest import method


def items_by_oid(dds: dict) -> dict:
    from loaders.common import dds_io
    return {oid: item for oid, (_, _, item, _) in dds_io.define_items(dds).items()}


def methods_by_oid(dds: dict) -> dict:
    return {m["OID"]: m for m in dds["methods"]}


EXPECTED = {
    "IT.AE.USUBJID": "MT.USUBJID", "IT.AE.AESEQ": "MT.SEQ", "IT.AE.AESTDY": "MT.DAYCALC",
    "IT.AE.AEDTC": "MT.ISO8601", "IT.AE.AEENRF": "MT.AE.AEENRF", "IT.TS.TSSEQ": "MT.TSSEQ",
    "IT.SV.SVSTDTC": "MT.SVSTDTC", "IT.SE.EPOCH": "MT.EPOCH", "IT.LB.LBSTRESC": "MT.LB.CUSTOM",
    "IT.VS.VSORRES.BMI": "MT.BMI", "IT.QS.QSSTRESN": "MT.STRESN", "IT.QS.QSSTRESN.TOTAL": "MT.STRESN",
}


class TestAssignment:
    def test_every_derived_item_gets_its_method(self, dds, run):
        out = run(dds).dds
        found = {oid: item.get("method") for oid, item in items_by_oid(out).items() if item.get("method")}
        assert found == EXPECTED

    def test_only_derived_items_get_a_method(self, dds, run):
        out = items_by_oid(run(dds).dds)
        for oid in ("IT.AE.STUDYID", "IT.AE.AESTDTC", "IT.SV.VISITDY", "IT.VS.VSORRES", "IT.VS.VSORRES.WEIGHT"):
            assert "method" not in out[oid], oid

    def test_a_protocol_visitdy_never_reaches_the_dy_assignment(self, dds, run):
        assert "method" not in items_by_oid(run(dds).dds)["IT.SV.VISITDY"]

    def test_crf_items_are_not_define_items(self, dds, run):
        form = run(dds).dds["itemGroups"][-1]
        assert "method" not in form["items"][0]

    def test_an_existing_method_is_kept(self, dds, run):
        loader = run(dds)
        assert loader.report.kept == {"IT.LB.LBSTRESC": "MT.LB.CUSTOM"}
        assert methods_by_oid(loader.dds)["MT.LB.CUSTOM"]["name"] == "Sponsor LBSTRESC"

    def test_an_existing_placeholder_string_is_replaced(self, dds, run):
        dds["itemGroups"][0]["items"][2]["method"] = PLACEHOLDER
        assert items_by_oid(run(dds).dds)["IT.AE.AESEQ"]["method"] == "MT.SEQ"

    def test_a_shared_method_lands_once_with_its_signature_and_without_basis(self, dds, run):
        dds["itemGroups"].append({"OID": "IG.CM", "name": "CM", "domain": "CM", "items": [
            {"OID": "IT.CM.CMSEQ", "name": "CMSEQ", "origin": [{"type": "Derived", "source": "Sponsor"}]}]})
        out = run(dds).dds
        oids = [m["OID"] for m in out["methods"]]
        assert oids.count("MT.SEQ") == 1 and len(oids) == len(set(oids))
        seq = methods_by_oid(out)["MT.SEQ"]
        assert "basis" not in seq
        assert seq["signature"]["returnValues"][0]["OID"] == "RV.SEQ.SEQ"

    def test_an_input_method_with_a_library_oid_is_not_replaced(self, dds, run):
        dds["methods"].append(method("MT.SEQ", name="The sponsor's own SEQ"))
        del dds["methods"][-1]["basis"]
        out = run(dds).dds
        assert methods_by_oid(out)["MT.SEQ"]["name"] == "The sponsor's own SEQ"
        assert [m["OID"] for m in out["methods"]].count("MT.SEQ") == 1


class TestPlaceholders:
    @pytest.mark.parametrize("item_oid, expected", [
        ("IT.AE.AEENRF", "MT.AE.AEENRF"), ("IT.VS.VSORRES.BMI", "MT.VS.VSORRES.BMI"),
        ("IT.LB.LBORRES.ALT ULN", "MT.LB.LBORRES.ALT-ULN"), ("ITX.AE.X", "MT.ITX.AE.X"),
    ])
    def test_placeholder_oids_follow_the_define_generator(self, item_oid, expected):
        assert placeholder_oid(item_oid) == expected

    def test_an_unmatched_derived_item_gets_a_placeholder_method(self, dds, run):
        loader = run(dds)
        placeholder = methods_by_oid(loader.dds)["MT.AE.AEENRF"]
        assert placeholder == {"OID": "MT.AE.AEENRF", "name": "Algorithm to derive AEENRF", "type": "Computation",
                               "description": PLACEHOLDER, "signature": {"parameters": [], "returnValues": []}}
        assert loader.report.placeholders == {"MT.AE.AEENRF": ["IT.AE.AEENRF"]}
        assert loader.open_items() == {"placeholder methods": 1}


class TestReport:
    def test_both_levels_are_reported(self, dds, run):
        assert run(dds).report.both_levels == {
            "QS.QSSTRESN": {"variable": "IT.QS.QSSTRESN", "valueLevel": ["IT.QS.QSSTRESN.TOTAL"]}}

    def test_report_file(self, dds, run, tmp_path):
        loader = run(dds)
        loader.write_report(str(tmp_path / "methods-report.yaml"))
        report = yaml.safe_load((tmp_path / "methods-report.yaml").read_text(encoding="utf-8"))
        assert list(report) == ["assigned", "placeholders", "kept", "bothLevels", "unmatched", "unreferenced"]
        assert report["assigned"]["MT.STRESN"] == {"assignments": ["--STRESN (sdtm_methods.json)"],
                                                   "items": ["IT.QS.QSSTRESN", "IT.QS.QSSTRESN.TOTAL"]}
        assert "RFSTDTC (sdtm_methods.json) -> MT.RFSTDTC" in report["unmatched"]
        assert report["unreferenced"] == []

    def test_an_input_method_no_item_names_is_unreferenced(self, dds, run):
        dds["methods"].append({**method("MT.UNUSED"), "basis": None})
        del dds["methods"][-1]["basis"]
        assert run(dds).report.unreferenced == ["MT.UNUSED"]

    def test_summary_counts(self, dds, run):
        loader = run(dds)
        assert loader.report.derived == 12           # 10 assigned, 1 kept, 1 placeholder
        assert loader.report.assigned_items == 10 and len(loader.report.assigned) == 9
        text = loader.summary()
        assert "assigned from library .... 10 (9 methods)" in text
        assert "placeholder methods ...... 1 (1 items)" in text


class TestOutputs:
    def test_dds_out_must_differ_from_dds_in(self, tmp_path, dds):
        path = tmp_path / "dds.json"
        path.write_text(json.dumps(dds), encoding="utf-8")
        with pytest.raises(MethodsError, match="must differ"):
            MethodsLoader(str(path), str(path))

    def test_an_unusable_library_is_refused(self, tmp_path, dds, write, library):
        library["assignments"].append({"name": "X", "method": "MT.NONE"})
        path = tmp_path / "dds.json"
        path.write_text(json.dumps(dds), encoding="utf-8")
        with pytest.raises(MethodsError, match="MT.NONE"):
            MethodsLoader(str(path), str(tmp_path / "out.json"), write(library))

    def test_two_runs_from_one_input_are_identical(self, dds, run, tmp_path):
        first = run(dds)
        first.save()
        one = (tmp_path / "dds-out.json").read_text(encoding="utf-8")
        second = run(dds)
        second.save()
        assert (tmp_path / "dds-out.json").read_text(encoding="utf-8") == one

    def test_a_wrapped_dds_is_written_back_wrapped(self, dds, run, tmp_path):
        loader = run({"metaDataVersion": dds})
        loader.save()
        written = json.loads((tmp_path / "dds-out.json").read_text(encoding="utf-8"))
        assert list(written) == ["metaDataVersion"]

    def test_a_dds_without_methods_gets_the_list(self, dds, run):
        del dds["methods"]
        dds["itemGroups"][4]["items"][0].pop("method")
        assert "MT.STRESC" in methods_by_oid(run(dds).dds)
