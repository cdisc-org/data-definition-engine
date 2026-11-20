"""The conformance checks: one failing case per rule, and a failure stops the loader before it writes."""
from __future__ import annotations

import copy
import json

import pytest

from loaders.common import dds_io
from loaders.common.patch import PLACEHOLDER
from loaders.methods import conformance
from loaders.methods.methods_loader import MethodsError, MethodsLoader
from tests.conftest import CUSTOM


def problems(dds: dict) -> list[str]:
    return conformance.check(dds, dds_io.define_items(dds))


def one_item(**item) -> dict:
    return {"itemGroups": [{"OID": "IG.LB", "name": "LB", "domain": "LB",
                            "items": [{"OID": "IT.LB.LBSTRESC", "name": "LBSTRESC", **item}]}],
            "methods": [copy.deepcopy(CUSTOM)]}


DERIVED = [{"type": "Derived", "source": "Sponsor"}]


class TestRules:
    def test_a_conforming_dds_has_no_problems(self):
        assert problems(one_item(origin=DERIVED, method="MT.LB.CUSTOM")) == []

    def test_rule_73_derived_item_without_a_method(self):
        assert problems(one_item(origin=DERIVED)) == ["IT.LB.LBSTRESC: Derived item without a method (rule 73)"]
        assert problems(one_item(origin=DERIVED, method=PLACEHOLDER))[0].endswith("(rule 73)")

    def test_rule_74_method_not_in_methods(self):
        found = problems(one_item(origin=[{"type": "Assigned", "source": "Sponsor"}], method="MT.MISSING"))
        assert found == ["IT.LB.LBSTRESC: method MT.MISSING is not in methods (rule 74)"]

    @pytest.mark.parametrize("description", ["", "   ", None, {"translations": []},
                                             {"translations": [{"language": "en", "value": ""}]}])
    def test_rules_56_210_empty_description(self, description):
        assert "empty description (rules 56, 210)" in conformance.method_problems({**CUSTOM, "description": description})

    def test_a_placeholder_description_is_open_not_a_failure(self):
        assert conformance.method_problems({**CUSTOM, "description": PLACEHOLDER}) == []

    def test_a_translated_text_description_conforms(self):
        method = {**CUSTOM, "description": {"translations": [{"language": "en", "value": "Text."}]}}
        assert conformance.method_problems(method) == []

    @pytest.mark.parametrize("type_", ["Transformation", "Analysis", "Display", None])
    def test_rules_208_209_type(self, type_):
        assert conformance.method_problems({**CUSTOM, "type": type_}) == [
            f"type {type_!r} is not Computation or Imputation (rules 208, 209)"]

    def test_rule_221_expression_context(self):
        method = {**CUSTOM, "expressions": [{"expression": "x + 1"}]}
        assert conformance.method_problems(method) == ["expression 1 has no context (rule 221)"]

    def test_odm20_signature_required(self):
        method = {k: v for k, v in CUSTOM.items() if k != "signature"}
        assert conformance.method_problems(method) == ["no signature (ODM v2.0 requires a MethodSignature)"]

    @pytest.mark.parametrize("bodies", [{}, {"expression": "x", "externalCodeLib": {"library": "sdtm.oak"}}])
    def test_odm20_exactly_one_expression_body(self, bodies):
        method = {**CUSTOM, "expressions": [{"context": "R", **bodies}]}
        assert conformance.method_problems(method) == [
            f"expression 1 has {len(bodies)} bodies; ODM v2.0 needs exactly one of expression or externalCodeLib"]

    def test_a_method_oid_appears_once(self):
        dds = one_item(origin=DERIVED, method="MT.LB.CUSTOM")
        dds["methods"].append(copy.deepcopy(CUSTOM))
        assert problems(dds) == ["MT.LB.CUSTOM: defined twice in methods"]


class TestLoaderStops:
    def test_a_nonconforming_input_method_stops_the_loader_before_it_writes(self, tmp_path, dds):
        dds["methods"][0]["type"] = "Analysis"
        dds_in, dds_out = tmp_path / "in.json", tmp_path / "out.json"
        dds_in.write_text(json.dumps(dds), encoding="utf-8")
        loader = MethodsLoader(str(dds_in), str(dds_out))
        with pytest.raises(MethodsError, match=r"MT.LB.CUSTOM: type 'Analysis'.*rules 208, 209"):
            loader.process()
        assert not dds_out.exists()

    def test_an_item_naming_a_missing_method_stops_the_loader(self, tmp_path, dds):
        dds["itemGroups"][0]["items"][1]["method"] = "MT.GONE"
        dds_in = tmp_path / "in.json"
        dds_in.write_text(json.dumps(dds), encoding="utf-8")
        with pytest.raises(MethodsError, match=r"IT.AE.USUBJID: method MT.GONE is not in methods \(rule 74\)"):
            MethodsLoader(str(dds_in), str(tmp_path / "out.json")).process()
