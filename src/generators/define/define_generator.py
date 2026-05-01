import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any
import os.path

from defineutils.validate import DefineSchemaValidator, DefineSchemaValidationError
from odmlib.define_2_1 import model as DEFINE

import odm as ODM
import supporting_docs as SD
import post_processing as PP
import study
import standards
import itemGroups
import items
import conditions
import annotatedCRF
import concepts
import conceptProperties
import whereClauses
import codeLists
import dictionaries
import methods
import comments
import documents
from constants import DEFAULT_LANGUAGE, ACRF_LEAF_ID, DEFAULT_OUTPUT_FILE

ELEMENTS = ["ValueListDef", "WhereClauseDef", "ItemGroupDef", "ItemDef", "CodeList", "MethodDef", "CommentDef", "leaf"]

# Loader classes for each section in the DDS JSON file.
# Ordering is significant — conditions must run before whereClauses (whereClauses reads
# the condition cache), itemGroups populates ItemDef/ValueListDef/WhereClauseDef entries,
# and post-processing depends on ItemDef being fully materialized.
SECTION_ORDER = [
    "standards",
    "annotatedCRF",
    "codeLists",
    "concepts",
    "conceptProperties",
    "dictionaries",
    "documents",
    "comments",
    "conditions",
    "methods",
    "itemGroups",
    "whereClauses",
]

LOADERS = {
    "itemGroups": itemGroups.ItemGroups,
    "conditions": conditions.Conditions,
    "whereClauses": whereClauses.WhereClauses,
    "codeLists": codeLists.CodeLists,
    "methods": methods.Methods,
    "standards": standards.Standards,
    "annotatedCRF": annotatedCRF.AnnotatedCRF,
    "concepts": concepts.Concepts,
    "conceptProperties": conceptProperties.ConceptProperties,
    "dictionaries": dictionaries.Dictionaries,
    "comments": comments.Comments,
    "documents": documents.Documents,
}

"""
define_generator.py - convert a define-360i.json file into a Define-XML v2.1 file.
Example Cmd-line Args:
    example: -t ./fixtures/define-360i.json -d ./fixtures/define-360i.xml
"""

class DefineGenerator:
    """Generate a Define-XML v2.1 file from the DDS JSON file."""

    def __init__(self, dds_file: str, define_file: str, log_level: str = "INFO") -> None:
        """
        Initialize the Define-XML generator.

        :param dds_file: path and filename of the Data Definition Specification (DDS) JSON file
        :param define_file: path and filename for the output Define-XML v2.1 file
        :param log_level: logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.dds_file: str = dds_file
        self.define_file: str = define_file
        logging.basicConfig(
            filename="define_generator.log",
            level=getattr(logging, log_level),
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        self._check_file_existence()
        self.lang: str = DEFAULT_LANGUAGE
        self.acrf: str = ACRF_LEAF_ID
        self.define_objects: dict[str, Any] = {}

    def create(self) -> None:
        """Create the Define-XML v2.1 file from the DDS JSON input file."""
        try:
            with open(self.dds_file, 'r') as f:
                template_objects = json.load(f)
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON in {self.dds_file}: {e.msg} at line {e.lineno}")
            print(f"ERROR: Invalid JSON in {self.dds_file}: {e.msg} at line {e.lineno}", file=sys.stderr)
            sys.exit(1)
        self._init_define_objects()
        self._load_study(template_objects)
        # Explicit dispatch order — no dependency on JSON key order.
        for section in SECTION_ORDER:
            if section not in template_objects:
                continue
            value = template_objects[section]
            if not isinstance(value, list):
                continue
            logging.info(f"processing {section}")
            self._load(section, value)

        self._post_process_elements()
        odm = self._build_doc()
        self._write_define(odm)


    def _post_process_elements(self) -> None:
        """
        Post-processing adds content determined after all elements are created.
        :return: None
        """
        pp = PP.PostProcessing(self.define_objects, self.lang)
        pp.process_define_objects()

    def _init_define_objects(self) -> None:
        """Initialize empty containers for each Define-XML element type."""
        for elem in ELEMENTS:
            self.define_objects[elem] = []
        # Containers populated by non-ELEMENTS loaders. Initializing here prevents
        # KeyErrors when a DDS JSON file omits these sections entirely.
        self.define_objects["AnnotatedCRF"] = []
        self.define_objects["Standards"] = DEFINE.Standards()
        # Internal caches written by one loader and read by another.
        self.define_objects["_conditions"] = []

    def _load(self, section: str, data: list[dict[str, Any]]) -> None:
        """
        Load a section of the DDS JSON using the appropriate loader class.

        :param section: name of the section in the DDS JSON
        :param data: list of dictionaries containing the section fixtures
        """
        loader_class = LOADERS.get(section)
        if not loader_class:
            logging.warning(f"No loader registered for section: {section}")
            return
        loader = loader_class()
        loader.create_define_objects(data, self.define_objects, self.lang, self.acrf)

    def _load_study(self, template: dict[str, Any]) -> None:
        """Load study-level metadata from the DDS JSON."""
        loader = study.Study()
        loader.create_define_objects(template, self.define_objects, self.lang, self.acrf)

    def _build_doc(self) -> Any:
        """
        after processing the content in the template input file organize the odmlib define_objects for use as a Define-XML v2.1
        :return: instantiated odmlib Define-XML v2.1 model
        """
        odm_elem = ODM.ODM()
        odm = odm_elem.create_root()
        odm.Study = self.define_objects["Study"]
        odm.Study.MetaDataVersion = self.define_objects["MetaDataVersion"]
        odm.Study.MetaDataVersion.Standards = self.define_objects["Standards"]
        supp_docs = SD.SupportingDocuments()
        # Prefer an AnnotatedCRF materialized by the annotatedCRF loader; fall back
        # to a synthesized stub when the DDS JSON has no annotatedCRF section.
        acrf_list = self.define_objects.get("AnnotatedCRF") or []
        if acrf_list:
            odm.Study.MetaDataVersion.AnnotatedCRF = acrf_list[0]
        else:
            odm.Study.MetaDataVersion.AnnotatedCRF = supp_docs.create_annotatedcrf(self.acrf)
        # Only add a fallback acrf leaf if the annotatedCRF loader didn't produce one.
        if self._find_leaf(ACRF_LEAF_ID) is None:
            self.define_objects["leaf"].append(
                supp_docs.create_leaf_object(leaf_id=ACRF_LEAF_ID, href="acrf.pdf", title="Annotated CRF")
            )
        for elem in ELEMENTS:
            self._load_elements(odm, elem)
        return odm

    def _find_leaf(self, leaf_id: str) -> Any | None:
        for leaf in self.define_objects["leaf"]:
            if getattr(leaf, "ID", None) == leaf_id:
                return leaf
        return None


    def _load_elements(self, odm: Any, elem_name: str) -> None:
        """
        Add instantiated define_objects to the odmlib MetaDataVersion.

        :param odm: odmlib Define-XML ODM object
        :param elem_name: name of the element type to add to MetaDataVersion
        """
        elem_list = getattr(odm.Study.MetaDataVersion, elem_name)
        for obj in self.define_objects[elem_name]:
            elem_list.append(obj)

    def _write_define(self, odm: Any) -> None:
        """
        Write the odmlib Define-XML to an XML file.

        :param odm: the instantiated odmlib Define-XML ODM object
        """
        odm.write_xml(self.define_file)

    def _check_file_existence(self) -> None:
        """Raise an error if the DDS input file cannot be found."""
        if not os.path.isfile(self.dds_file):
            raise ValueError("The template file specified on the command-line cannot be found.")

def validate_define_file(define_file: str) -> bool:
    """
    Validate the Define-XML file against the schema.

    :param define_file: path to the Define-XML file to validate
    :return: True when the file is valid, False otherwise
    """
    validator = DefineSchemaValidator(Path(define_file))
    try:
        validator.validate_define_file()
    except DefineSchemaValidationError as e:
        logging.error(f"Define-XML schema validation failed: {e}")
        print(f"ERROR: Schema validation failed: {e}", file=sys.stderr)
        return False
    logging.info("Define-XML file is valid.")
    return True


def set_cmd_line_args() -> argparse.Namespace:
    """
    Parse command-line arguments for the Define-XML generator.

    :return: parsed command-line arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--define", help="path and file name of Define-XML v2 file to create", required=False,
                        dest="define_file", default=DEFAULT_OUTPUT_FILE)
    parser.add_argument("-t", "--template", help="path and file name of the template file to load", required=True,
                        dest="dds_file", )
    parser.add_argument("-l", "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level (default: INFO)",
    )
    parser.add_argument("-s", "--validate", help="schema validate the define.xml", default=False, const=True,
                        nargs='?', dest="is_validate")
    args = parser.parse_args()
    return args


def main() -> None:
    """Main entry point that generates Define-XML v2.1 from a DDS JSON file."""
    args = set_cmd_line_args()
    dg = DefineGenerator(dds_file=args.dds_file, define_file=args.define_file, log_level=args.log_level)
    dg.create()
    if args.is_validate:
        if not validate_define_file(args.define_file):
            sys.exit(1)


if __name__ == "__main__":
    main()
