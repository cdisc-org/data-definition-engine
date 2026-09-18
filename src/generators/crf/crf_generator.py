"""crf_generator.py - generate ODM CRFs and annotated CRFs from a DDS JSON file.

Emits ODM v1.3.2 or ODM v2.0 from the combined DDS that ``crf_loader.py`` writes. The
SDTM dataset mapping annotations are **always** embedded (as ``Alias Context=SDTM`` in
both versions, alongside ODM 2.0's native ``Coding``), so one ODM file serves as both the
blank CRF and the aCRF — which of the two you see is a rendering choice
(``displayAnnotations``), not a different document.

Example::

    python crf_generator.py -t ../../../output/NCT01797120-dds-crf.json \\
        -o ../../../output/crf-2.0.xml --odm-version 2.0 --validate
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Importable both as ``python crf_generator.py`` from this directory and as
# ``python -m generators.crf.crf_generator`` from ``src/``.
_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from generators.crf import annotatedCRF, codeLists, itemGroups  # noqa: E402
from generators.crf import post_processing as PP  # noqa: E402
from generators.crf import standards, studyEvents  # noqa: E402
from generators.crf.constants import (DEFAULT_LANGUAGE, ODM_VERSIONS)  # noqa: E402
from generators.crf.targets import get_target  # noqa: E402
from generators.crf.validate import validate_odm  # noqa: E402

logger = logging.getLogger("crf_generator")

#: DDS section -> loader class.
LOADERS = {
    "standards": standards.Standards,
    "annotatedCRFs": annotatedCRF.AnnotatedCRF,
    "codeLists": codeLists.CodeLists,
    "itemGroups": itemGroups.ItemGroups,
    "studyEvents": studyEvents.StudyEvents,
}

#: Dispatch order. ``standards`` must precede ``studyEvents`` (the Protocol carries the
#: standard aliases) and ``itemGroups`` must precede ``studyEvents`` (events reference
#: forms). ``codeLists`` precedes ``itemGroups`` only for readable document order.
SECTION_ORDER = ["standards", "annotatedCRFs", "codeLists", "itemGroups", "studyEvents"]

#: Object containers shared by every loader.
CONTAINERS = ("FormDef", "ItemGroupDef", "ItemDef", "CodeList", "StudyEventDef",
              "StudyEventGroupDef", "Leaf")

HEADER_KEYS = ("OID", "name", "description", "fileOID", "creationDateTime", "fileType",
               "originator", "sourceSystem", "sourceSystemVersion", "context",
               "studyOID", "studyName", "studyDescription", "protocolName")


class CrfGenerator:
    """Generate an ODM CRF from a DDS JSON file."""

    def __init__(self, dds_file: str, odm_file: str, odm_version: str = "2.0",
                 log_level: str = "INFO", include_hidden: bool = False,
                 forms: list[str] | None = None,
                 prune_codelists: bool = True) -> None:
        """
        :param dds_file: path to the combined DDS JSON
        :param odm_file: path of the ODM XML to write
        :param odm_version: ``"1.3.2"`` or ``"2.0"``
        :param include_hidden: emit items flagged ``crfDisplayHidden``
        :param forms: only emit these Form OIDs
        :param prune_codelists: drop CodeLists no CRF item references
        """
        if odm_version not in ODM_VERSIONS:
            raise ValueError(f"odm_version must be one of {ODM_VERSIONS}")
        if not Path(dds_file).is_file():
            raise ValueError(f"The DDS file cannot be found: {dds_file}")

        self.dds_file = dds_file
        self.odm_file = odm_file
        self.odm_version = odm_version
        self.include_hidden = include_hidden
        self.forms = forms
        self.prune_codelists = prune_codelists
        self.lang = DEFAULT_LANGUAGE
        self.crf_objects: dict[str, Any] = {}
        self.warnings: list[str] = []

        logging.basicConfig(
            filename="crf_generator.log", level=getattr(logging, log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        self.target = get_target(odm_version)

    def create(self) -> Any:
        """Run the pipeline and return the odmlib ODM root."""
        template = self._load()
        self._init_objects(template)
        for section in SECTION_ORDER:
            value = template.get(section)
            if section == "annotatedCRFs" and value is None:
                value = template.get("annotatedCRF")  # legacy singular key
            if not isinstance(value, list):
                continue
            logger.info("processing %s", section)
            LOADERS[section]().create_crf_objects(value, self.crf_objects,
                                                  self.target, self.lang)

        pp = PP.PostProcessing(self.crf_objects, template, self.target,
                               self.prune_codelists)
        pp.process()
        self.warnings = pp.warnings

        header = {k: template.get(k) for k in HEADER_KEYS}
        odm = self.target.assemble(header, self.crf_objects, self.lang)
        return odm

    def _load(self) -> dict[str, Any]:
        try:
            with open(self.dds_file, "r", encoding="utf-8") as f:
                template = json.load(f)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in %s: %s at line %s", self.dds_file, e.msg, e.lineno)
            print(f"ERROR: Invalid JSON in {self.dds_file}: {e.msg} at line {e.lineno}",
                  file=sys.stderr)
            sys.exit(1)
        # crf_loader.py writes the DDS unwrapped, but accept the wrapped shape too.
        if "metaDataVersion" in template and isinstance(template["metaDataVersion"], dict):
            template = template["metaDataVersion"]
        if template.get("language"):
            self.lang = template["language"]
        return template

    def _init_objects(self, template: dict[str, Any]) -> None:
        for name in CONTAINERS:
            self.crf_objects[name] = []
        self.crf_objects["Standards"] = None
        self.crf_objects["AnnotatedCRF"] = None
        self.crf_objects["Protocol"] = None
        self.crf_objects["_include_hidden"] = self.include_hidden
        self.crf_objects["_standards"] = []

        # A target sometimes needs a sibling it is not being handed: ODM 1.3.2 reads the
        # unit value off the item that a result item's ``unitsItem`` points at.
        self.target.set_item_index(_index_items(template))
        if hasattr(self.target, "codelist_index"):
            self.target.codelist_index = {
                cl["OID"]: cl for cl in template.get("codeLists") or [] if cl.get("OID")
            }
        if self.forms:
            known = {g.get("OID") for g in template.get("itemGroups") or []
                     if g.get("type") == "Form"}
            unknown = [f for f in self.forms if f not in known]
            if unknown:
                raise ValueError(f"--forms names unknown Form OID(s): {', '.join(unknown)}")
            self.crf_objects["_form_filter"] = set(self.forms)

    def write(self, odm: Any) -> str:
        """Serialize and write the ODM file. Returns the XML string."""
        xml = self.target.to_xml_string(odm)
        Path(self.odm_file).parent.mkdir(parents=True, exist_ok=True)
        with open(self.odm_file, "w", encoding="utf-8") as f:
            f.write(xml)
        return xml

    def summary(self) -> str:
        counts = {name: len(self.crf_objects.get(name) or []) for name in CONTAINERS}
        form_count = counts["FormDef"] or sum(
            1 for g in self.crf_objects.get("ItemGroupDef", [])
            if vars(g).get("Type") == "Form")
        lines = [
            "",
            f"CRF generator summary (ODM {self.odm_version})",
            "-------------------------------------",
            f"  forms .................... {form_count}",
            f"  item groups .............. {counts['ItemGroupDef']}",
            f"  items .................... {counts['ItemDef']}",
            f"  codelists ................ {counts['CodeList']}",
            f"  study events ............. {counts['StudyEventDef']}",
        ]
        if self.odm_version == "2.0":
            lines.append(f"  study event groups ....... {counts['StudyEventGroupDef']}")
        if getattr(self.target, "measurement_units", None):
            lines.append(f"  measurement units ........ {len(self.target.measurement_units)}")
        for warning in self.warnings:
            lines.append(f"  ! {warning}")
        return "\n".join(lines)


def _index_items(template: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index every item in the DDS by OID, walking itemGroups and their slices."""
    index: dict[str, dict[str, Any]] = {}

    def walk(group: dict[str, Any]) -> None:
        for item in group.get("items") or []:
            if item.get("OID"):
                index.setdefault(item["OID"], item)
        for slice_group in group.get("slices") or []:
            walk(slice_group)

    for group in template.get("itemGroups") or []:
        walk(group)
    for item in template.get("items") or []:
        if item.get("OID"):
            index.setdefault(item["OID"], item)
    return index


def set_cmd_line_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an ODM CRF (blank and SDTM-annotated) from a DDS JSON file.")
    parser.add_argument("-t", "--template", dest="dds_file", required=True,
                        help="path of the DDS JSON file to load")
    parser.add_argument("-o", "--odm", dest="odm_file", default="crf.xml",
                        help="path of the ODM XML file to create (default: crf.xml)")
    parser.add_argument("--odm-version", dest="odm_version", required=True,
                        choices=list(ODM_VERSIONS),
                        help="ODM version to generate")
    parser.add_argument("-v", "--validate", dest="is_validate", default=False,
                        const=True, nargs="?",
                        help="validate with odmlib and against the ODM XSD")
    parser.add_argument("--xsd", help="validate against this XSD instead of the bundled one")
    parser.add_argument("--html", nargs="?", const=".", default=None, dest="html_dir",
                        help="also render the blank CRF and the aCRF as HTML into this "
                             "directory (needs saxonche and a stylesheet)")
    parser.add_argument("--stylesheet", help="XSLT stylesheet to use with --html")
    parser.add_argument("--include-hidden", dest="include_hidden", default=False,
                        const=True, nargs="?",
                        help="emit items flagged crfDisplayHidden")
    parser.add_argument("--forms", help="comma-separated Form OIDs to emit (default: all)")
    parser.add_argument("--no-prune-codelists", dest="prune_codelists", action="store_false",
                        help="keep CodeLists that no CRF item references")
    parser.add_argument("-l", "--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="logging level (default: INFO)")
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = set_cmd_line_args()

    try:
        generator = CrfGenerator(
            dds_file=args.dds_file, odm_file=args.odm_file,
            odm_version=args.odm_version, log_level=args.log_level,
            include_hidden=bool(args.include_hidden),
            forms=[f.strip() for f in args.forms.split(",")] if args.forms else None,
            prune_codelists=args.prune_codelists,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        odm = generator.create()
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    xml = generator.write(odm)
    print(f"✅ ODM {args.odm_version} written to {args.odm_file}")
    print(generator.summary())

    exit_code = 0
    if args.is_validate:
        errors = validate_odm(odm, generator.target, xml, args.xsd)
        for error in errors[:20]:
            print(f"  ✗ {error}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")
        if errors:
            print(f"❌ validation FAILED — {len(errors)} error(s)")
            exit_code = 1
        else:
            print("✅ odmlib and XSD validation passed")

    if args.html_dir:
        from generators.crf.render import render_html

        try:
            written = render_html(args.odm_file, args.html_dir, args.odm_version,
                                  args.stylesheet)
            for path in written:
                print(f"✅ HTML written to {path}")
        except (RuntimeError, FileNotFoundError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
