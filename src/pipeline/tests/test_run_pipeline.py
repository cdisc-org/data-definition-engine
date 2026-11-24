"""Tests for the pipeline driver with the eight stages stubbed: order, folders, paths and control;
and stages G and H run for real on a small DDS (the define patch loop for methods).

Stages A and B need the CDISC Library, so the real run of every stage is the end-to-end check in the README.
"""
from __future__ import annotations

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
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
                          ("loaders.defaults", "F"), ("loaders.methods", "G"), ("define_generator", "H"),
                          ("defineutils", "H")):
        if needle in joined:
            return stage
    return "?"


def test_stages_run_in_order_in_their_folders_with_absolute_paths(study_yaml):
    recorder = Recorder()
    pipeline = P.Pipeline(P.load_study(study_yaml), python="py", runner=recorder, echo=lambda _: None)
    pipeline.run()
    assert [_stage_of(c) for c, _ in recorder.calls] == ["A", "B", "C", "D", "D", "E", "F", "G", "H", "H"]
    cwds = [Path(cwd) for _, cwd in recorder.calls]
    assert cwds[0] == P.SRC / "define-xml" and cwds[1] == P.SRC and cwds[2] == P.SRC / "generators" / "crf"
    assert cwds[5] == cwds[6] == cwds[7] == P.SRC and cwds[8] == P.SRC / "generators" / "define"
    for command, _ in recorder.calls:
        for part in command:
            if part.endswith((".json", ".xml", ".yaml", ".csv", ".pdf")):
                assert Path(part).is_absolute(), part
    # the PDF name comes from DDS2's annotated CRF leaf, and crfutils runs from its configured path
    crfpdf = next(c for c, _ in recorder.calls if "crfpdf" in c[0])
    assert crfpdf[0] == "/opt/crfutils/bin/crfpdf" and crfpdf[crfpdf.index("-o") + 1].endswith("/output/S1/acrf.pdf")
    record = json.loads(pipeline.write_record().read_text())
    assert [s["stage"] for s in record["steps"]] == ["A", "B", "C", "D", "D", "E", "F", "G", "H", "H"]


def test_review_files_are_applied_when_they_exist(study_yaml):
    study = P.load_study(study_yaml)
    first = {s.name: s.command for s in P.steps(study, "py")}
    assert "--apply_patch" not in first["define loader"] and "--apply_patch" not in first["CRF loader"]
    study.crf_refinement.write_text("items: {}\n")
    again = {s.name: s.command for s in P.steps(study, "py")}
    assert again["CRF loader"][-2:] == ["--apply_patch", str(study.crf_refinement)]
    assert "--apply_patch" not in again["pagerefs loader"]


def test_stages_a_and_f_apply_the_define_patch_and_stage_g_rewrites_it(study_yaml):
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
    assert "--patch_read_only" in defaults and study.define_patch not in steps["defaults loader"].outputs
    assert defaults[defaults.index("--report") + 1] == str(study.output_dir / "defaults-report.yaml")
    methods = steps["methods loader"].command
    assert methods[methods.index("--dds_in") + 1] == str(study.output_dir / "dds-defaults.json")
    assert methods[methods.index("--dds_out") + 1] == str(study.output_dir / "dds-methods.json")
    assert methods[methods.index("--patch_file") + 1] == str(study.define_patch)
    assert methods[methods.index("--report") + 1] == str(study.output_dir / "methods-report.yaml")
    assert "--patch_read_only" not in methods and study.define_patch in steps["methods loader"].outputs
    generator = steps["define generator"].command
    assert generator[generator.index("-t") + 1] == str(study.output_dir / "dds-methods.json")


@pytest.mark.parametrize("key, stage, default", [("defaults", "F", P.DEFAULT_DICTIONARY),
                                                  ("methods", "G", P.DEFAULT_METHODS)])
def test_the_defaults_dictionaries_and_the_method_libraries(study_yaml, key, stage, default):
    option = f"--{key}"
    study = P.load_study(study_yaml)
    command = next(s.command for s in P.steps(study, "py") if s.stage == stage)
    assert command[command.index(option) + 1] == str(default) and command[command.index(option) + 2][:2] == "--"
    data = yaml.safe_load(study_yaml.read_text())
    data[key] = [f"../../{key}/shared.json", f"study-{key}.json"]
    study_yaml.write_text(yaml.safe_dump(data))
    study = P.load_study(study_yaml)
    command = next(s.command for s in P.steps(study, "py") if s.stage == stage)
    first = command.index(option) + 1
    assert command[first:first + 3] == [str(study_yaml.parent.parent.parent / key / "shared.json"),
                                        str(study_yaml.parent / f"study-{key}.json"), "--patch_file"]
    data[key] = f"study-{key}.json"     # one file needs no list
    study_yaml.write_text(yaml.safe_dump(data))
    assert getattr(P.load_study(study_yaml), key) == [study_yaml.parent / f"study-{key}.json"]


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
    assert [_stage_of(c) for c, _ in recorder.calls] == ["F", "G", "H", "H"]
    recorder.calls.clear()
    pipeline.run("G")
    assert [_stage_of(c) for c, _ in recorder.calls] == ["G", "H", "H"]
    with pytest.raises(P.PipelineError, match="not a range"):
        pipeline.run("H", "A")


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


def test_open_methods_are_counted_apart(study_yaml):
    study = P.load_study(study_yaml)
    study.output_dir.mkdir(parents=True, exist_ok=True)
    study.define_patch.write_text(yaml.safe_dump({
        "items": {"IT.X": {"length": None}},
        "methods": {"MT.AE.AEENRF": {"name": "Algorithm to derive AEENRF", "type": "Computation",
                                     "description": "__PLACEHOLDER__"},
                    "MT.RS.RSLNKGRP": {"description": "Answered."}},
        "resources": {"LF.AE": {"title": "AE derivations", "href": "__PLACEHOLDER__"}}}))
    items = P.Pipeline(study, runner=Recorder(), echo=lambda _: None).open_items()
    assert items["define patch open values"] == 1 and items["define patch open methods"] == 2


# -- stages G and H for real ---------------------------------------------------------------
def _item(name: str, origin: str, **extra) -> dict:
    return {"OID": f"IT.AE.{name}", "name": name, "dataType": "text", "length": 20,
            "origin": [{"type": origin, "source": "Sponsor"}], **extra}


SMALL_DDS = {
    "studyOID": "S1", "studyName": "S1", "studyDescription": "S1", "protocolName": "S1", "defineVersion": "2.1.0",
    "conditions": [], "whereClauses": [], "codeLists": [], "methods": [], "standards": [],
    "itemGroups": [{"OID": "IG.AE", "name": "AE", "domain": "AE", "description": "Adverse Events",
                    "purpose": "Tabulation", "structure": "One record per adverse event per subject",
                    "items": [_item("STUDYID", "Protocol", mandatory=True, keySequence=1),
                              _item("USUBJID", "Derived", mandatory=True, keySequence=2),
                              _item("AESEQ", "Derived", mandatory=True),
                              _item("AEENRF", "Derived", mandatory=False)]}],
}


def _real_g_and_h(command, cwd):
    """The methods loader and the Define generator run for real; defineutils is stubbed."""
    if "defineutils.validate" in command:
        return SimpleNamespace(returncode=0)
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    return completed


def _method_defs(define: Path) -> dict:
    """MethodDef OID -> (description text, the leafIDs its DocumentRefs name)."""
    found = {}
    for element in ET.parse(define).getroot().iter():
        if element.tag.endswith("}MethodDef"):
            text = next((t.text for t in element.iter() if t.tag.endswith("}TranslatedText")), None)
            leaves = [r.get("leafID") for r in element.iter() if r.tag.endswith("}DocumentRef")]
            found[element.get("OID")] = (text, leaves)
    return found


def test_from_g_answers_a_placeholder_method_with_the_real_methods_loader_and_define_generator(study_yaml):
    study = P.load_study(study_yaml)
    study.output_dir.mkdir(parents=True, exist_ok=True)
    study.dds_defaults.write_text(json.dumps(SMALL_DDS))
    pipeline = P.Pipeline(study, python=sys.executable, runner=_real_g_and_h, echo=lambda _: None)

    pipeline.run("G")
    assert [step["stage"] for step in pipeline.record] == ["G", "H", "H"]
    report = yaml.safe_load(study.methods_report.read_text())
    assert report["placeholders"] == {"MT.AE.AEENRF": ["IT.AE.AEENRF"]}
    assert set(report["assigned"]) == {"MT.USUBJID", "MT.SEQ"}
    patch = yaml.safe_load(study.define_patch.read_text())
    assert patch["methods"]["MT.AE.AEENRF"]["description"] == P.PLACEHOLDER
    assert "Written by loaders/methods (pipeline stage G)" in study.define_patch.read_text()
    assert pipeline.open_items()["define patch open methods"] == 1
    assert _method_defs(study.define)["MT.AE.AEENRF"] == (P.PLACEHOLDER, [])

    # a person answers the placeholder in the define patch; --from G applies it
    patch["methods"]["MT.AE.AEENRF"].update(description="Compare AEENDTC with the reference end date.",
                                            documents=[{"leafID": "LF.AE", "pages": [2]}])
    patch["resources"] = {"LF.AE": {"title": "AE derivations", "href": "ae-derivations.pdf"}}
    study.define_patch.write_text(yaml.safe_dump(patch, sort_keys=False))
    pipeline.run("G")
    methods = _method_defs(study.define)
    assert methods["MT.AE.AEENRF"] == ("Compare AEENDTC with the reference end date.", ["LF.AE"])
    assert set(methods) == {"MT.USUBJID", "MT.SEQ", "MT.AE.AEENRF"}    # no generator placeholders
    assert pipeline.open_items()["define patch open methods"] == 0
    rewritten = yaml.safe_load(study.define_patch.read_text())
    assert rewritten["resources"] == {"LF.AE": {"title": "AE derivations", "href": "ae-derivations.pdf"}}
    assert json.loads(study.dds_defaults.read_text()) == SMALL_DDS     # G never writes its input
