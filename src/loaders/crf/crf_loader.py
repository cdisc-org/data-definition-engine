"""crf_loader.py - the DDE's CRF loader.

Reads the Define DDS produced by ``create_define_json.py`` plus the USDM study design,
resolves each Biomedical Concept to a CRF Specialization, enriches it with CDASHIG and
CDASH CT, and writes a **combined DDS** carrying both Define-XML and CRF metadata. The
combined file is the contract: ``define_generator.py`` and ``crf_generator.py`` each read
it and ignore the sections they do not own.

Example::

    python crf_loader.py \\
        --dds_in  ../../../output/NCT01797120-dds.json \\
        --usdm_file ../../../data/protocols/NCT01797120/NCT01797120-latest.json \\
        --dds_out ../../../output/NCT01797120-dds-crf.json \\
        --crf_spec_file ../../../data/crf_specializations/cdisc_crf_specializations_draft.csv \\
        --cdashig 2.3 --cdashct 2026-03-27 \\
        --patch_file ../../../output/crf-refinement.yaml --validate --debug
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

# Importable both as ``python crf_loader.py`` from this directory and as
# ``python -m loaders.crf.crf_loader`` from ``src/``.
_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from loaders.common import dds_io, usdm_bc, usdm_study  # noqa: E402
from loaders.common.library_cache import (DEFAULT_CACHE_DIR,  # noqa: E402
                                          CachingLibraryClient)
from loaders.common.profiles import (profile_extension_slots,  # noqa: E402
                                     strip_extensions, validate_against_profile,
                                     write_validation_excel)
from loaders.crf import patch as crf_patch  # noqa: E402
from loaders.crf.builders.codelists import CodeListBuilder  # noqa: E402
from loaders.crf.builders.forms import FormBuilder  # noqa: E402
from loaders.crf.builders.items import ItemBuilder  # noqa: E402
from loaders.crf.builders.study_events import StudyEventBuilder  # noqa: E402
from loaders.crf.constants import (ACRF_HREF, ACRF_LEAF_ID, CRF_PROFILE_URI,  # noqa: E402
                                   DEFAULT_CDASHIG_VERSION,
                                   DEFAULT_IMPLEMENTATION_OPTION, DEFINE_PROFILE_URI,
                                   PLACEHOLDER, STD_CDASHCT_OID)
from loaders.crf.sources.cdash_ct import CdashCtSource  # noqa: E402
from loaders.crf.sources.cdashig import CdashigSource  # noqa: E402
from loaders.crf.sources.crf_specializations import open_source  # noqa: E402
from loaders.crf.standards import crf_standards, merge_standards  # noqa: E402

logger = logging.getLogger("crf_loader")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REPO_ROOT = _SRC.parent
DEFAULT_CRF_SCHEMA = REPO_ROOT / "schemas" / "dds" / "profiles" / "crf" / "crf.schema.json"
DEFAULT_CRF_PROFILE = REPO_ROOT / "schemas" / "dds" / "profiles" / "crf" / "profile.yaml"


class CrfLoader:
    """Enriches a Define DDS with CRF metadata."""

    def __init__(self, dds_in: str, usdm_file: str, dds_out: str,
                 crf_spec_file: str | None = None, crf_spec_source: str = "auto",
                 cdashig: str = DEFAULT_CDASHIG_VERSION, cdashct: str | None = None,
                 sdtmct: str | None = None, cdisc_api_key: str | None = None,
                 base_api_url: str | None = None,
                 implementation_option: str = DEFAULT_IMPLEMENTATION_OPTION,
                 studyversion: int = 0, studydesign: int = 0,
                 timeline: str | None = None, include_uncovered: bool = False,
                 cache_dir: str = DEFAULT_CACHE_DIR, use_cache: bool = True,
                 debug: bool = False) -> None:
        if cdashct and not DATE_RE.match(cdashct):
            raise ValueError("cdashct must be in yyyy-mm-dd format")
        if sdtmct and not DATE_RE.match(sdtmct):
            raise ValueError("sdtmct must be in yyyy-mm-dd format")

        self.dds_in = dds_in
        self.usdm_file = usdm_file
        self.dds_out = dds_out
        self.crf_spec_file = crf_spec_file
        self.crf_spec_source = crf_spec_source
        self.cdashig_version = cdashig
        self.cdashct = cdashct
        self.sdtmct = sdtmct
        self.implementation_option = implementation_option
        self.studyversion = studyversion
        self.studydesign = studydesign
        self.timeline = timeline
        self.include_uncovered = include_uncovered
        self.debug = debug

        self.dds, self.wrapped = dds_io.load_dds(dds_in)
        with open(usdm_file, "r", encoding="utf-8") as f:
            self.usdm = json.load(f)

        self.client = self._make_client(cdisc_api_key, base_api_url, cache_dir, use_cache)
        self.spec_source = open_source(crf_spec_file, crf_spec_source, self.client)
        self.cdashig = CdashigSource(self.client, cdashig)
        self.cdash_ct = CdashCtSource(self.client, cdashct or "", self.sdtmct)

        self.report: dict[str, Any] = {
            "forms": 0, "concepts": 0, "items": 0, "codeLists": 0,
            "uncovered": [], "groupChoices": {}, "unboundEvents": [],
            "placeholders": [], "conflicts": [], "normalized": [],
        }
        self.debug_data: dict[str, Any] = {}

    # -- setup ----------------------------------------------------------------
    def _make_client(self, api_key: str | None, base_api_url: str | None,
                     cache_dir: str, use_cache: bool) -> Any:
        from cdisc_library_client import CDISCLibraryClient
        from dotenv import find_dotenv, load_dotenv

        # find_dotenv() starts at this module's directory, so a .env kept beside the
        # Define loader is not visible here. Try the repo root and that directory too.
        load_dotenv()
        for candidate in (REPO_ROOT / ".env", _SRC / "define-xml" / ".env"):
            if candidate.is_file():
                load_dotenv(candidate, override=False)
        if not api_key:
            api_key = os.getenv("CDISC_API_KEY")
        if not api_key:
            raise ValueError(
                "A CDISC Library API key is required: pass --cdisc_api_key, set "
                "CDISC_API_KEY, or put it in a .env file."
            )
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_api_url:
            kwargs["base_api_url"] = base_api_url
        return CachingLibraryClient(CDISCLibraryClient(**kwargs), cache_dir, use_cache)

    # -- pipeline -------------------------------------------------------------
    def process(self) -> dict[str, Any]:
        """Run the full enrichment pipeline and return the combined DDS."""
        self._normalize_input()
        soa = self._read_soa()
        bcs = self._resolve_bcs()
        resolutions = self._select_groups(bcs)
        forms = self._build_forms(soa, bcs, resolutions)
        events = self._build_study_events(soa, forms)
        self._assemble(forms, events)
        if self.debug:
            self._write_debug()
        return self.dds

    def _normalize_input(self) -> None:
        changes = dds_io.normalize_dds(self.dds)
        for change in changes:
            logger.info("normalized input: %s", change)
        if not self.dds.get("studyName") or self.dds.get("studyName") == "None":
            header = usdm_study.study_header(self.usdm, self.studyversion, self.studydesign)
            self.dds.update(header)
            logger.warning(
                "input DDS had no studyName; recomputed the header from the USDM "
                "(studyName=%s). OIDs containing 'None' were rewritten.",
                header["studyName"],
            )
        print(f"✅ input DDS normalized — {len(changes)} repair(s)")

    def _read_soa(self) -> Any:
        from loaders.crf.usdm.soa import SoA

        design = usdm_study.study_design(self.usdm, self.studyversion, self.studydesign)
        soa = SoA(design, self.timeline)
        self.debug_data["soa"] = soa.summary()
        print(f"✅ SoA read — {len(soa.activities)} activities, "
              f"{len(soa.encounters)} encounters")
        return soa

    def _resolve_bcs(self) -> dict[str, dict[str, Any]]:
        """Resolve every USDM Biomedical Concept to its ids and DDS concept OID."""
        concept_oids = {c.get("OID") for c in self.dds.get("concepts") or []}
        resolved: dict[str, dict[str, Any]] = {}
        for bc in usdm_bc.usdm_biomedical_concepts(self.usdm, self.studyversion):
            bc_id = bc.get("id")
            if not bc_id:
                continue
            concept_oid = f"CONC.{bc_id}"
            resolved[bc_id] = {
                "usdm_id": bc_id,
                "name": bc.get("name") or bc_id,
                "code": usdm_bc.usdm_bc_code(bc),
                "sdtm_dss_ids": usdm_bc.usdm_specialization_ids(bc, "sdtm"),
                "crf_spec_ids": usdm_bc.usdm_specialization_ids(bc, "crf"),
                # Reuse the concept the Define loader already wrote; never re-fetch.
                "concept_oid": concept_oid if concept_oid in concept_oids else None,
            }
        self.debug_data["bc_resolution"] = resolved
        print(f"✅ biomedical concepts resolved — {len(resolved)}")
        return resolved

    def _select_groups(self, bcs: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Choose one CRF specialization group per Biomedical Concept.

        Priority: an explicit USDM ``crf`` extension, then the SDTM dataset
        specialization id, then the BC's own C-code. Ties among several groups are broken
        by ``--implementation_option`` then by a blank scenario, and recorded for the
        refinement file either way.
        """
        groups = self.spec_source.groups()
        by_vlm = self.spec_source.index_by_vlm()
        by_bc = self.spec_source.index_by_bc()

        selected: dict[str, Any] = {}
        for bc_id, bc in bcs.items():
            candidates: list[Any] = []
            for spec_id in bc["crf_spec_ids"]:
                if spec_id in groups:
                    candidates = [groups[spec_id]]
                    break
            if not candidates:
                for dss_id in bc["sdtm_dss_ids"]:
                    candidates.extend(by_vlm.get(dss_id) or [])
            if not candidates and bc["code"]:
                candidates = list(by_bc.get(bc["code"]) or [])

            if not candidates:
                self.report["uncovered"].append({"code": bc["code"], "name": bc["name"]})
                continue

            chosen = self._break_tie(candidates)
            if len(candidates) > 1:
                self.report["groupChoices"][bc["code"] or bc_id] = {
                    "selected": chosen.crf_group_id,
                    "candidates": sorted(c.crf_group_id for c in candidates),
                }
                logger.warning("BC %s (%s) matched %d CRF groups; chose %s",
                               bc["name"], bc["code"], len(candidates), chosen.crf_group_id)
            if chosen.is_normalized:
                self.report["normalized"].append(chosen.crf_group_id)
            selected[bc_id] = chosen

        self.debug_data["group_selection"] = {
            k: v.crf_group_id for k, v in selected.items()
        }
        print(f"✅ CRF groups selected — {len(selected)} covered, "
              f"{len(self.report['uncovered'])} uncovered")
        return selected

    def _placeholder_group(self, bc: dict[str, Any]) -> Any:
        """A stub CRF group for a concept no specialization covers (--include_uncovered).

        The concept appears on the form with a single obviously-unfinished field, so the
        gap is visible where it matters instead of only in the refinement file. Nothing
        here is invented metadata: the question is the ``__PLACEHOLDER__`` sentinel and a
        human must answer it before the CRF is usable.
        """
        from loaders.crf.sources.crf_specializations import CrfGroup, CrfItem

        code = bc.get("code") or bc.get("usdm_id") or "UNKNOWN"
        name = bc.get("name") or code
        group = CrfGroup(crf_group_id=f"UNCOVERED_{code}", bc_id=bc.get("code") or "",
                         short_name=name)
        group.items = [CrfItem(crf_item=f"UNCOVERED_{code}", variable_name="",
                               question_text=PLACEHOLDER, order_number=1,
                               mandatory_variable="N", data_type="text")]
        logger.warning("emitting a placeholder concept for uncovered %s (%s)", name, code)
        return group

    def _break_tie(self, candidates: list[Any]) -> Any:
        preferred = [c for c in candidates
                     if (c.implementation_option or "").lower()
                     == self.implementation_option.lower()]
        pool = preferred or candidates
        blank_scenario = [c for c in pool if not c.scenario]
        pool = blank_scenario or pool
        return sorted(pool, key=lambda c: c.crf_group_id)[0]

    def _build_forms(self, soa: Any, bcs: dict[str, dict[str, Any]],
                     selected: dict[str, Any]) -> list[dict[str, Any]]:
        sdtm_item_oids = {
            item.get("OID")
            for group in self.dds.get("itemGroups") or []
            for item in dds_io.all_items(group)
            if item.get("OID")
        }
        property_by_dec = self._property_index()

        self.codelist_builder = CodeListBuilder(self.cdash_ct, self.cdashct or "")
        self.item_builder = ItemBuilder(self.cdashig, self.codelist_builder, sdtm_item_oids)
        package_date = next(
            (g.package_date for g in self.spec_source.groups().values() if g.package_date), "")
        self.form_builder = FormBuilder(self.item_builder, package_date)

        forms: list[dict[str, Any]] = []
        self.form_oid_by_activity: dict[str, str] = {}
        for activity in soa.activities:
            resolutions = []
            for bc_id in activity.biomedical_concept_ids:
                bc = bcs.get(bc_id) or {}
                group = selected.get(bc_id)
                if group is None:
                    # Record which activity wanted this concept, so the refinement file
                    # tells the curators where the gap actually hurts.
                    for entry in self.report["uncovered"]:
                        if entry["code"] == bc.get("code") and "activity" not in entry:
                            entry["activity"] = activity.name
                    if not self.include_uncovered:
                        continue
                    group = self._placeholder_group(bc)
                resolutions.append({
                    "group": group,
                    "concept_oid": bc.get("concept_oid"),
                    "bc_name": bc.get("name"),
                })
            if not resolutions:
                logger.info("activity %s has no covered concepts - no form built",
                            activity.name)
                continue
            form = self.form_builder.build_form(activity, resolutions, property_by_dec)
            forms.append(form)
            self.form_oid_by_activity[activity.id] = form["OID"]

        self.report["forms"] = len(forms)
        self.report["concepts"] = sum(
            len(s.get("slices") or []) for f in forms for s in f.get("slices") or [])
        self.report["conflicts"] = self.item_builder.conflicts
        self.report["placeholders"] = sorted(self.item_builder.placeholders)
        print(f"✅ forms built — {len(forms)} form(s), {self.report['concepts']} concept(s)")
        return forms

    def _property_index(self) -> dict[str, str]:
        """Map a DEC C-code to the conceptProperty OID the Define loader wrote."""
        index: dict[str, str] = {}
        for concept in self.dds.get("concepts") or []:
            for prop in concept.get("properties") or []:
                if not isinstance(prop, dict):
                    continue
                for coding in prop.get("coding") or []:
                    code = coding.get("code")
                    if code and code not in index and prop.get("OID"):
                        index[code] = prop["OID"]
        for prop in self.dds.get("conceptProperties") or []:
            for coding in prop.get("coding") or []:
                code = coding.get("code")
                if code and code not in index and prop.get("OID"):
                    index[code] = prop["OID"]
        return index

    def _build_study_events(self, soa: Any, forms: list[dict[str, Any]]) -> list[dict[str, Any]]:
        builder = StudyEventBuilder(soa)
        events = builder.build(self.form_oid_by_activity)
        self.report["unboundEvents"] = builder.unbound
        print(f"✅ study events built — {len(events)} visit(s), "
              f"{len(builder.unbound)} unbound")
        return events

    def _assemble(self, forms: list[dict[str, Any]], events: list[dict[str, Any]]) -> None:
        self.dds.setdefault("itemGroups", []).extend(forms)
        code_lists = self.codelist_builder.as_list()
        self.dds.setdefault("codeLists", []).extend(code_lists)
        self.dds["standards"] = merge_standards(
            self.dds.get("standards") or [],
            crf_standards(self.cdashig_version, self.cdashct or ""),
        )
        self.dds["studyEvents"] = events

        acrfs = self.dds.setdefault("annotatedCRFs", [])
        if not any(a.get("leafID") == ACRF_LEAF_ID for a in acrfs):
            acrfs.append({"leafID": ACRF_LEAF_ID, "title": "Annotated CRF", "href": ACRF_HREF})

        profiles = self.dds.setdefault("profile", [])
        for uri in (DEFINE_PROFILE_URI, CRF_PROFILE_URI):
            if uri not in profiles:
                profiles.append(uri)

        self.report["items"] = len(self.item_builder.items)
        self.report["codeLists"] = len(code_lists)
        print(f"✅ DDS assembled — {self.report['items']} CRF item(s), "
              f"{len(code_lists)} CRF codelist(s)")

    # -- outputs --------------------------------------------------------------
    def save(self) -> None:
        dds_io.save_dds(self.dds, self.dds_out, self.wrapped)
        print(f"✅ combined DDS written to {self.dds_out}")

    def _write_debug(self) -> None:
        out_dir = Path(self.dds_out).parent
        self.debug_data["cdashig_fields"] = {
            domain: sorted(fields) for domain, fields in self.cdashig._domains.items()
        }
        for name, payload in self.debug_data.items():
            path = out_dir / f"debug_crf_{name}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, default=str)
        print(f"✅ debug files written to {out_dir}")

    def generate_patch_file(self, path: str) -> None:
        crf_patch.generate_patch_file(path, self.dds, {
            "crfGroupChoices": self.report["groupChoices"],
            "uncoveredConcepts": self.report["uncovered"],
            "formCandidates": sorted(self.form_oid_by_activity.values()),
        })
        print(f"✅ refinement file written to {path}")

    def apply_patch(self, path: str) -> None:
        changes = crf_patch.apply_patch_file(path, self.dds)
        print(f"✅ refinement applied — {len(changes)} change(s)")

    def validate(self, schema: str, report: str | None = None) -> bool:
        """Validate the combined DDS against the CRF profile, and the stripped instance
        against the Define profile when that schema is present."""
        errors = validate_against_profile(self.dds, schema)
        for error in errors[:20]:
            print(f"  ✗ {error}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")
        if report:
            write_validation_excel(errors, report, self.dds, self.dds_out, schema)
        if errors:
            print(f"❌ CRF profile validation FAILED — {len(errors)} error(s)")
        else:
            print("✅ CRF profile validation passed")
        return not errors

    def summary(self) -> str:
        r = self.report
        lines = [
            "",
            "CRF loader summary",
            "------------------",
            f"  forms built .............. {r['forms']}",
            f"  concepts ................. {r['concepts']}",
            f"  CRF items ................ {r['items']}",
            f"  CRF codelists ............ {r['codeLists']}",
            f"  concepts uncovered ....... {len(r['uncovered'])}",
            f"  group choices to confirm . {len(r['groupChoices'])}",
            f"  normalized groups ........ {len(r['normalized'])}",
            f"  unbound study events ..... {len(r['unboundEvents'])}",
            f"  question placeholders .... {len(r['placeholders'])}",
            f"  item conflicts ........... {len(r['conflicts'])}",
        ]
        if isinstance(self.client, CachingLibraryClient):
            lines.append(f"  {self.client.summary()}")
        for conflict in r["conflicts"][:5]:
            lines.append(f"    ! {conflict}")
        return "\n".join(lines)


def set_cmd_line_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add CRF metadata to a DDS JSON file (DDS in -> DDS out).")
    parser.add_argument("--dds_in", required=True,
                        help="path to the Define DDS JSON produced by create_define_json.py")
    parser.add_argument("--usdm_file", required=True, help="path to the USDM JSON file")
    parser.add_argument("--dds_out", required=True, help="path of the combined DDS to write")
    parser.add_argument("--crf_spec_file",
                        help="CRF specializations .csv/.xlsx (required unless "
                             "--crf_spec_source library)")
    parser.add_argument("--crf_spec_source", default="auto",
                        choices=["auto", "csv", "xlsx", "library"],
                        help="how to read the CRF specializations (default: from the "
                             "file extension)")
    parser.add_argument("--cdashig", default=DEFAULT_CDASHIG_VERSION,
                        help=f"CDASHIG version (default: {DEFAULT_CDASHIG_VERSION})")
    parser.add_argument("--cdashct", required=True,
                        help="CDASH CT package date, yyyy-mm-dd")
    parser.add_argument("--sdtmct",
                        help="SDTM CT package date used as codelist fallback, yyyy-mm-dd "
                             "(default: the STD.SDTMCT version in --dds_in)")
    parser.add_argument("--cdisc_api_key", help="CDISC Library API key "
                                                "(default: CDISC_API_KEY env or .env)")
    parser.add_argument("--base_api_url", help="override the CDISC Library base URL")
    parser.add_argument("--implementation_option", default=DEFAULT_IMPLEMENTATION_OPTION,
                        choices=["Denormalized", "Normalized"],
                        help="preferred option when a concept has several CRF groups")
    parser.add_argument("--studyversion", type=int, default=0, help="USDM study version index")
    parser.add_argument("--studydesign", type=int, default=0, help="USDM study design index")
    parser.add_argument("--timeline", help="schedule timeline name (default: mainTimeline)")
    parser.add_argument("--patch_file", help="path of the CRF refinement YAML to write")
    parser.add_argument("--apply_patch", help="apply this refinement YAML before writing")
    parser.add_argument("--validate", nargs="?", const=str(DEFAULT_CRF_SCHEMA), default=None,
                        help="validate against the CRF profile JSON Schema")
    parser.add_argument("--validation_report", help="path of the xlsx validation report")
    parser.add_argument("--cache_dir", default=DEFAULT_CACHE_DIR,
                        help=f"CDISC Library cache directory (default: {DEFAULT_CACHE_DIR})")
    parser.add_argument("--no_cache", action="store_true", help="bypass the Library cache")
    parser.add_argument("--include_uncovered", action="store_true",
                        help="emit placeholder concepts for BCs with no CRF specialization")
    parser.add_argument("--debug", action="store_true", help="write debug_crf_*.json files")
    parser.add_argument("-l", "--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="logging level (default: INFO)")

    args = parser.parse_args()
    if args.apply_patch and not args.patch_file:
        parser.error("--patch_file is required with --apply_patch so the refinement file "
                     "is refreshed after applying")
    if args.crf_spec_source != "library" and not args.crf_spec_file:
        parser.error("--crf_spec_file is required unless --crf_spec_source library")
    return args


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = set_cmd_line_args()
    logging.basicConfig(
        filename="crf_loader.log", level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    sdtmct = args.sdtmct
    if not sdtmct:
        try:
            dds, _ = dds_io.load_dds(args.dds_in)
            sdtmct = next((s.get("version") for s in dds.get("standards") or []
                           if s.get("OID") == "STD.SDTMCT"), None)
        except (OSError, json.JSONDecodeError):
            sdtmct = None

    try:
        loader = CrfLoader(
            dds_in=args.dds_in, usdm_file=args.usdm_file, dds_out=args.dds_out,
            crf_spec_file=args.crf_spec_file, crf_spec_source=args.crf_spec_source,
            cdashig=args.cdashig, cdashct=args.cdashct, sdtmct=sdtmct,
            cdisc_api_key=args.cdisc_api_key, base_api_url=args.base_api_url,
            implementation_option=args.implementation_option,
            studyversion=args.studyversion, studydesign=args.studydesign,
            timeline=args.timeline, include_uncovered=args.include_uncovered,
            cache_dir=args.cache_dir, use_cache=not args.no_cache, debug=args.debug,
        )
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    loader.process()
    if args.apply_patch:
        loader.apply_patch(args.apply_patch)
    loader.save()
    if args.patch_file:
        loader.generate_patch_file(args.patch_file)
    print(loader.summary())

    if args.validate:
        if not loader.validate(args.validate, args.validation_report):
            sys.exit(1)


if __name__ == "__main__":
    main()
