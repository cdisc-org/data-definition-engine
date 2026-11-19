"""The methods library format: schema, load-time checks, layering, and the seed (methods plan M1)."""
from __future__ import annotations

import copy
import json

import pytest

from loaders.methods.library import SCHEMA_FILE, SEED_FILE, Library, LibraryError
from loaders.methods.tests.conftest import method


def _refused(write, *contents, match: str):
    with pytest.raises(LibraryError, match=match):
        Library.load(write(*contents))


# =============================================================================
# Load-time checks
# =============================================================================

class TestRefusals:
    def test_valid_library_loads(self, write, library):
        lib = Library.load(write(library))
        assert sorted(lib.methods) == ["MT.BMI", "MT.SEQ", "MT.TSSEQ"]
        assert [a.label for a in lib.assignments] == ["--SEQ", "TSSEQ", "VSORRES [VS] where VSTESTCD=BMI"]

    def test_assignment_to_an_undefined_method(self, write, library):
        library["assignments"].append({"name": "--DY", "method": "MT.DAYCALC"})
        _refused(write, library, match="names MT.DAYCALC, which no library file defines")

    @pytest.mark.parametrize("mtype", ["Transformation", "Analysis", "Display", "Preload"])
    def test_type_outside_rule_209(self, write, library, mtype):
        library["methods"][0]["type"] = mtype
        _refused(write, library, match="methods/0/type")

    @pytest.mark.parametrize("description", ["", {"translations": []}])
    def test_empty_description(self, write, library, description):
        library["methods"][0]["description"] = description
        _refused(write, library, match="methods/0/description")

    def test_duplicate_oid_in_one_file(self, write, library):
        library["methods"].append(method("MT.SEQ"))
        _refused(write, library, match="MT.SEQ is defined twice")

    def test_duplicate_assignment_in_one_file(self, write, library):
        library["assignments"].append({"name": "--SEQ", "method": "MT.TSSEQ"})
        _refused(write, library, match="two assignments for --SEQ")

    def test_duplicate_signature_name(self, write, library):
        library["methods"][0]["signature"]["returnValues"][0]["name"] = "IN"
        _refused(write, library, match="signature name IN is used twice")

    def test_duplicate_order_number(self, write, library):
        library["methods"][0]["signature"]["parameters"].append(
            {"name": "IN2", "dataType": "text", "orderNumber": 1})
        _refused(write, library, match="parameters orderNumber 1 is used twice")

    def test_data_type_outside_the_dds_enum(self, write, library):
        library["methods"][0]["signature"]["parameters"][0]["dataType"] = "decimal"
        _refused(write, library, match="dataType")

    @pytest.mark.parametrize("expression", [
        {"context": "SAS", "expression": "x=1;", "externalCodeLib": {"library": "sdtm.oak"}},
        {"context": "SAS"},
    ])
    def test_expression_needs_exactly_one_body(self, write, library, expression):
        library["methods"][0]["expressions"] = [expression]
        _refused(write, library, match="methods/0/expressions/0")

    def test_expression_needs_a_context(self, write, library):
        library["methods"][0]["expressions"] = [{"expression": "x=1;"}]
        _refused(write, library, match="'context' is a required property")

    def test_star_needs_domains(self, write, library):
        library["assignments"].append({"name": "*", "method": "MT.SEQ"})
        _refused(write, library, match="'domains' is a required property")

    def test_where_value_must_be_a_string(self, write, library):
        library["assignments"][2]["where"] = {"VSTESTCD": ["BMI", "HEIGHT"]}
        _refused(write, library, match="assignments/2/where")

    def test_unsupported_major_version(self, write, library):
        library["schemaVersion"] = "2.0"
        _refused(write, library, match="schemaVersion 2.0 is not supported")

    def test_unreadable_file(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        with pytest.raises(LibraryError, match="bad.json"):
            Library.load([str(bad)])

    def test_both_expression_bodies_are_accepted_one_at_a_time(self, write, library):
        library["methods"][0]["expressions"] = [
            {"context": "SAS 9.4", "expression": "SEQ + 1"},
            {"context": "R (sdtm.oak 0.2.0)",
             "externalCodeLib": {"library": "sdtm.oak", "method": "derive_seq", "version": "0.2.0",
                                 "href": "https://pharmaverse.github.io/sdtm.oak/reference/derive_seq.html"}},
        ]
        assert len(Library.load(write(library)).methods["MT.SEQ"]["expressions"]) == 2


# =============================================================================
# Layering
# =============================================================================

class TestLayering:
    def test_a_later_file_replaces_a_method_as_a_whole(self, write, library):
        study = {"schemaVersion": "1.0", "methods": [
            {"OID": "MT.SEQ", "name": "Study SEQ", "type": "Computation", "description": "Study text."}]}
        lib = Library.load(write(library, study))
        assert lib.methods["MT.SEQ"]["description"] == "Study text."
        assert "signature" not in lib.methods["MT.SEQ"]
        assert lib.method_files["MT.SEQ"] == "methods-1.json"
        assert lib.method_files["MT.TSSEQ"] == "methods-0.json"

    def test_a_later_file_may_assign_a_method_an_earlier_file_defines(self, write, library):
        study = {"schemaVersion": "1.0", "assignments": [{"name": "DISEQ", "method": "MT.TSSEQ"}]}
        lib = Library.load(write(library, study))
        assert lib.assignments[-1].label == "DISEQ" and lib.assignments[-1].order == 1

    def test_an_earlier_file_may_assign_a_method_a_later_file_defines(self, write, library):
        library["assignments"].append({"name": "--ENTPT", "method": "MT.ENTPT"})
        study = {"schemaVersion": "1.0", "methods": [method("MT.ENTPT")]}
        assert "MT.ENTPT" in Library.load(write(library, study)).methods

    def test_the_same_assignment_may_repeat_across_files(self, write, library):
        study = {"schemaVersion": "1.0", "assignments": [{"name": "--SEQ", "method": "MT.TSSEQ"}]}
        lib = Library.load(write(library, study))
        assert [a.method for a in lib.assignments if a.name == "--SEQ"] == ["MT.SEQ", "MT.TSSEQ"]


class TestDdsMethod:
    def test_basis_never_reaches_the_dds(self, write, library):
        dds = Library.load(write(library)).dds_method("MT.SEQ")
        assert "basis" not in dds
        assert dds["signature"]["parameters"][0]["name"] == "IN"

    def test_a_method_without_a_signature_gets_an_empty_one(self, write, library):
        del library["methods"][0]["signature"]
        dds = Library.load(write(library)).dds_method("MT.SEQ")
        assert dds["signature"] == {"parameters": [], "returnValues": []}

    def test_signature_entries_and_expressions_get_stable_oids(self, write, library):
        # Parameter, ReturnValue and FormalExpression are IdentifiableElements in the DDS, so the
        # generated DDS JSON Schema requires an OID; ODM v2.0 has none. Decided 2026-11-19.
        library["methods"][0]["expressions"] = [
            {"context": "SAS 9.4", "expression": "SEQ + 1"},
            {"context": "R", "externalCodeLib": {"library": "sdtm.oak", "method": "derive_seq"}}]
        lib = Library.load(write(library))
        dds = lib.dds_method("MT.SEQ")
        assert [p["OID"] for p in dds["signature"]["parameters"]] == ["PA.SEQ.IN"]
        assert [r["OID"] for r in dds["signature"]["returnValues"]] == ["RV.SEQ.OUT"]
        assert [e["OID"] for e in dds["expressions"]] == ["FE.SEQ.1", "FE.SEQ.2"]
        assert lib.dds_method("MT.SEQ") == dds
        assert "OID" not in lib.methods["MT.SEQ"]["signature"]["parameters"][0]

    def test_an_oid_the_library_gives_is_kept(self, write, library):
        library["methods"][0]["signature"]["parameters"][0]["OID"] = "PA.CUSTOM"
        dds = Library.load(write(library)).dds_method("MT.SEQ")
        assert dds["signature"]["parameters"][0]["OID"] == "PA.CUSTOM"
        assert dds["signature"]["returnValues"][0]["OID"] == "RV.SEQ.OUT"

    def test_seed_oids_are_unique_across_the_library(self):
        seed = Library.load([SEED_FILE])
        oids = [entry["OID"] for oid in seed.methods
                for key in ("parameters", "returnValues")
                for entry in seed.dds_method(oid)["signature"][key]]
        assert len(oids) == len(set(oids)) and "PA.DAYCALC.DTC" in oids and "RV.DAYCALC.DY" in oids

    def test_the_dds_copy_is_independent_of_the_library(self, write, library):
        lib = Library.load(write(library))
        lib.dds_method("MT.SEQ")["signature"]["parameters"].clear()
        assert lib.methods["MT.SEQ"]["signature"]["parameters"]


# =============================================================================
# The frozen PR-DDS-3 slot names
# =============================================================================

#: The DDS slot names PR-DDS-3 proposes (DDS_FOR_METHODS.md changes 1-5), plus the existing DDS Method,
#: Parameter, ReturnValue, FormalExpression and DocumentReference slots the library uses. The methods
#: loader writes these into the DDS before upstream merges them, so a rename here must be a rename there.
PR_DDS_3_SLOTS = {
    "method": {"OID", "name", "type", "description", "signature", "expressions", "documents", "basis"},
    "signature": {"parameters", "returnValues"},
    "parameter": {"OID", "name", "dataType", "description", "orderNumber"},
    "returnValue": {"OID", "name", "dataType", "description", "orderNumber"},
    "expression": {"OID", "context", "expression", "externalCodeLib"},
    "externalCodeLib": {"library", "method", "version", "ref", "href"},
    "document": {"leafID", "pages", "title"},
}

DDS_DATATYPE = {"text", "integer", "float", "date", "time", "datetime", "boolean", "double", "hex",
                "base64", "hexBinary", "durationDatetime"}
ISO8601_TYPES = {"partialDate", "partialTime", "partialDatetime", "intervalDatetime",
                 "incompleteDatetime", "incompleteDate", "incompleteTime"}


class TestFrozenSlotNames:
    @pytest.fixture(scope="class")
    def defs(self):
        return json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))["$defs"]

    @pytest.mark.parametrize("definition", sorted(PR_DDS_3_SLOTS))
    def test_slot_names_match_pr_dds_3(self, defs, definition):
        assert set(defs[definition]["properties"]) == PR_DDS_3_SLOTS[definition]

    def test_data_type_is_the_dds_enum_plus_the_iso_8601_types(self, defs):
        assert set(defs["dataType"]["enum"]) == DDS_DATATYPE | ISO8601_TYPES


# =============================================================================
# The shared seed
# =============================================================================

class TestSeed:
    @pytest.fixture(scope="class")
    def seed(self):
        return Library.load([SEED_FILE])

    def test_seed_loads_with_22_methods_and_22_assignments(self, seed):
        assert len(seed.methods) == 22
        assert len(seed.assignments) == 22

    def test_every_method_states_its_basis_and_has_a_signature(self, seed):
        for oid, entry in seed.methods.items():
            assert entry.get("basis"), oid
            assert entry["signature"]["parameters"], oid
            assert entry["signature"]["returnValues"], oid

    def test_every_signature_entry_is_ordered_and_defined(self, seed):
        for oid, entry in seed.methods.items():
            for key in ("parameters", "returnValues"):
                values = entry["signature"][key]
                assert [v["orderNumber"] for v in values] == list(range(1, len(values) + 1)), oid
                assert all(v.get("description") for v in values), oid

    def test_seed_carries_no_expressions_or_documents(self, seed):
        # Out of scope for this phase: the format supports both, the seed ships neither.
        assert not any("expressions" in m or "documents" in m for m in seed.methods.values())

    def test_method_oids_carry_no_domain(self, seed):
        assert all(oid.count(".") == 1 for oid in seed.methods)

    def test_every_method_is_assigned(self, seed):
        assert {a.method for a in seed.assignments} == set(seed.methods)

    def test_draft_entries_are_marked(self, seed):
        drafts = sorted(oid for oid, m in seed.methods.items() if m["basis"].startswith("Draft"))
        assert drafts == ["MT.AGE", "MT.ISO8601", "MT.RFICDTC", "MT.USUBJID"]
