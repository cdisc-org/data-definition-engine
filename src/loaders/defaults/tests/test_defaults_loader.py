"""Tests for stage F: the fill rules, origins, ranking across datasets, the other sections,
define-patch answers and the rewritten patch, and the outputs."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from loaders.common import define_patch
from loaders.common.patch import PLACEHOLDER, is_placeholder
from loaders.defaults.defaults_loader import DEFAULT_DICTIONARY, DefaultsError, DefaultsLoader

from .conftest import P

SRC = Path(__file__).resolve().parents[3]


def _run(files, dds=None, dictionaries=None, patch=None):
    dds_in, dds_out, paths = files(dds, dictionaries)
    loader = DefaultsLoader(dds_in, dds_out, paths, patch)
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


def _groups(dds):
    return {g["OID"]: g for g in dds["itemGroups"]}


class TestFillRules:
    def test_real_values_are_never_changed(self, files, dds):
        items = _items(_run(files).dds)
        assert items["IT.LB.LBTESTCD"] == _items(dds)["IT.LB.LBTESTCD"]     # length 8, Protocol with pages
        assert items["IT.AE.AETERM"]["length"] == 200
        assert items["IT.LB.LBORRES.ALT"]["length"] == 12

    @pytest.mark.parametrize("unfilled", [None, PLACEHOLDER, ""])
    def test_a_missing_null_or_placeholder_length_is_filled(self, files, dds, unfilled):
        dds["itemGroups"][0]["items"][1]["length"] = unfilled                 # LBSEQ
        items = _items(_run(files, dds).dds)
        assert items["IT.LB.LBSEQ"]["length"] == 3
        assert items["IT.LB.LBSCAT"]["length"] == 30                         # missing

    def test_no_length_goes_on_a_datetime_item(self, files):
        items = _items(_run(files).dds)
        assert "length" not in items["IT.LB.LBDTC"]
        assert "length" not in items["IT.SE.SESTDTC"]

    def test_significant_digits_only_on_float(self, files):
        items = _items(_run(files).dds)
        assert items["IT.LB.LBSTRESN"]["significantDigits"] == 3
        assert "significantDigits" not in items["IT.LB.LBORNRLO"]

    def test_a_datatype_conflict_skips_the_type_dependent_fields_and_is_reported(self, files):
        loader = _run(files)
        item = _items(loader.dds)["IT.LB.LBORNRLO"]
        assert item["dataType"] == "text" and "length" not in item
        assert loader.report.conflicts["IT.LB.LBORNRLO"] == [
            {"entry": "items LBORNRLO (defaults-0.json)", "dataType": "text", "default": "float"}]
        # the origin does not depend on the type, so it still applies
        assert item["origin"][0]["source"] == "Vendor"

    def test_each_field_falls_through_to_the_next_entry(self, files):
        item = _items(_run(files).dds)["IT.LB.LBSCAT"]
        assert item["length"] == 30                                           # from --SCAT
        assert item["origin"] == [{"type": "Assigned", "source": "Sponsor"}]  # from --CAT

    def test_a_computed_length(self, files, dds, dictionary):
        dictionary["items"][0]["values"]["length"] = {"lengthOf": "studyName", "plus": 9}
        assert _items(_run(files, dictionaries=[dictionary]).dds)["IT.LB.STUDYID"]["length"] == 16
        dds["studyName"] = P
        assert "length" not in _items(_run(files, dds).dds)["IT.LB.STUDYID"]

    def test_displayformat_and_datatype(self, files):
        item = _items(_run(files).dds)["IT.LB.VISITNUM"]
        assert (item["dataType"], item["length"], item["displayFormat"]) == ("integer", 2, "Z2.")


class TestOrigin:
    def test_a_placeholder_origin_is_replaced(self, files):
        assert _items(_run(files).dds)["IT.LB.LBSEQ"]["origin"] == [{"type": "Derived", "source": "Sponsor"}]

    def test_a_placeholder_source_is_filled_and_the_pages_kept(self, files):
        origin = _items(_run(files).dds)["IT.LB.LBORNRLO"]["origin"]
        assert origin == [{"type": "Collected", "source": "Vendor", "documents": [{"leafID": "LF.acrf",
                                                                                   "pages": [4]}]}]

    def test_a_value_list_parent_without_origin_is_left_alone(self, files):
        assert "origin" not in _items(_run(files).dds)["IT.LB.LBORRES"]

    def test_collected_investigator_without_pages_is_listed(self, files):
        loader = _run(files)
        assert _items(loader.dds)["IT.LB.LBDTC"]["origin"] == [{"type": "Collected", "source": "Investigator"}]
        assert list(loader.report.no_pages) == ["IT.LB.LBDTC"]
        # each Derived origin gets a MethodDef placeholder from the Define generator
        assert loader.report.derived == {"IT.LB.LBSEQ", "IT.LB.LBSTRESN", "IT.SE.SESTDTC", "IT.SE.ETCD",
                                         "IT.SE.SESTDY"}


class TestRankingAcrossDatasets:
    def test_star_entries_rank_last(self, files):
        items = _items(_run(files).dds)
        assert items["IT.TA.ARM"]["origin"] == [{"type": "Protocol", "source": "Sponsor"}]
        assert items["IT.TA.STUDYID"]["origin"] == [{"type": "Protocol", "source": "Sponsor"}]
        assert items["IT.TA.STUDYID"]["length"] == 7                  # STUDYID, not *
        assert items["IT.SE.ETCD"]["origin"] == [{"type": "Derived", "source": "Sponsor"}]

    def test_an_excluded_domain_falls_to_the_star_entry(self, files):
        epoch = _items(_run(files).dds)["IT.TA.EPOCH"]
        assert epoch["origin"] == [{"type": "Protocol", "source": "Sponsor"}] and "length" not in epoch

    def test_a_domain_filtered_suffix_beats_the_plain_one(self, files):
        assert _items(_run(files).dds)["IT.SE.SESTDTC"]["origin"] == [{"type": "Derived", "source": "Sponsor"}]

    def test_an_exact_name_beats_a_suffix(self, files):
        items = _items(_run(files).dds)
        assert items["IT.TV.VISITDY"]["origin"] == [{"type": "Protocol", "source": "Sponsor"}]
        assert items["IT.TV.VISITDY"]["length"] == 4
        assert items["IT.SE.SESTDY"]["length"] == 3                   # --DY

    def test_a_later_file_wins(self, files, dictionary):
        override = {"schemaVersion": "1.0", "items": [{"name": "--SEQ", "values": {"length": 5}}]}
        item = _items(_run(files, dictionaries=[dictionary, override]).dds)["IT.LB.LBSEQ"]
        assert item["length"] == 5
        assert item["origin"] == [{"type": "Derived", "source": "Sponsor"}]   # still from the first file


class TestSections:
    def test_crf_items_and_define_items_stay_apart(self, files):
        loader = _run(files)
        assert _items(loader.dds)["IT.AE.AETERM"]["length"] == 200
        crf = loader.dds["itemGroups"][-1]["slices"][0]["slices"][0]["items"][0]
        assert crf["length"] == 50 and crf["question"] == "What is the adverse event term?"
        assert crf["prompt"] == "Term"                                        # real value kept
        assert list(loader.report.applied["IT.CRF.AETERM"]) == ["length", "question"]

    def test_a_repeated_crf_item_is_filled_in_every_copy_and_counted_once(self, files):
        loader = _run(files)
        concepts = loader.dds["itemGroups"][-1]["slices"][0]["slices"]
        assert concepts[0]["items"][0] == concepts[1]["items"][0]
        assert concepts[1]["items"][0]["length"] == 50
        # LB: STUDYID, LBSEQ, LBSCAT, LBSTRESN, VISITNUM; SE: SESTDY; TA: STUDYID; TV: VISITDY;
        # AE: AESOCCD; and the CRF AETERM once
        assert loader.report.filled["length"] == 10

    def test_crf_sections(self, files):
        loader = _run(files)
        section = loader.dds["itemGroups"][-1]["slices"][0]
        assert section["crfSectionInstructions"] == "Record each adverse event."
        assert loader.remaining_crf() == {}

    def test_key_sequences(self, files):
        groups = _groups(_run(files).dds)
        assert groups["IG.LB"]["keySequence"] == ["STUDYID", "USUBJID", "LBTESTCD"]
        assert groups["IG.SE"]["keySequence"] == ["STUDYID", "USUBJID", "SESTDTC"]    # real, kept
        assert groups["IG.TA"]["keySequence"] == [P]


class TestAnswers:
    def _patch(self, tmp_path, content):
        path = tmp_path / "define-patch.yaml"
        path.write_text(yaml.safe_dump(content), encoding="utf-8")
        return str(path)

    def test_answers_come_before_the_dictionary(self, files, tmp_path):
        patch = self._patch(tmp_path, {"items": {"IT.LB.LBSEQ": {
            "length": 5, "origin": [{"type": "Assigned", "source": "Sponsor"}]}}})
        loader = _run(files, patch=patch)
        item = _items(loader.dds)["IT.LB.LBSEQ"]
        assert item["length"] == 5 and item["origin"] == [{"type": "Assigned", "source": "Sponsor"}]
        assert loader.report.applied["IT.LB.LBSEQ"] == {"length": "answer", "origin": "answer"}

    def test_answers_never_replace_a_real_value(self, files, tmp_path):
        patch = self._patch(tmp_path, {"items": {"IT.LB.LBTESTCD": {"length": 99}}})
        assert _items(_run(files, patch=patch).dds)["IT.LB.LBTESTCD"]["length"] == 8

    def test_unanswered_values_are_not_answers(self, files, tmp_path):
        patch = self._patch(tmp_path, {"items": {"IT.LB.LBSEQ": {
            "length": None, "origin": [{"type": PLACEHOLDER, "source": PLACEHOLDER}]}},
            "itemGroups": {"IG.TA": {"keySequence": ["STUDYID", PLACEHOLDER]}}})
        loader = _run(files, patch=patch)
        assert loader.report.answered == 0
        assert _items(loader.dds)["IT.LB.LBSEQ"]["length"] == 3

    def test_a_codelist_and_a_key_sequence_answer(self, files, tmp_path):
        patch = self._patch(tmp_path, {
            "codeLists": {"CL.X": {"codeListItems": [{"codedValue": "Y", "decode": "Yes"}]}},
            "itemGroups": {"IG.TA": {"keySequence": ["STUDYID", "ARMCD", "TAETORD"]}}})
        loader = _run(files, patch=patch)
        assert loader.dds["codeLists"][0]["codeListItems"] == [{"codedValue": "Y", "decode": "Yes"}]
        assert _groups(loader.dds)["IG.TA"]["keySequence"] == ["STUDYID", "ARMCD", "TAETORD"]

    def test_the_rewritten_patch_lists_what_is_open_and_keeps_every_answer(self, files, tmp_path):
        patch = self._patch(tmp_path, {
            "items": {"IT.LB.LBSEQ": {"length": 5}, "IT.GONE": {"length": 1}},
            "codeLists": {"CL.X": {"codeListItems": [{"codedValue": "Y", "decode": "Yes"}]}}})
        loader = _run(files, patch=patch)
        loader.write_patch(patch)
        written = yaml.safe_load(Path(patch).read_text(encoding="utf-8"))
        assert written["items"]["IT.LB.LBSEQ"] == {"length": 5}              # answered, carried over
        assert "IT.GONE" not in written["items"]                             # no longer in the DDS
        assert written["items"]["IT.LB.LBORNRLO"] == {"length": None}        # the conflict left it open
        assert written["items"]["IT.TA.ARM"] == {"length": None}
        assert "IT.LB.LBDTC" not in written["items"]                         # datetime: no length
        assert written["itemGroups"] == {"IG.TA": {"keySequence": [P]}}      # no standard: standardOID set
        assert written["codeLists"]["CL.X"]["codeListItems"] == [{"codedValue": "Y", "decode": "Yes"}]
        # and it is still answered on the next run
        again = _run(files, patch=patch)
        assert _items(again.dds)["IT.LB.LBSEQ"]["length"] == 5

    def test_count_open(self, files):
        loader = _run(files)
        # lengths of LBORNRLO, LBORRES, SE.ETCD, TA.ARM and TA.EPOCH; TA's keySequence; one CL.X term
        # (codedValue and decode), counted as the pipeline counts the written file
        assert loader.open_items()["define patch values"] == define_patch.count_open(loader.remaining) == 8

    def test_count_open_matches_the_pipeline(self, files, tmp_path):
        from pipeline.run_pipeline import _count_open
        loader = _run(files)
        path = tmp_path / "define-patch.yaml"
        loader.write_patch(str(path))
        assert _count_open(path) == loader.open_items()["define patch values"]


class TestOutputs:
    def test_the_output_must_be_a_new_file(self, files):
        dds_in, _, paths = files()
        with pytest.raises(DefaultsError, match="must differ"):
            DefaultsLoader(dds_in, dds_in, paths)

    def test_an_unusable_dictionary_stops_the_run(self, files):
        with pytest.raises(DefaultsError, match="not usable"):
            _run(files, dictionaries=[{"schemaVersion": "1.0", "items": [{"name": "X"}]}])

    def test_a_second_run_on_its_output_changes_nothing(self, files, tmp_path):
        first = _run(files)
        first.save()
        second = DefaultsLoader(first.dds_out, str(tmp_path / "again.json"), files()[2])
        before = copy.deepcopy(second.dds)
        second.process()
        assert second.dds == before and not second.report.applied

    def test_the_seed_fills_only_unfilled_values(self, tmp_path):
        """On a committed combined DDS, every value the seed changes was unfilled before."""
        fixture = SRC / "generators" / "crf" / "tests" / "fixtures" / "dds-360i-crf.json"
        loader = DefaultsLoader(str(fixture), str(tmp_path / "out.json"), [str(DEFAULT_DICTIONARY)])
        before = copy.deepcopy(loader.dds)
        loader.process()
        changes = list(_changes(before, loader.dds))
        assert changes, "the seed should fill something in the fixture"
        for path, old in changes:
            if path.endswith("/origin"):
                assert define_patch.origin_open(old), path
            elif path.endswith("/keySequence"):
                assert define_patch.key_sequence_open(old), path
            else:
                assert is_placeholder(old), (path, old)

    def test_the_command(self, files, tmp_path):
        dds_in, dds_out, paths = files()
        patch, report = tmp_path / "define-patch.yaml", tmp_path / "defaults-report.yaml"
        completed = subprocess.run(
            [sys.executable, "-m", "loaders.defaults", "--dds_in", dds_in, "--dds_out", dds_out,
             "--defaults", *paths, "--patch_file", str(patch), "--report", str(report)],
            cwd=SRC, capture_output=True, text=True)
        assert completed.returncode == 0, completed.stderr
        assert "Defaults loader summary" in completed.stdout
        written = yaml.safe_load(report.read_text(encoding="utf-8"))
        assert written["noPages"] == {"IT.LB.LBDTC": "Collected/Investigator from items --DTC (defaults-0.json)"}
        # the fixture's only EPOCH is in TA, which the EPOCH entry excludes
        assert written["unmatched"] == ["items EPOCH [not TA] (defaults-0.json)", "items NOSUCH (defaults-0.json)"]
        assert yaml.safe_load(patch.read_text(encoding="utf-8"))["items"]
        assert json.loads(Path(dds_out).read_text(encoding="utf-8"))["itemGroups"]

    def test_the_seeded_output_of_a_combined_dds_validates(self, tmp_path):
        fixture = SRC / "generators" / "crf" / "tests" / "fixtures" / "dds-360i-crf.json"
        completed = subprocess.run([sys.executable, "-m", "loaders.defaults", "--dds_in", str(fixture),
                                    "--dds_out", str(tmp_path / "out.json"), "--validate"],
                                   cwd=SRC, capture_output=True, text=True)
        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert "profile validation passed" in completed.stdout

    def test_the_command_stops_on_an_unusable_dictionary(self, files, tmp_path):
        dds_in, dds_out, _ = files()
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({"schemaVersion": "1.0", "items": [{"name": "*", "values": {"length": 1}}]}))
        completed = subprocess.run([sys.executable, "-m", "loaders.defaults", "--dds_in", dds_in,
                                    "--dds_out", dds_out, "--defaults", str(bad)],
                                   cwd=SRC, capture_output=True, text=True)
        assert completed.returncode == 1 and "'domains' is a required property" in completed.stderr
        assert not Path(dds_out).exists()


def _changes(before, after, path=""):
    """(path, old value) for every value that differs, with origins and key sequences whole."""
    if isinstance(before, dict) and isinstance(after, dict):
        assert set(before) <= set(after), f"{path}: keys removed"
        for key, value in after.items():
            where = f"{path}/{key}"
            if key in ("origin", "keySequence"):
                if before.get(key) != value:
                    yield where, before.get(key)
            elif key not in before:
                yield where, None
            else:
                yield from _changes(before[key], value, where)
    elif isinstance(before, list) and isinstance(after, list):
        assert len(before) == len(after), f"{path}: length changed"
        for n, (old, new) in enumerate(zip(before, after)):
            yield from _changes(old, new, f"{path}[{n}]")
    elif before != after:
        yield path, before
