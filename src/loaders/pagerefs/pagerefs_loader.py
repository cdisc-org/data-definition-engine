"""Stage E: merge the aCRF page references into the DDS as Define-XML Origin.

An enrichment loader, like ``loaders/crf``: DDS in, DDS out. It runs after the CRF loader
(which built the DDS this CRF was generated from) and after crfutils ``crfpdf`` rendered the
annotated CRF and wrote ``acrf.pagerefs.json``. The Define-XML generator then reads its output.

Origin with pages cannot exist earlier: the Define loader has no CRF and the CRF loader has no
PDF. So the page references are a third load, and the generators keep reading only the DDS.

For each Define item (variable-level or value-level) the origin is decided in this order:

1. a pin in ``origin-review.yaml`` (by item OID, ValueListDef OID or ``DATASET.VARIABLE``);
2. the CRF evidence the pagerefs file files under the item's OID (``define_items``): it
   replaces the Define loader's origin, and a replaced non-placeholder origin is listed for
   review (``replaced``); a placeholder or missing origin is simply filled;
3. for an item the CRF does not name, the key recipe of the pagerefs README (variable-level
   roll-up, or a value-level where clause that admits the CRF target's conditions);
4. otherwise the Define loader's origin stays as it is.

Origins are written in the DDS schema shape, ``{type, source, documents: [{leafID, pages}]}``.
A variable whose value-level items carry origins keeps no origin of its own, as the Define
loader writes it.

The loader always starts from the CRF-enriched DDS and writes a new file, so a re-run replaces
the CRF origins instead of stacking them.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Importable both as ``python pagerefs_loader.py`` from this directory and as
# ``python -m loaders.pagerefs`` from ``src/``.
_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from loaders.common import dds_io  # noqa: E402
from loaders.common.patch import PLACEHOLDER, is_placeholder  # noqa: E402
from loaders.crf.builders.sdtm_links import DefineIndex, admits  # noqa: E402
from loaders.pagerefs import review as origin_review  # noqa: E402

logger = logging.getLogger("pagerefs_loader")

MIN_SCHEMA_VERSION = (2, 1)
DEFAULT_LEAF_ID = "LF.acrf"
COLLECTED_INVESTIGATOR = ("Collected", "Investigator")


class PagerefsError(Exception):
    """The inputs do not belong together, or cannot be read; nothing was written."""


class PagerefsLoader:
    """Merges one ``acrf.pagerefs.json`` into the DDS the CRF was generated from."""

    def __init__(self, dds_in: str, pagerefs: str, crf: str, dds_out: str) -> None:
        if Path(dds_in).resolve() == Path(dds_out).resolve():
            raise PagerefsError("--dds_out must differ from --dds_in: the loader always starts "
                                "from the CRF-enriched DDS, so a re-run replaces the CRF origins")
        self.dds_in, self.crf, self.dds_out = dds_in, crf, dds_out
        try:
            self.dds, self.wrapped = dds_io.load_dds(dds_in)
            with open(pagerefs, "r", encoding="utf-8") as f:
                self.refs = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            raise PagerefsError(str(exc)) from exc
        self.normalized = dds_io.normalize_dds(self.dds)
        self.pins: dict[str, Any] = {}
        self.answered: dict[str, dict[str, Any]] = {}
        self.review: dict[str, dict[str, dict[str, Any]]] = {
            "replaced": {}, "noPages": {}, "unknownOids": {}, "unpaired": {}}
        self.extra_pins: dict[str, Any] = {}
        self.report: dict[str, int] = {"crfOrigins": 0, "fallbackOrigins": 0, "pinned": 0,
                                       "filled": 0, "replaced": 0}

    # -- identity -------------------------------------------------------------
    def check_identity(self) -> list[str]:
        """Every way the pagerefs file fails to belong to this DDS and CRF (empty when it does)."""
        refs, dds, problems = self.refs, self.dds, []
        version = str(refs.get("schema_version") or "0")
        try:
            parsed = tuple(int(p) for p in version.split(".")[:2])
        except ValueError:
            parsed = (0,)
        if parsed < MIN_SCHEMA_VERSION:
            problems.append(f"pagerefs schema_version {version} is older than "
                            f"{'.'.join(map(str, MIN_SCHEMA_VERSION))}: re-run crfpdf")
        study = refs.get("study") or {}
        for label, theirs, ours in (("study OID", study.get("oid"), dds.get("studyOID")),
                                    ("MetaDataVersion OID", study.get("mdv_oid"), dds.get("OID")),
                                    ("FileOID", refs.get("file_oid"), dds.get("fileOID")),
                                    ("CreationDateTime", refs.get("creation_datetime"),
                                     dds.get("creationDateTime"))):
            if theirs != ours:
                problems.append(f"{label}: the pagerefs file has {theirs!r}, the DDS {ours!r}")
        try:
            sha = hashlib.sha256(Path(self.crf).read_bytes()).hexdigest()
        except OSError as exc:
            problems.append(f"cannot read --crf {self.crf}: {exc}")
        else:
            if refs.get("crf_sha256") != sha:
                problems.append(f"crf_sha256: the pagerefs file was made from another CRF than "
                                f"{self.crf} (re-run crfpdf on it)")
        href = self._leaf().get("href")
        pdf = Path(str(refs.get("pdf_file") or "")).name
        if href and pdf != Path(href).name:
            problems.append(f"the PDF is {pdf!r} but the DDS annotated CRF is {Path(href).name!r}")
        return problems

    def _leaf(self) -> dict[str, Any]:
        acrfs = self.dds.get("annotatedCRFs") or []
        return acrfs[0] if acrfs and isinstance(acrfs[0], dict) else {}

    # -- pins -----------------------------------------------------------------
    def load_review(self, path: str) -> None:
        """Read the pins of an answered ``origin-review.yaml``."""
        self.pins, self.extra_pins, self.answered = origin_review.read_pins(path)

    def _pin_for(self, oid: str, dataset: str, variable: str, vl_oid: str | None) -> Any:
        for key in (oid, vl_oid, f"{dataset}.{variable}"):
            if key and key in self.pins:
                return self.pins[key]
        return None

    # -- the merge --------------------------------------------------------------
    def process(self) -> dict[str, Any]:
        problems = self.check_identity()
        if problems:
            raise PagerefsError("the pagerefs file does not belong to this DDS and CRF:\n  - "
                                + "\n  - ".join(problems))
        leaf_id = self._leaf().get("leafID") or DEFAULT_LEAF_ID
        define = DefineIndex(self.dds)
        items = dds_io.define_items(self.dds)
        evidence_by_oid = self.refs.get("define_items") or {}

        for oid in evidence_by_oid:
            if oid not in items:
                self.review["unknownOids"][oid] = {"pin": self._answer("unknownOids", oid)}

        for oid, (dataset, variable, item, vl_oid) in items.items():
            stage_a = copy.deepcopy(item.get("origin") or [])
            evidence = evidence_by_oid.get(oid)
            source = "crf"
            if evidence is None:
                evidence = self._fallback(oid, dataset, variable, vl_oid, define)
                source = "fallback"
            pin = self._pin_for(oid, dataset, variable, vl_oid)
            crf_origins = self._origins(evidence or [], leaf_id)

            # "crf" accepts the CRF evidence and "ack" only acknowledges a review entry
            if pin is not None and not is_placeholder(pin) and pin not in ("crf", "ack"):
                pinned = self._apply_pin(pin, stage_a, crf_origins)
                if pinned is not None:
                    item["origin"] = pinned
                    self.report["pinned"] += 1
                if evidence and _real(stage_a) and _kinds(stage_a) != _kinds(crf_origins):
                    self.review["replaced"][oid] = self._replaced_entry(stage_a, crf_origins, pin)
                continue
            if not crf_origins:
                continue
            item["origin"] = crf_origins
            self.report["crfOrigins" if source == "crf" else "fallbackOrigins"] += 1
            if _real(stage_a) and _kinds(stage_a) != _kinds(crf_origins):
                self.report["replaced"] += 1
                self.review["replaced"][oid] = self._replaced_entry(
                    stage_a, crf_origins, pin if pin == "crf" else self._answer("replaced", oid))
            elif not _real(stage_a):
                self.report["filled"] += 1

        self._drop_parent_origins(items)
        self._collect_no_pages(items)
        for warning in self.refs.get("warnings") or []:
            if warning.get("check") == "define_oid_unpaired":
                text = warning.get("text") or ""
                self.review["unpaired"][text] = {"pin": self._answer("unpaired", text)}
        return self.dds

    def _fallback(self, oid: str, dataset: str, variable: str, vl_oid: str | None,
                  define: DefineIndex) -> list[dict[str, Any]]:
        """The key recipe, for a Define item the CRF names no OID for."""
        origins = self.refs.get("origins") or {}
        if vl_oid is None:
            if (dataset, variable) in define.value_lists:
                return []        # the origins belong on the value-level items
            return origins.get(f"{dataset}.{variable}") or []
        where = next((c.conditions for c in define.value_lists.get((dataset, variable)) or []
                      if c.oid == oid), None)
        if where is None:
            return []
        merged: dict[tuple, dict[str, Any]] = {}
        for annotation in self.refs.get("annotations") or []:
            for target in annotation.get("targets") or []:
                if target.get("dataset") != dataset or target.get("variable") != variable \
                        or target.get("define_item_oid"):
                    continue
                if not _target_matches(where, target.get("where") or []):
                    continue
                for entry in origins.get(target.get("key")) or []:
                    key = (entry.get("type"), entry.get("source"))
                    into = merged.setdefault(key, {**entry, "pages": []})
                    into["pages"] = sorted(set(into["pages"]) | set(entry.get("pages") or []))
        return list(merged.values())

    @staticmethod
    def _origins(evidence: list[dict[str, Any]], leaf_id: str) -> list[dict[str, Any]]:
        """CRF evidence as DDS origins. Derived origins get no description: the Define
        generator's post-processing writes the MethodDef placeholder."""
        out = []
        for entry in evidence:
            if not entry.get("type"):
                continue
            origin: dict[str, Any] = {"type": entry["type"],
                                      "source": entry.get("source") or PLACEHOLDER}
            pages = sorted({int(p) for p in entry.get("pages") or []})
            if pages:
                origin["documents"] = [{"leafID": leaf_id, "pages": pages}]
            out.append(origin)
        return out

    @staticmethod
    def _apply_pin(pin: Any, stage_a: list[dict[str, Any]],
                   crf_origins: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        """A pin's origin list, or None to leave the item as it is."""
        if pin in ("stageA", "keep"):
            return stage_a
        if pin == "ack":
            return None
        if isinstance(pin, dict) and pin.get("type"):
            origin: dict[str, Any] = {"type": pin["type"], "source": pin.get("source") or PLACEHOLDER}
            # the aCRF pages are evidence for the same type and source only (a pinned
            # Collected/Vendor origin is not on the CRF)
            same = next((o for o in crf_origins if o["type"] == origin["type"]
                         and o["source"] in (origin["source"], PLACEHOLDER)), None)
            if same and same.get("documents"):
                origin["documents"] = same["documents"]
            return [origin]
        logger.warning("ignored pin %r: use crf, stageA, ack or {type, source}", pin)
        return None

    def _replaced_entry(self, stage_a, crf_origins, pin) -> dict[str, Any]:
        return {"stageA": _describe(stage_a), "crf": _describe(crf_origins), "pin": pin}

    def _answer(self, section: str, key: str) -> Any:
        """The pin a previous review file gave this entry, so answers survive regeneration."""
        return self.answered.get(section, {}).get(key, PLACEHOLDER)

    def _drop_parent_origins(self, items) -> None:
        """A variable whose value-level items carry origins keeps none of its own."""
        with_origins = {(d, v) for d, v, item, vl in items.values() if vl and item.get("origin")}
        for dataset, variable, item, vl_oid in items.values():
            if vl_oid is None and (dataset, variable) in with_origins and "origin" in item:
                if not any(o.get("documents") for o in item.get("origin") or []):
                    del item["origin"]

    def _collect_no_pages(self, items) -> None:
        for oid, (_, _, item, _) in items.items():
            origins = item.get("origin") or []
            if any((o.get("type"), o.get("source")) == COLLECTED_INVESTIGATOR
                   and not o.get("documents") for o in origins):
                pin = self.pins.get(oid, self._answer("noPages", oid))
                self.review["noPages"][oid] = {"origin": _describe(origins), "pin": pin}

    # -- outputs ----------------------------------------------------------------
    def open_items(self) -> dict[str, int]:
        """Review entries still unanswered, per section."""
        return {section: sum(1 for entry in entries.values() if is_placeholder(entry.get("pin")))
                for section, entries in self.review.items()}

    def save(self) -> None:
        dds_io.save_dds(self.dds, self.dds_out, self.wrapped)

    def write_review(self, path: str) -> None:
        origin_review.write_review(path, self.review, self.extra_pins)

    def summary(self) -> str:
        r, open_items = self.report, self.open_items()
        lines = [
            "",
            "Pagerefs loader summary",
            "-----------------------",
            f"  origins from the CRF ..... {r['crfOrigins']}",
            f"  origins by key recipe .... {r['fallbackOrigins']}",
            f"  placeholders filled ...... {r['filled']}",
            f"  origins replaced ......... {r['replaced']}",
            f"  pinned ................... {r['pinned']}",
        ]
        lines += [f"  open {name:.<21} {count}" for name, count in open_items.items()]
        return "\n".join(lines)


def _real(origins: list[dict[str, Any]]) -> bool:
    """Whether an origin list says something: not missing, not only placeholders."""
    return any(o.get("type") and not is_placeholder(o.get("type")) for o in origins or [])


def _kinds(origins: list[dict[str, Any]]) -> set[tuple]:
    return {(o.get("type"), o.get("source")) for o in origins or []}


def _describe(origins: list[dict[str, Any]]) -> str:
    parts = []
    for o in origins or []:
        pages = [p for d in o.get("documents") or [] for p in d.get("pages") or []]
        text = f"{o.get('type')}/{o.get('source')}"
        if pages:
            text += " p. " + " ".join(str(p) for p in sorted(set(pages)))
        parts.append(text)
    return "; ".join(parts) or "none"


def _target_matches(where: dict[str, tuple], conditions: list[dict[str, Any]]) -> bool:
    """The README recipe: annotation conditions admitted by a tested variable, concept
    conditions admitted where the where clause tests their variable."""
    for condition in conditions:
        tested = where.get(condition.get("variable"))
        values = condition.get("values") or []
        if condition.get("source") == "concept":
            if tested is not None and not all(admits(tested[0], tested[1], v) for v in values):
                return False
            continue
        if tested is None:
            return False
        if condition.get("comparator") == "NE":
            if tested != ("NE", tuple(values)):
                return False
        elif not all(admits(tested[0], tested[1], v) for v in values):
            return False
    return True


def set_cmd_line_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m loaders.pagerefs",
        description="Merge acrf.pagerefs.json into the DDS as Define-XML Origin (Stage E).")
    parser.add_argument("--dds_in", required=True, help="the CRF-enriched DDS the CRF came from")
    parser.add_argument("--pagerefs", required=True, help="acrf.pagerefs.json written by crfpdf")
    parser.add_argument("--crf", required=True, help="the ODM CRF crfpdf rendered (checked by sha256)")
    parser.add_argument("--dds_out", required=True, help="the DDS to write, with origins")
    parser.add_argument("--patch_file", help="the origin-review.yaml to write")
    parser.add_argument("--apply_patch", help="an answered origin-review.yaml whose pins to apply")
    parser.add_argument("--validate", nargs="?", const="default", default=None,
                        help="validate the output against the CRF profile JSON Schema")
    parser.add_argument("-l", "--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = set_cmd_line_args()
    logging.basicConfig(level=getattr(logging, args.log_level),
                        format="%(levelname)s - %(name)s - %(message)s")
    try:
        loader = PagerefsLoader(args.dds_in, args.pagerefs, args.crf, args.dds_out)
        if args.apply_patch:
            loader.load_review(args.apply_patch)
        loader.process()
    except PagerefsError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    loader.save()
    print(f"✅ DDS with origins written to {args.dds_out}")
    if args.patch_file:
        loader.write_review(args.patch_file)
        print(f"✅ origin review written to {args.patch_file}")
    print(loader.summary())
    if args.validate:
        from loaders.common.profiles import validate_against_profile
        schema = (Path(__file__).resolve().parents[3] / "schemas" / "dds" / "profiles" / "crf"
                  / "crf.schema.json") if args.validate == "default" else Path(args.validate)
        errors = validate_against_profile(loader.dds, str(schema))
        for error in errors[:20]:
            print(f"  ✗ {error}")
        if errors:
            print(f"❌ profile validation FAILED — {len(errors)} error(s)")
            sys.exit(1)
        print("✅ profile validation passed")


if __name__ == "__main__":
    main()
