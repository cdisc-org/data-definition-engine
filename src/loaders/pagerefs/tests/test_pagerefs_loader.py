"""Tests for Stage E: identity checks, the origin precedence, pins, the key recipe and idempotency."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from loaders.common.patch import PLACEHOLDER
from loaders.pagerefs.pagerefs_loader import PagerefsError, PagerefsLoader


def _run(files, dds=None, refs=None, review=None):
    dds_in, refs_in, crf, out = files(dds, refs)
    loader = PagerefsLoader(dds_in, refs_in, crf, out)
    if review is not None:
        loader.load_review(review)
    loader.process()
    return loader


def _items(dds):
    found = {}
    for group in dds["itemGroups"]:
        for item in group.get("items") or []:
            found[item["OID"]] = item
        for slice_ in group.get("slices") or []:
            for item in slice_.get("items") or []:
                found[item["OID"]] = item
    return found


class TestIdentity:
    @pytest.mark.parametrize("edit, message", [
        (lambda r: r.update(schema_version="2.0"), "schema_version 2.0 is older than 2.1"),
        (lambda r: r["study"].update(oid="ODM.OTHER"), "study OID"),
        (lambda r: r["study"].update(mdv_oid="MDV.OTHER"), "MetaDataVersion OID"),
        (lambda r: r.update(file_oid="ODM.OTHER"), "FileOID"),
        (lambda r: r.update(creation_datetime="2020-01-01"), "CreationDateTime"),
        (lambda r: r.update(crf_sha256="0" * 64), "made from another CRF"),
        (lambda r: r.update(pdf_file="/out/crf_acrf.pdf"), "the PDF is 'crf_acrf.pdf'"),
    ])
    def test_each_mismatch_stops_the_run(self, files, pagerefs, edited, edit, message):
        refs = edited(pagerefs)
        edit(refs)
        with pytest.raises(PagerefsError, match="does not belong") as excinfo:
            _run(files, refs=refs)
        assert message in str(excinfo.value)

    def test_the_output_must_be_a_new_file(self, files):
        dds_in, refs_in, crf, _ = files()
        with pytest.raises(PagerefsError, match="must differ"):
            PagerefsLoader(dds_in, refs_in, crf, dds_in)


class TestPrecedence:
    def test_crf_evidence_replaces_and_reports_a_real_origin(self, files):
        loader = _run(files)
        items = _items(loader.dds)
        assert items["IT.LB.LBORRES.ALT"]["origin"] == [
            {"type": "Collected", "source": "Investigator", "documents": [{"leafID": "LF.acrf", "pages": [12, 13]}]}]
        assert loader.review["replaced"]["IT.LB.LBORRES.ALT"] == {
            "stageA": "Collected/Vendor", "crf": "Collected/Investigator p. 12 13", "pin": PLACEHOLDER}
        # AEENRF: Assigned in the Define, Derived from the CRF, with its page and no description
        assert items["IT.AE.AEENRF"]["origin"] == [
            {"type": "Derived", "source": "Sponsor", "documents": [{"leafID": "LF.acrf", "pages": [20]}]}]
        assert "IT.AE.AEENRF" in loader.review["replaced"]

    def test_placeholder_and_missing_origins_are_filled_not_reported(self, files):
        loader = _run(files)
        items = _items(loader.dds)
        assert items["IT.VS.VSDTC"]["origin"][0]["documents"][0]["pages"] == [5, 6]
        assert items["IT.AE.AETERM"]["origin"][0]["type"] == "Collected"
        assert not {"IT.VS.VSDTC", "IT.AE.AETERM"} & set(loader.review["replaced"])
        assert loader.report["filled"] == 2

    def test_the_same_origin_with_pages_is_not_a_replacement(self, files):
        loader = _run(files)
        assert "IT.VS.VSORRES.SYSBP" not in loader.review["replaced"]
        assert _items(loader.dds)["IT.VS.VSORRES.SYSBP"]["origin"][0]["documents"][0]["pages"] == [5]

    def test_items_the_crf_does_not_name_keep_their_origin(self, files):
        assert _items(_run(files).dds)["IT.AE.AESER"]["origin"] == [{"type": "Collected", "source": "Investigator"}]


class TestKeyRecipe:
    def test_variable_level_roll_up(self, files):
        origin = _items(_run(files).dds)["IT.VS.VSPOS"]["origin"]
        assert origin == [{"type": "Collected", "source": "Investigator",
                           "documents": [{"leafID": "LF.acrf", "pages": [5, 6]}]}]

    def test_value_level_where_clause_admits_in_lists(self, files):
        # DIABP's where clause is VSTESTCD EQ DIABP and VSPOS IN (PRONE, SEMI-RECUMBENT, SITTING);
        # the CRF target has VSTESTCD = DIABP and the concept condition VSPOS = SITTING
        loader = _run(files)
        assert _items(loader.dds)["IT.VS.VSORRES.DIABP"]["origin"][0]["documents"][0]["pages"] == [6]
        assert loader.report["fallbackOrigins"] == 2

    def test_a_concept_value_the_where_clause_does_not_admit_matches_nothing(self, files, pagerefs, edited):
        refs = edited(pagerefs)
        refs["annotations"][0]["targets"][0]["where"][1]["values"] = ["SUPINE"]
        origin = _items(_run(files, refs=refs).dds)["IT.VS.VSORRES.DIABP"]["origin"]
        assert origin == [{"type": "Collected", "source": "Investigator"}]

    def test_a_variable_with_a_value_list_keeps_no_origin_of_its_own(self, files, dds2, edited):
        dds = edited(dds2)
        dds["itemGroups"][0]["items"][0]["origin"] = [{"type": "Collected", "source": "Investigator"}]
        assert "origin" not in _items(_run(files, dds=dds).dds)["IT.VS.VSORRES"]


class TestReview:
    def test_no_pages_unknown_oids_and_unpaired(self, files):
        loader = _run(files)
        assert list(loader.review["noPages"]) == ["IT.AE.AESER"]
        assert list(loader.review["unknownOids"]) == ["IT.XX.UNKNOWN"]
        assert len(loader.review["unpaired"]) == 1
        # ALT, AST, AEENRF, and VSTESTCD (Assigned in the Define, Protocol on the CRF)
        assert set(loader.review["replaced"]) == {"IT.LB.LBORRES.ALT", "IT.LB.LBORRES.AST", "IT.AE.AEENRF",
                                                  "IT.VS.VSTESTCD"}
        assert loader.open_items() == {"replaced": 4, "noPages": 1, "unknownOids": 1, "unpaired": 1}

    def test_pins_and_a_value_list_pin(self, files, tmp_path):
        loader = _run(files)
        path = tmp_path / "origin-review.yaml"
        loader.write_review(str(path))
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert content["replaced"]["IT.AE.AEENRF"]["pin"] == PLACEHOLDER and content["pins"] == {}
        content["replaced"]["IT.AE.AEENRF"]["pin"] = "crf"
        content["noPages"]["IT.AE.AESER"]["pin"] = "ack"
        content["unknownOids"]["IT.XX.UNKNOWN"]["pin"] = "ack"
        # one pin for the whole LB value list: the labs come from a central lab
        content["pins"] = {"VL.LB.LBORRES": {"type": "Collected", "source": "Vendor"}}
        path.write_text(yaml.safe_dump(content), encoding="utf-8")

        rerun = _run(files, review=str(path))
        items = _items(rerun.dds)
        for oid in ("IT.LB.LBORRES.ALT", "IT.LB.LBORRES.AST"):
            assert items[oid]["origin"] == [{"type": "Collected", "source": "Vendor"}]
            # the value-list pin answers each entry it covers
            assert rerun.review["replaced"][oid]["pin"] == {"type": "Collected", "source": "Vendor"}
        assert items["IT.AE.AEENRF"]["origin"][0]["type"] == "Derived"
        assert rerun.open_items() == {"replaced": 1, "noPages": 0, "unknownOids": 0, "unpaired": 1}

        # answers survive the file being regenerated
        rerun.write_review(str(path))
        again = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert again["replaced"]["IT.AE.AEENRF"]["pin"] == "crf"
        assert again["pins"]["VL.LB.LBORRES"] == {"type": "Collected", "source": "Vendor"}

    def test_a_stage_a_pin_keeps_the_define_origin(self, files, tmp_path):
        path = tmp_path / "r.yaml"
        path.write_text(yaml.safe_dump({"pins": {"LB.LBORRES": "stageA"}}), encoding="utf-8")
        items = _items(_run(files, review=str(path)).dds)
        assert items["IT.LB.LBORRES.ALT"]["origin"] == [{"type": "Collected", "source": "Vendor"}]


class TestOutputs:
    def test_a_second_run_from_the_same_dds_writes_an_identical_file(self, files, tmp_path):
        first = _run(files)
        first.save()
        one = Path(first.dds_out).read_bytes()
        second = _run(files)
        second.save()
        assert Path(second.dds_out).read_bytes() == one

    def test_the_command(self, files, tmp_path):
        dds_in, refs_in, crf, out = files()
        review = tmp_path / "origin-review.yaml"
        src = Path(__file__).resolve().parents[3]
        completed = subprocess.run(
            [sys.executable, "-m", "loaders.pagerefs", "--dds_in", dds_in, "--pagerefs", refs_in, "--crf", crf,
             "--dds_out", out, "--patch_file", str(review)], cwd=src, capture_output=True, text=True)
        assert completed.returncode == 0, completed.stderr
        assert "open replaced" in completed.stdout and review.exists()
        assert json.loads(Path(out).read_text())["itemGroups"]

    def test_the_command_stops_on_a_mismatch(self, files, pagerefs, edited, tmp_path):
        refs = edited(pagerefs)
        refs["crf_sha256"] = "0" * 64
        dds_in, refs_in, crf, out = files(refs=refs)
        src = Path(__file__).resolve().parents[3]
        completed = subprocess.run(
            [sys.executable, "-m", "loaders.pagerefs", "--dds_in", dds_in, "--pagerefs", refs_in, "--crf", crf,
             "--dds_out", out], cwd=src, capture_output=True, text=True)
        assert completed.returncode == 1 and "made from another CRF" in completed.stderr
        assert not Path(out).exists()
