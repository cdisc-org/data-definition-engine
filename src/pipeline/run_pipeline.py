"""Run the DDE stages A-F for one study, from its study design to define.xml and the annotated CRF.

| Stage | Program | Writes |
|---|---|---|
| A | define-xml/create_define_json.py | DDS1 (the Define DDS), the define patch |
| B | loaders/crf/crf_loader.py | DDS2 (with the CRF), crf-refinement.yaml |
| C | generators/crf/crf_generator.py | crf-2.0.xml |
| D | crfutils crfvalidate + crfpdf | acrf.pdf, acrf.pagerefs.json |
| E | loaders/pagerefs | DDS3 (with Origin and pages), origin-review.yaml |
| F | generators/define/define_generator.py (+ defineutils) | define.xml |

Each stage runs as a subprocess in the folder it needs (``define-xml/`` and
``generators/define/`` use flat imports; the loaders run as packages from ``src/``), with every
path made absolute. A stage that exits non-zero stops the run. A stage whose review file exists
applies it and writes it back with what is still open. The run ends with a summary of open
review items; with ``--strict`` it exits non-zero while any is open (a define.xml that fails
schema validation counts as one).

The study YAML (paths relative to it)::

    study: NCT01797120
    usdm_file: NCT01797120-latest.json
    crf_spec_file: ../../crf_specializations/cdisc_crf_specializations_draft.csv
    dds_define: ../../../src/define-xml/output/NCT_DDS.json
    output_dir: ../../../output/NCT01797120
    sdtmig: "3.4"
    sdtmct: "2025-09-26"
    cdashig: "2.3"
    cdashct: "2026-03-27"
    page_size: letter
    review:
      define_patch: define-patch.yaml
      crf_refinement: crf-refinement.yaml
      origin_review: origin-review.yaml
    commands:            # optional; defaults shown
      crfvalidate: crfvalidate
      crfpdf: crfpdf
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

SRC = Path(__file__).resolve().parents[1]
STAGES = ("A", "B", "C", "D", "E", "F")
PLACEHOLDER = "__PLACEHOLDER__"


class PipelineError(Exception):
    """The study YAML is unusable or a stage failed."""


@dataclass
class Step:
    stage: str
    name: str
    command: list[str]
    cwd: Path
    inputs: list[Path] = field(default_factory=list)
    outputs: list[Path] = field(default_factory=list)
    check: bool = False        # a validation whose failure is an open item, not a stop


@dataclass
class Study:
    path: Path
    name: str
    usdm_file: Path
    crf_spec_file: Path
    dds_define: Path
    output_dir: Path
    sdtmig: str
    sdtmct: str
    cdashig: str
    cdashct: str
    page_size: str
    define_patch: Path
    crf_refinement: Path
    origin_review: Path
    crfvalidate: list[str]
    crfpdf: list[str]

    @property
    def dds_crf(self) -> Path:
        return self.output_dir / "dds-crf.json"

    @property
    def dds_origin(self) -> Path:
        return self.output_dir / "dds-origin.json"

    @property
    def crf(self) -> Path:
        return self.output_dir / "crf-2.0.xml"

    @property
    def define(self) -> Path:
        return self.output_dir / "define.xml"


def load_study(path: str | Path) -> Study:
    path = Path(path).resolve()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise PipelineError(f"cannot read the study YAML {path}: {exc}") from exc
    base = path.parent

    def file(key: str, default: str | None = None) -> Path:
        value = data.get(key, default)
        if not value:
            raise PipelineError(f"the study YAML {path} has no {key}")
        return (base / value).resolve()

    review = data.get("review") or {}
    commands = data.get("commands") or {}
    return Study(
        path=path, name=str(data.get("study") or path.parent.name),
        usdm_file=file("usdm_file"), crf_spec_file=file("crf_spec_file"),
        dds_define=file("dds_define"), output_dir=file("output_dir"),
        sdtmig=str(data.get("sdtmig", "3.4")), sdtmct=str(file_value(data, "sdtmct", path)),
        cdashig=str(data.get("cdashig", "2.3")), cdashct=str(file_value(data, "cdashct", path)),
        page_size=str(data.get("page_size", "letter")),
        define_patch=(base / review.get("define_patch", "define-patch.yaml")).resolve(),
        crf_refinement=(base / review.get("crf_refinement", "crf-refinement.yaml")).resolve(),
        origin_review=(base / review.get("origin_review", "origin-review.yaml")).resolve(),
        crfvalidate=shlex.split(str(commands.get("crfvalidate", "crfvalidate"))),
        crfpdf=shlex.split(str(commands.get("crfpdf", "crfpdf"))),
    )


def file_value(data: dict[str, Any], key: str, path: Path) -> str:
    if not data.get(key):
        raise PipelineError(f"the study YAML {path} has no {key}")
    return data[key]


def acrf_name(dds_file: Path) -> str:
    """The PDF name the DDS's annotated CRF leaf gives (``acrf.pdf`` when it names none)."""
    try:
        with open(dds_file, "r", encoding="utf-8") as f:
            dds = json.load(f)
    except (OSError, json.JSONDecodeError):
        return "acrf.pdf"
    dds = dds.get("metaDataVersion", dds)
    acrfs = dds.get("annotatedCRFs") or []
    href = acrfs[0].get("href") if acrfs and isinstance(acrfs[0], dict) else None
    return Path(href).name if href else "acrf.pdf"


def steps(study: Study, python: str = sys.executable) -> list[Step]:
    """Every step of stages A-F, in order. Stage D's PDF name is read from DDS2 when it runs."""
    out = study.output_dir
    refs = out / "acrf.pagerefs.json"

    def review_args(path: Path) -> list[str]:
        args = ["--patch_file", str(path)]
        return args + ["--apply_patch", str(path)] if path.exists() else args

    return [
        Step("A", "define loader", [python, "create_define_json.py", "--usdm_file", str(study.usdm_file),
                                    "--output_template", str(study.dds_define), "--sdtmig", study.sdtmig,
                                    "--sdtmct", study.sdtmct] + review_args(study.define_patch),
             SRC / "define-xml", [study.usdm_file], [study.dds_define, study.define_patch]),
        Step("B", "CRF loader", [python, "-m", "loaders.crf.crf_loader", "--dds_in", str(study.dds_define),
                                 "--usdm_file", str(study.usdm_file), "--dds_out", str(study.dds_crf),
                                 "--crf_spec_file", str(study.crf_spec_file), "--cdashig", study.cdashig,
                                 "--cdashct", study.cdashct, "--sdtmct", study.sdtmct]
             + review_args(study.crf_refinement),
             SRC, [study.dds_define, study.usdm_file, study.crf_spec_file], [study.dds_crf, study.crf_refinement]),
        Step("C", "CRF generator", [python, "crf_generator.py", "-t", str(study.dds_crf), "-o", str(study.crf),
                                    "--odm-version", "2.0", "--validate"],
             SRC / "generators" / "crf", [study.dds_crf], [study.crf]),
        Step("D", "crfvalidate", study.crfvalidate + ["-c", str(study.crf)], out, [study.crf], []),
        Step("D", "crfpdf", study.crfpdf + ["-c", str(study.crf), "-o", "<acrf>", "--refs", str(refs),
                                            "--page-size", study.page_size],
             out, [study.crf], [refs]),
        Step("E", "pagerefs loader", [python, "-m", "loaders.pagerefs", "--dds_in", str(study.dds_crf),
                                      "--pagerefs", str(refs), "--crf", str(study.crf),
                                      "--dds_out", str(study.dds_origin)] + review_args(study.origin_review),
             SRC, [study.dds_crf, refs, study.crf], [study.dds_origin, study.origin_review]),
        Step("F", "define generator", [python, "define_generator.py", "-t", str(study.dds_origin),
                                       "-d", str(study.define)],
             SRC / "generators" / "define", [study.dds_origin], [study.define]),
        Step("F", "define.xml validation", [python, "-m", "defineutils.validate", "-d", str(study.define)],
             out, [study.define], [], check=True),
    ]


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


class Pipeline:
    def __init__(self, study: Study, python: str = sys.executable,
                 runner: Callable[..., Any] = subprocess.run,
                 echo: Callable[[str], None] = lambda text: print(text, flush=True)) -> None:
        self.study = study
        self.python = python
        self.runner = runner
        self.echo = echo
        self.record: list[dict[str, Any]] = []
        self.failed_checks: list[str] = []

    def run(self, first: str = "A", last: str = "F") -> None:
        """Run stages ``first`` to ``last``. Raises PipelineError when a stage fails."""
        if first not in STAGES or last not in STAGES or STAGES.index(first) > STAGES.index(last):
            raise PipelineError(f"--from {first} --to {last} is not a range of {', '.join(STAGES)}")
        wanted = STAGES[STAGES.index(first):STAGES.index(last) + 1]
        self.study.output_dir.mkdir(parents=True, exist_ok=True)
        self.study.dds_define.parent.mkdir(parents=True, exist_ok=True)
        for step in steps(self.study, self.python):
            if step.stage not in wanted:
                continue
            if "<acrf>" in step.command:
                pdf = self.study.output_dir / acrf_name(self.study.dds_crf)
                step.command = [str(pdf) if part == "<acrf>" else part for part in step.command]
                step.outputs.insert(0, pdf)
            self._run(step)

    def _run(self, step: Step) -> None:
        self.echo(f"[{step.stage}] {step.name}: {' '.join(shlex.quote(p) for p in step.command)}")
        started = time.monotonic()
        try:
            completed = self.runner(step.command, cwd=str(step.cwd))
            code = completed.returncode
        except OSError as exc:
            code = 127
            self.echo(f"    cannot start {step.command[0]}: {exc}")
        self.record.append({
            "stage": step.stage, "name": step.name, "command": step.command, "cwd": str(step.cwd),
            "exit_code": code, "seconds": round(time.monotonic() - started, 2),
            "inputs": {str(p): _sha256(p) for p in step.inputs},
            "outputs": {str(p): _sha256(p) for p in step.outputs},
        })
        if code != 0:
            if step.check:
                self.failed_checks.append(f"{step.name} failed (exit {code})")
                return
            raise PipelineError(f"stage {step.stage} ({step.name}) exited {code}")

    # -- the summary ------------------------------------------------------------
    def open_items(self) -> dict[str, int]:
        """Open review items per source; zero everywhere means --strict passes."""
        items = {
            "define patch placeholders": _count_placeholders(self.study.define_patch),
            "CRF mappingReview": len(_load_yaml(self.study.crf_refinement).get("mappingReview") or {}),
        }
        refs = _load_json(self.study.output_dir / "acrf.pagerefs.json")
        for check in ("sdtm_alias_disagrees", "define_oid_unpaired"):
            items[f"pagerefs {check}"] = sum(1 for w in refs.get("warnings") or [] if w.get("check") == check)
        review = _load_yaml(self.study.origin_review)
        for section in ("replaced", "noPages", "unknownOids", "unpaired"):
            items[f"origin review {section}"] = sum(
                1 for entry in (review.get(section) or {}).values()
                if not isinstance(entry, dict) or entry.get("pin") in (None, "", PLACEHOLDER))
        items["validation failures"] = len(self.failed_checks)
        return items

    def write_record(self) -> Path:
        path = self.study.output_dir / "pipeline-run.json"
        path.write_text(json.dumps({"study": self.study.name, "study_yaml": str(self.study.path),
                                    "steps": self.record, "open_items": self.open_items()}, indent=2) + "\n",
                        encoding="utf-8")
        return path


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return {}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _count_placeholders(path: Path) -> int:
    def walk(value: Any) -> int:
        if isinstance(value, dict):
            return sum(walk(v) for v in value.values())
        if isinstance(value, list):
            return sum(walk(v) for v in value)
        return 1 if value == PLACEHOLDER else 0
    return walk(_load_yaml(path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pipeline",
                                     description="Run the DDE stages A-F for one study.")
    parser.add_argument("--study", required=True, help="the study's pipeline.yaml")
    parser.add_argument("--from", dest="first", default="A", choices=STAGES, help="first stage to run")
    parser.add_argument("--to", dest="last", default="F", choices=STAGES, help="last stage to run")
    parser.add_argument("--strict", action="store_true",
                        help="exit non-zero while any review item is open")
    parser.add_argument("--dry-run", action="store_true", help="print the commands without running them")
    args = parser.parse_args(argv)
    try:
        study = load_study(args.study)
        if args.dry_run:
            for step in steps(study):
                if STAGES.index(args.first) <= STAGES.index(step.stage) <= STAGES.index(args.last):
                    print(f"[{step.stage}] (cd {step.cwd}) {' '.join(shlex.quote(p) for p in step.command)}")
            return 0
        pipeline = Pipeline(study)
        try:
            pipeline.run(args.first, args.last)
        finally:
            if pipeline.record:
                print(f"run record: {pipeline.write_record()}")
    except PipelineError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    items = pipeline.open_items()
    print("\nOpen review items")
    for name, count in items.items():
        print(f"  {name:.<34} {count}")
    for failure in pipeline.failed_checks:
        print(f"  ! {failure}")
    total = sum(items.values())
    if args.strict and total:
        print(f"--strict: {total} open item(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
