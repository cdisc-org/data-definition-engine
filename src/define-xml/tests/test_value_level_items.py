"""
Value-level items: safe OIDs, duplicate merging, where-clause de-duplication and the
dataset specialization coding.

The CRF carries Define item OIDs as space-separated DATASET.VARIABLE=OID pairs, so a
value-level OID must not contain whitespace or '=', and two items must never share one.
"""

from create_define_json import SDTM_DSS_SYSTEM, USDMDefineJSONProcessor


def _vlm_item(oid, where, dss=None):
    item = {"OID": oid, "name": oid.split(".")[2], "applicableWhen": list(where)}
    if dss:
        item["coding"] = [{"code": dss, "codeSystem": SDTM_DSS_SYSTEM}]
    return item


class TestValueLevelOid:
    def test_safe_values_are_unchanged(self):
        assert USDMDefineJSONProcessor._value_level_oid("VS", "VSORRES", "SYSBP") == "IT.VS.VSORRES.SYSBP"
        assert USDMDefineJSONProcessor._value_level_oid("LB", "LBORRES", "PT-INR") == "IT.LB.LBORRES.PT-INR"

    def test_whitespace_and_equals_become_dashes(self):
        assert USDMDefineJSONProcessor._value_level_oid("DS", "DSDECOD", "PROTOCOL MILESTONE") == \
               "IT.DS.DSDECOD.PROTOCOL-MILESTONE"
        assert USDMDefineJSONProcessor._value_level_oid("XX", "XXORRES", " A = B ") == "IT.XX.XXORRES.A-B"

    def test_no_value_gives_the_variable_oid(self):
        assert USDMDefineJSONProcessor._value_level_oid("TS", "TSVAL", None) == "IT.TS.TSVAL"


class TestAddVlmItem:
    def test_same_oid_and_where_clause_is_one_item_with_merged_codings(self, processor):
        processor._add_vlm_item("DS.DSDECOD", _vlm_item("IT.DS.DSDECOD.PROTOCOL-MILESTONE", ["WC.DS.1"], "CONSENT"))
        processor._add_vlm_item("DS.DSDECOD", _vlm_item("IT.DS.DSDECOD.PROTOCOL-MILESTONE", ["WC.DS.1"], "RANDOM"))
        processor._add_vlm_item("DS.DSDECOD", _vlm_item("IT.DS.DSDECOD.PROTOCOL-MILESTONE", ["WC.DS.1"], "CONSENT"))
        items = processor.vlm_items_by_variable["DS.DSDECOD"]
        assert len(items) == 1
        assert [c["code"] for c in items[0]["coding"]] == ["CONSENT", "RANDOM"]

    def test_same_oid_with_a_different_where_clause_gets_a_suffix(self, processor):
        processor._add_vlm_item("LB.LBORRES", _vlm_item("IT.LB.LBORRES.GLUC", ["WC.LB.1"]))
        processor._add_vlm_item("LB.LBORRES", _vlm_item("IT.LB.LBORRES.GLUC", ["WC.LB.2"]))
        processor._add_vlm_item("LB.LBORRES", _vlm_item("IT.LB.LBORRES.GLUC", ["WC.LB.3"]))
        assert [i["OID"] for i in processor.vlm_items_by_variable["LB.LBORRES"]] == \
               ["IT.LB.LBORRES.GLUC", "IT.LB.LBORRES.GLUC-2", "IT.LB.LBORRES.GLUC-3"]


class TestWhereClauseDeduplication:
    def test_the_same_where_clause_is_written_once(self, processor):
        first = processor._create_where_clause_for_variable("DS", "DSDECOD", ["COND.DS.DSCAT.1"])
        second = processor._create_where_clause_for_variable("DS", "DSDECOD", ["COND.DS.DSCAT.1"])
        assert first == second
        assert [wc["OID"] for wc in processor.where_clauses] == [first]

    def test_another_variable_with_the_same_conditions_is_its_own_where_clause(self, processor):
        processor._create_where_clause_for_variable("VS", "VSORRES", ["COND.VS.VSTESTCD.1"])
        processor._create_where_clause_for_variable("VS", "VSORRESU", ["COND.VS.VSTESTCD.1"])
        assert len(processor.where_clauses) == 2
