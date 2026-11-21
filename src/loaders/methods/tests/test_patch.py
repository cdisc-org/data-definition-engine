"""The review loop: placeholder methods in ``define-patch.yaml``, the answers applied, and the patch
rewritten with every section's open values plus every answer."""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from loaders.common import define_patch
from loaders.common.patch import PLACEHOLDER
from loaders.methods.methods_loader import MethodsError, MethodsLoader

SRC = Path(__file__).resolve().parents[3]
AEENRF = "MT.AE.AEENRF"
LEAF = {"title": "AE derivations", "href": "ae-derivations.pdf"}


@pytest.fixture
def go(tmp_path):
    """Run the loader over a DDS with a define patch; returns the loader, the patch path and the outputs."""
    def _go(dds: dict, patch: dict | None = None, name: str = "dds-in.json"):
        dds_in = tmp_path / name
        dds_in.write_text(json.dumps(dds), encoding="utf-8")
        path = tmp_path / "define-patch.yaml"
        if patch is not None:
            path.write_text(yaml.safe_dump(patch, sort_keys=False), encoding="utf-8")
        loader = MethodsLoader(str(dds_in), str(tmp_path / "dds-out.json"), None, str(path))
        loader.process()
        return loader
    return _go


def methods_by_oid(dds: dict) -> dict:
    return {m["OID"]: m for m in dds["methods"]}


def rewrite(loader) -> dict:
    loader.write_patch(loader.patch_file)
    return yaml.safe_load(Path(loader.patch_file).read_text(encoding="utf-8"))


class TestThePatchListsPlaceholders:
    def test_a_placeholder_method_is_listed_for_a_person(self, dds, go):
        loader = go(dds)
        written = rewrite(loader)
        assert written["methods"] == {AEENRF: {"name": "Algorithm to derive AEENRF", "type": "Computation",
                                               "description": PLACEHOLDER}}
        assert written["resources"] == {}
        text = Path(loader.patch_file).read_text(encoding="utf-8")
        assert f"{AEENRF}:  # used by IT.AE.AEENRF" in text
        assert "Written by loaders/methods" in text and "Computation | Imputation" in text

    def test_a_rewritten_placeholder_is_not_an_answer(self, dds, go):
        loader = go(dds)
        rewrite(loader)
        again = go(dds, patch=None)
        assert again.report.answered == {} and again.report.placeholders == {AEENRF: ["IT.AE.AEENRF"]}
        assert again.open_items()["define patch methods"] == 1

    def test_the_count_matches_the_pipeline(self, dds, go):
        from pipeline.run_pipeline import _count_open
        loader = go(dds, {"methods": {AEENRF: {"documents": [{"leafID": "LF.AE", "pages": [2]}]}}})
        rewrite(loader)
        path = Path(loader.patch_file)
        assert _count_open(path, methods=True) == loader.open_items()["define patch methods"] == 3
        assert _count_open(path) == loader.open_items()["define patch values"]


class TestAnswers:
    def test_an_answered_placeholder_takes_its_answer_and_its_leaf(self, dds, go):
        patch = {"methods": {AEENRF: {"name": "AEENRF from AEENDTC", "description": "Compare AEENDTC with RFENDTC.",
                                      "documents": [{"leafID": "LF.AE", "pages": [3, 4]}]}},
                 "resources": {"LF.AE": LEAF}}
        loader = go(dds, patch)
        method = methods_by_oid(loader.dds)[AEENRF]
        assert method["name"] == "AEENRF from AEENDTC" and method["description"] == "Compare AEENDTC with RFENDTC."
        assert method["documents"] == [{"leafID": "LF.AE", "pages": [3, 4]}]
        assert loader.dds["resources"] == [{"OID": "LF.AE", "leafID": "LF.AE", **LEAF}]
        assert loader.report.answered == {"LF.AE": ["title", "href"], AEENRF: ["name", "description", "documents"]}
        assert loader.report.placeholders == {}
        assert loader.open_items()["define patch methods"] == 0

    def test_the_answer_survives_the_rewrite_and_two_runs_are_identical(self, dds, go, tmp_path):
        patch = {"methods": {AEENRF: {"description": "Compare AEENDTC with RFENDTC.",
                                      "documents": [{"leafID": "LF.AE", "pages": [3]}]}},
                 "resources": {"LF.AE": LEAF}}
        first = go(dds, patch)
        first.save()
        written = rewrite(first)
        assert written["methods"][AEENRF]["documents"] == [{"leafID": "LF.AE", "pages": [3]}]
        assert written["resources"] == {"LF.AE": LEAF}
        dds_text, patch_text = ((tmp_path / "dds-out.json").read_text(), Path(first.patch_file).read_text())
        second = go(dds, patch=None)
        second.save()
        rewrite(second)
        assert (tmp_path / "dds-out.json").read_text() == dds_text
        assert Path(second.patch_file).read_text() == patch_text

    def test_a_partly_answered_placeholder_stays_open(self, dds, go):
        loader = go(dds, {"methods": {AEENRF: {"name": "AEENRF from AEENDTC", "description": PLACEHOLDER}}})
        assert methods_by_oid(loader.dds)[AEENRF]["name"] == "AEENRF from AEENDTC"
        assert AEENRF in loader.report.placeholders
        assert rewrite(loader)["methods"][AEENRF]["description"] == PLACEHOLDER

    def test_an_answer_for_a_library_method_is_not_applied(self, dds, go, caplog):
        with caplog.at_level(logging.WARNING):
            loader = go(dds, {"methods": {"MT.SEQ": {"description": "Our own SEQ."}}})
        assert methods_by_oid(loader.dds)["MT.SEQ"]["description"] != "Our own SEQ."
        assert "MT.SEQ already has a description" in caplog.text
        assert rewrite(loader)["methods"]["MT.SEQ"] == {"description": "Our own SEQ."}   # kept, not lost

    def test_a_type_rule_209_rejects_stops_the_loader(self, dds, go):
        with pytest.raises(MethodsError, match=r"MT.AE.AEENRF: type 'Analysis'.*rules 208, 209"):
            go(dds, {"methods": {AEENRF: {"type": "Analysis", "description": "x"}}})

    def test_a_document_on_an_annotated_crf_leaf_needs_no_resource(self, dds, go):
        dds["annotatedCRFs"] = [{"leafID": "LF.acrf", "href": "acrf.pdf", "title": "Annotated CRF"}]
        loader = go(dds, {"methods": {AEENRF: {"description": "x", "documents": [{"leafID": "LF.acrf", "pages": [9]}]}}})
        assert methods_by_oid(loader.dds)[AEENRF]["documents"] == [{"leafID": "LF.acrf", "pages": [9]}]
        assert "resources" not in loader.dds


class TestOpenLeaves:
    def test_a_document_without_a_leaf_waits_and_the_leaf_is_listed(self, dds, go):
        loader = go(dds, {"methods": {AEENRF: {"description": "x", "documents": [{"leafID": "LF.AE", "pages": [3]}]}},
                          "resources": {"LF.AE": {"title": "AE derivations", "href": PLACEHOLDER}}})
        method = methods_by_oid(loader.dds)[AEENRF]
        assert method["description"] == "x" and "documents" not in method
        assert loader.report.open_leaves == {"LF.AE": {"title": "AE derivations", "href": PLACEHOLDER}}
        written = rewrite(loader)
        assert written["resources"] == {"LF.AE": {"title": "AE derivations", "href": PLACEHOLDER}}
        assert written["methods"][AEENRF]["documents"] == [{"leafID": "LF.AE", "pages": [3]}]
        assert loader.open_items()["define patch methods"] == 1

    @pytest.mark.parametrize("documents, message", [
        ([{"leafID": "LF.AE", "pages": ["AE"]}], "named destinations are not supported yet"),
        ([{"pages": [3]}], "document 1 has no leafID"),
        ({"leafID": "LF.AE"}, "documents must be a list"),
    ])
    def test_an_unusable_document_answer_stops_the_loader(self, dds, go, documents, message):
        with pytest.raises(MethodsError, match=message):
            go(dds, {"methods": {AEENRF: {"documents": documents}}})


class TestTheRewrite:
    def test_answers_for_methods_nothing_needs_are_dropped(self, dds, go):
        loader = go(dds, {"methods": {"MT.AE.GONE": {"description": "x"}}, "resources": {"LF.GONE": LEAF}})
        written = rewrite(loader)
        assert "MT.AE.GONE" not in written["methods"] and written["resources"] == {}

    def test_every_section_is_rewritten(self, dds, go):
        loader = go(dds, {"items": {"IT.AE.AETERM": {"length": 200}}})
        written = rewrite(loader)
        assert written["items"]["IT.AE.AETERM"] == {"length": 200}
        assert written["items"]["IT.AE.STUDYID"] == {"length": None}
        assert loader.open_items()["define patch values"] == define_patch.count_open(
            loader.remaining, define_patch.CORE_SECTIONS)

    def test_the_command(self, dds, tmp_path):
        dds_in, dds_out = tmp_path / "in.json", tmp_path / "out.json"
        dds_in.write_text(json.dumps(dds), encoding="utf-8")
        patch = tmp_path / "define-patch.yaml"
        patch.write_text(yaml.safe_dump({"methods": {AEENRF: {"description": "Compare AEENDTC with RFENDTC."}}}))
        completed = subprocess.run([sys.executable, "-m", "loaders.methods", "--dds_in", str(dds_in),
                                    "--dds_out", str(dds_out), "--patch_file", str(patch)],
                                   cwd=SRC, capture_output=True, text=True)
        assert completed.returncode == 0, completed.stderr
        assert "from define-patch answers  1" in completed.stdout
        assert yaml.safe_load(patch.read_text())["methods"][AEENRF]["description"] == "Compare AEENDTC with RFENDTC."
