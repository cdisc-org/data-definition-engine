"""Tests for the pipeline driver with the seven stages stubbed: order, folders, paths and control.

Stages A and B need the CDISC Library, so the real run is the end-to-end check in the README.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pipeline import run_pipeline as P  # noqa: E402


@pytest.fixture
def study_yaml(tmp_path) -> Path:
    folder = tmp_path / "protocols" / "S1"
    folder.mkdir(parents=True)
    (folder / "S1-latest.json").write_text("{}")
    (tmp_path / "specs.csv").write_text("")
    path = folder / "pipeline.yaml"
    path.write_text(yaml.safe_dump({
        "study": "S1", "usdm_file": "S1-latest.json", "crf_spec_file": "../../specs.csv",
        "dds_define": "../../define-xml/output/S1_DDS.json", "output_dir": "../../output/S1",
        "sdtmct": "2025-09-26", "cdashct": "2026-03-27",
        "commands": {"crfvalidate": "/opt/crfutils/bin/crfvalidate", "crfpdf": "/opt/crfutils/bin/crfpdf"},
    }))
    return path


class Recorder:
    """Stands in for subprocess.run: records each call and writes what the stage would write."""

    def __init__(self, fail: str | None = None, codes: dict | None = None):
        self.calls, self.fail, self.codes = [], fail, codes or {}

    def __call__(self, command, cwd):
        self.calls.append((command, cwd))
        joined = " ".join(command)
        if "crf_loader" in joined:
            out = Path(command[command.index("--dds_out") + 1])
            out.write_text(json.dumps({"annotatedCRFs": [{"leafID": "LF.acrf", "href": "acrf.pdf"}]}))
        code = 1 if self.fail and self.fail in joined else 0
        for needle, value in self.codes.items():
            if needle in joined:
                code = value
        return SimpleNamespace(returncode=code)


def _stage_of(command):
    joined = " ".join(command)
    for needle, stage in (("create_define_json", "A"), ("crf_loader", "B"), ("crf_generator", "C"),
                          ("crfvalidate", "D"), ("crfpdf", "D"), ("loaders.pagerefs", "E"),
                          ("loaders.defaults", "F"), ("define_generator", "G"), ("defineutils", "G")):
        if needle in joined:
            return stage
    return "?"


def test_stages_run_in_order_in_their_folders_with_absolute_paths(study_yaml):
    recorder = Recorder()
    pipeline = P.Pipeline(P.load_study(study_yaml), python="py", runner=recorder, echo=lambda _: None)
    pipeline.run()
    assert [_stage_of(c) for c, _ in recorder.calls] == ["A", "B", "C", "D", "D", "E", "F", "G", "G"]
    cwds = [Path(cwd) for _, cwd in recorder.calls]
    assert cwds[0] == P.SRC / "define-xml" and cwds[1] == P.SRC and cwds[2] == P.SRC / "generators" / "crf"
    assert cwds[5] == P.SRC and cwds[6] == P.SRC and cwds[7] == P.SRC / "generators" / "define"
    for command, _ in recorder.calls:
        for part in command:
            if part.endswith((".json", ".xml", ".yaml", ".csv", ".pdf")):
                assert Path(part).is_absolute(), part
    # the PDF name comes from DDS2's annotated CRF leaf, and crfutils runs from its configured path
    crfpdf = next(c for c, _ in recorder.calls if "crfpdf" in c[0])
    assert crfpdf[0] == "/opt/crfutils/bin/crfpdf" and crfpdf[crfpdf.index("-o") + 1].endswith("/output/S1/acrf.pdf")
    record = json.loads(pipeline.write_record().read_text())
    assert [s["stage"] for s in record["steps"]] == ["A", "B", "C", "D", "D", "E", "F", "G", "G"]


def test_review_files_are_applied_when_they_exist(study_yaml):
    study = P.load_study(study_yaml)
    first = {s.name: s.command for s in P.steps(study, "py")}
    assert "--apply_patch" not in first["define loader"] and "--apply_patch" not in first["CRF loader"]
    study.crf_refinement.write_text("items: {}\n")
    again = {s.name: s.command for s in P.steps(study, "py")}
    assert again["CRF loader"][-2:] == ["--apply_patch", str(study.crf_refinement)]
    assert "--apply_patch" not in again["pagerefs loader"]


def test_stage_a_applies_the_define_patch_and_stage_f_rewrites_it(study_yaml):
    study = P.load_study(study_yaml)
    stage_a = next(s for s in P.steps(study, "py") if s.stage == "A")
    assert stage_a.command[-2:] == ["--patch_file", str(study.output_dir / "define-patch-stageA.yaml")]
    study.define_patch.write_text("items: {}\n")
    steps = {s.name: s for s in P.steps(study, "py")}
    assert steps["define loader"].command[-4:] == ["--patch_file", str(study.define_patch_stage_a),
                                                   "--apply_patch", str(study.define_patch)]
    assert steps["define loader"].outputs == [study.dds_define, study.define_patch_stage_a]
    defaults = steps["defaults loader"].command
    assert defaults[defaults.index("--dds_in") + 1] == str(study.output_dir / "dds-origin.json")
    assert defaults[defaults.index("--patch_file") + 1] == str(study.define_patch)
    assert defaults[defaults.index("--report") + 1] == str(study.output_dir / "defaults-report.yaml")
    generator = steps["define generator"].command
    assert generator[generator.index("-t") + 1] == str(study.output_dir / "dds-defaults.json")


def test_the_defaults_dictionaries(study_yaml):
    study = P.load_study(study_yaml)
    command = next(s.command for s in P.steps(study, "py") if s.stage == "F")
    assert command[command.index("--defaults") + 1] == str(P.DEFAULT_DICTIONARY)
    data = yaml.safe_load(study_yaml.read_text())
    data["defaults"] = ["../../defaults/shared.json", "study-defaults.json"]
    study_yaml.write_text(yaml.safe_dump(data))
    study = P.load_study(study_yaml)
    command = next(s.command for s in P.steps(study, "py") if s.stage == "F")
    first = command.index("--defaults") + 1
    assert command[first:first + 2] == [str(study_yaml.parent.parent.parent / "defaults" / "shared.json"),
                                        str(study_yaml.parent / "study-defaults.json")]


def test_a_failing_stage_stops_the_run(study_yaml):
    recorder = Recorder(fail="crf_generator")
    pipeline = P.Pipeline(P.load_study(study_yaml), python="py", runner=recorder, echo=lambda _: None)
    with pytest.raises(P.PipelineError, match="stage C"):
        pipeline.run()
    assert [_stage_of(c) for c, _ in recorder.calls] == ["A", "B", "C"]


def test_a_failed_validation_is_an_open_item_not_a_stop(study_yaml):
    recorder = Recorder(codes={"defineutils": 1})
    pipeline = P.Pipeline(P.load_study(study_yaml), python="py", runner=recorder, echo=lambda _: None)
    pipeline.run()
    assert pipeline.open_items()["validation failures"] == 1


def test_from_and_to(study_yaml):
    recorder = Recorder()
    pipeline = P.Pipeline(P.load_study(study_yaml), python="py", runner=recorder, echo=lambda _: None)
    pipeline.run("E", "F")
    assert [_stage_of(c) for c, _ in recorder.calls] == ["E", "F"]
    recorder.calls.clear()
    pipeline.run("F")
    assert [_stage_of(c) for c, _ in recorder.calls] == ["F", "G", "G"]
    with pytest.raises(P.PipelineError, match="not a range"):
        pipeline.run("G", "A")


def test_open_items_and_strict(study_yaml, monkeypatch, capsys):
    study = P.load_study(study_yaml)
    study.output_dir.mkdir(parents=True, exist_ok=True)
    study.define_patch_stage_a.write_text(yaml.safe_dump({"items": {"IT.X": {"length": None}}}))
    assert P.Pipeline(study, runner=Recorder(), echo=lambda _: None).open_items()["define patch open values"] == 1
    study.define_patch.write_text(yaml.safe_dump({"items": {"IT.X": {"length": None, "origin": [
        {"type": "__PLACEHOLDER__", "source": "__PLACEHOLDER__"}]}, "IT.Y": {"length": 8}}}))
    study.defaults_report.write_text(yaml.safe_dump({"noPages": {"IT.RE.REDTC": "Collected/Investigator"}}))
    study.origin_review.write_text(yaml.safe_dump({"replaced": {"IT.A": {"pin": "__PLACEHOLDER__"},
                                                                "IT.B": {"pin": "crf"}}}))
    (study.output_dir / "acrf.pagerefs.json").write_text(json.dumps(
        {"warnings": [{"check": "define_oid_unpaired"}, {"check": "unparsed_annotation"}]}))
    items = P.Pipeline(study, runner=Recorder(), echo=lambda _: None).open_items()
    assert items["define patch open values"] == 3 and items["origin review replaced"] == 1
    assert items["defaults noPages"] == 1
    assert items["pagerefs define_oid_unpaired"] == 1 and items["pagerefs sdtm_alias_disagrees"] == 0

    monkeypatch.setattr(P, "Pipeline", lambda study_: SimpleNamespace(
        run=lambda first, last: None, record=[], open_items=lambda: items, failed_checks=[]))
    assert P.main(["--study", str(study_yaml)]) == 0
    assert P.main(["--study", str(study_yaml), "--strict"]) == 1
    assert "--strict: 6 open item(s)" in capsys.readouterr().err


def test_dry_run_prints_without_running(study_yaml, capsys):
    assert P.main(["--study", str(study_yaml), "--dry-run", "--from", "C", "--to", "D"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert [line[:3] for line in out] == ["[C]", "[D]", "[D]"]


def test_an_unusable_study_yaml(tmp_path, capsys):
    path = tmp_path / "pipeline.yaml"
    path.write_text("study: X\n")
    assert P.main(["--study", str(path)]) == 1
    assert "has no usdm_file" in capsys.readouterr().err
