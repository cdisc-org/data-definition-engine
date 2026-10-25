"""Tests for the SDTM links: annotation parsing, CDASHIG cross-check, Define links, mapping codes.

No network: the Define side is a small hand-built DDS whose VS value list carries the
specialization ranges as IN lists, the shape the Define loader writes for NCT01797120.
"""
from __future__ import annotations

import copy

import pytest

from loaders.crf.builders import sdtm_links as L
from loaders.crf.builders.codelists import CodeListBuilder
from loaders.crf.builders.forms import FormBuilder
from loaders.crf.builders.items import ItemBuilder
from loaders.crf.sources.cdash_ct import CdashCtSource
from loaders.crf.sources.cdashig import CdashigSource

DSS = "https://library.cdisc.org/api/mdr/specializations/sdtm/datasetspecializations"


def _condition(oid, item, comparator, values):
    return {"OID": oid, "rangeChecks": [{"item": item, "comparator": comparator,
                                         "checkValues": values, "softHard": "Soft"}]}


@pytest.fixture
def define_dds() -> dict:
    """VS with value lists for VSORRES (SYSBP by specialization, DIABP by where clause only),
    DS with a DSDECOD value list on DSCAT, and paired test code / name codelists."""
    return {
        "OID": "MDV.T", "studyOID": "ODM.T",
        "itemGroups": [
            {"OID": "IG.VS", "name": "VS", "domain": "VS",
             "items": [{"OID": f"IT.VS.{v}", "name": v} for v in
                       ("VSORRES", "VSORRESU", "VSTEST", "VSDTC", "VSPOS", "VSLOC")]
                      + [{"OID": "IT.VS.VSTESTCD", "name": "VSTESTCD", "codeList": "CL.VSTESTCD"}],
             "slices": [{"OID": "VL.VS.VSORRES", "type": "ValueList", "items": [
                 {"OID": "IT.VS.VSORRES.SYSBP", "name": "VSORRES", "applicableWhen": ["WC.1"],
                  "coding": [{"code": "SYSBP", "codeSystem": DSS}]},
                 {"OID": "IT.VS.VSORRES.DIABP", "name": "VSORRES", "applicableWhen": ["WC.2"]},
             ]}]},
            {"OID": "IG.DS", "name": "DS", "domain": "DS",
             "items": [{"OID": "IT.DS.DSDECOD", "name": "DSDECOD"},
                       {"OID": "IT.DS.DSCAT", "name": "DSCAT"}],
             "slices": [{"OID": "VL.DS.DSDECOD", "type": "ValueList", "items": [
                 {"OID": "IT.DS.DSDECOD.PROTOCOL-MILESTONE", "name": "DSDECOD",
                  "applicableWhen": ["WC.3"]}]}]},
        ],
        "conditions": [
            _condition("C.1", "IT.VS.VSTESTCD", "EQ", ["SYSBP"]),
            _condition("C.2", "IT.VS.VSPOS", "IN", ["PRONE", "SEMI-RECUMBENT", "SITTING"]),
            _condition("C.3", "IT.VS.VSTESTCD", "EQ", ["DIABP"]),
            _condition("C.4", "IT.DS.DSCAT", "EQ", ["PROTOCOL MILESTONE"]),
        ],
        "whereClauses": [{"OID": "WC.1", "conditions": ["C.1", "C.2"]},
                         {"OID": "WC.2", "conditions": ["C.3", "C.2"]},
                         {"OID": "WC.3", "conditions": ["C.4"]}],
        "codeLists": [{"OID": "CL.VSTESTCD", "codeListItems": [
            {"codedValue": "SYSBP", "decode": "Systolic Blood Pressure"},
            {"codedValue": "DIABP", "decode": "Diastolic Blood Pressure"}]}],
    }


@pytest.fixture
def define(define_dds) -> L.DefineIndex:
    return L.DefineIndex(define_dds)


class TestParseAnnotation:
    @pytest.mark.parametrize("text, expected", [
        ("AETERM", [("AETERM", None, ())]),
        ("VSORRES when VSTESTCD = SYSBP", [("VSORRES", None, (("VSTESTCD", "EQ", ("SYSBP",)),))]),
        ("VSORRESU = mmHg when VSTESTCD = SYSBP",
         [("VSORRESU", "mmHg", (("VSTESTCD", "EQ", ("SYSBP",)),))]),
        ("CMCAT = ANTI-CANCER THERAPY", [("CMCAT", "ANTI-CANCER THERAPY", ())]),
        ("CMDOSE;CMDOSTXT", [("CMDOSE", None, ()), ("CMDOSTXT", None, ())]),
        ("QSORRES where QSTESTCD = EQ5D0201", [("QSORRES", None, (("QSTESTCD", "EQ", ("EQ5D0201",)),))]),
        ("LBORRES when LBTESTCD IN (ALT, AST)",
         [("LBORRES", None, (("LBTESTCD", "IN", ("ALT", "AST")),))]),
    ])
    def test_targets(self, text, expected):
        parsed = L.parse_annotation(text)
        got = [(t.variable, t.value, tuple((c.variable, c.comparator, c.values) for c in t.conditions))
               for t in parsed.targets]
        assert got == expected
        assert not parsed.unparsed

    def test_not_submitted_with_and_without_targets(self):
        assert L.parse_annotation("[NOT SUBMITTED]") == L.Annotation(True, (), ())
        parsed = L.parse_annotation("[NOT SUBMITTED];MHSTRF;MHSTRTPT;MHSTTPT")
        assert parsed.not_submitted and [t.variable for t in parsed.targets] == ["MHSTRF", "MHSTRTPT", "MHSTTPT"]

    def test_supp(self):
        target = L.parse_annotation("RACEOTH in SUPPDM").targets[0]
        assert (target.dataset, target.variable, target.qnam) == ("SUPPDM", "QVAL", "RACEOTH")

    def test_unparsed_text_never_raises(self):
        for text in (None, "", ";;", "see protocol", "X when", "= =", "VSORRES when VSTESTCD"):
            L.parse_annotation(text)
        assert L.parse_annotation("see protocol").unparsed == ("see protocol",)


class TestMappingType:
    def test_order_of_the_rules(self):
        parse = L.parse_annotation
        assert L.mapping_type("AEYN", parse("[NOT SUBMITTED]"), [], None) == L.NOT_SUBMITTED
        assert L.mapping_type("MHPRIOR", parse("[NOT SUBMITTED];MHSTRF;MHSTRTPT"), [], None) == L.RELATIVE_TIMING
        assert L.mapping_type("AEONGO", parse("AEENRF;AEENRTPT"), ["AEENRTPT"], None) == L.RELATIVE_TIMING
        assert L.mapping_type("AESTDAT", parse("AESTDTC"), ["AESTDTC"], None) == L.CONCATENATED
        assert L.mapping_type("CMDOSE", parse("CMDOSE;CMDOSTXT"), ["CMDOSE"],
                              "If numeric, map to CMDOSE; if non-numeric, map to CMDOSTXT.") == L.SPLIT
        assert L.mapping_type("AETERM", parse("AETERM"), ["AETERM"], None) == L.DIRECT
        assert L.mapping_type("XXFIELD", parse("YYVAR"), [], None) is None

    def test_library_targets(self):
        field = {"_links": {"sdtmigDatasetMappingTargets": [
            {"href": "/mdr/sdtmig/3-4/datasets/AE/variables/AEENRTPT"},
            {"href": "/mdr/sdtmig/3-4/datasets/AE/variables/AEENRF"}]}}
        assert L.library_targets(field) == ["AEENRTPT", "AEENRF"]
        assert L.library_targets({}) == [] and L.library_targets(None) == []


class TestAdmitsAndLinks:
    def test_admits(self):
        assert L.admits("EQ", ("SYSBP",), "SYSBP") and not L.admits("EQ", ("SYSBP",), "DIABP")
        assert L.admits("IN", ("PRONE", "SITTING"), "SITTING") and not L.admits("IN", ("PRONE",), "SUPINE")
        assert L.admits("NE", ("HGB",), "ALT") and not L.admits("NE", ("HGB",), "HGB")

    def test_specialization_id_decides(self, define):
        link = define.link("VS", "VSORRES", (L.Condition("VSTESTCD", "EQ", ("SYSBP",)),), {}, "SYSBP")
        assert (link.item, link.basis) == ("IT.VS.VSORRES.SYSBP", "dss")

    def test_where_clause_with_in_lists_admits_the_annotation(self, define):
        # DIABP has no specialization coding; its where clause adds VSPOS IN (...)
        conditions = (L.Condition("VSTESTCD", "EQ", ("DIABP",)),)
        link = define.link("VS", "VSORRES", conditions, {"VSPOS": "SITTING"}, None)
        assert (link.item, link.basis) == ("IT.VS.VSORRES.DIABP", "whereClause")

    def test_a_concept_value_the_where_clause_does_not_admit_rejects(self, define):
        conditions = (L.Condition("VSTESTCD", "EQ", ("DIABP",)),)
        link = define.link("VS", "VSORRES", conditions, {"VSPOS": "SUPINE"}, None)
        assert link.item is None and link.basis == "no value-level item matches"

    def test_no_conditions_and_no_value_level_match_links_the_variable(self, define):
        link = define.link("DS", "DSDECOD", (), {"DSCAT": "DISPOSITION EVENT"}, "ADVEVENT")
        assert (link.item, link.basis) == ("IT.DS.DSDECOD", "variable")
        link = define.link("DS", "DSDECOD", (), {"DSCAT": "PROTOCOL MILESTONE"}, "CONSENT")
        assert link.item == "IT.DS.DSDECOD.PROTOCOL-MILESTONE"

    def test_variables_without_a_value_list_and_missing_targets(self, define):
        assert define.link("VS", "VSDTC").item == "IT.VS.VSDTC"
        assert define.link("VS", "VSXX").basis == "the Define has no VS.VSXX"
        assert define.link("SUPPDM", "QVAL").basis == "the Define has no SUPPDM dataset"

    def test_decode_and_pairs(self, define):
        assert define.decode("VS", "VSTESTCD", "SYSBP") == "Systolic Blood Pressure"
        assert L.paired_name_variable("VSTESTCD") == "VSTEST"
        assert L.paired_name_variable("TSPARMCD") == "TSPARM"
        assert L.paired_name_variable("VSORRES") is None
        assert L.oid_pairs([{"dataset": "VS", "variable": "VSORRES", "item": "IT.VS.VSORRES.SYSBP"},
                            {"dataset": "VS", "variable": "VSXX", "item": None}]) == \
               "VS.VSORRES=IT.VS.VSORRES.SYSBP"


# --- the builders -------------------------------------------------------------------

@pytest.fixture
def ae_fields() -> dict:
    """CDASHIG AE fields with the structured mapping targets the Library publishes."""
    def field(name, targets, instructions=""):
        return {"name": name, "mappingInstructions": instructions, "_links": {
            "sdtmigDatasetMappingTargets": [{"href": f"/mdr/sdtmig/3-4/datasets/AE/variables/{t}"}
                                            for t in targets]}}
    return {"name": "AE", "fields": [
        field("AETERM", ["AETERM"], "Maps directly to the SDTMIG variable listed in the SDTMIG Target column."),
        field("AESTDAT", ["AESTDTC"], "This does not map directly to an SDTMIG variable. For the SDTM "
                                      "submission dataset, concatenate all collected CDASH START DATE"),
        field("AEONGO", ["AEENRTPT", "AEENRF"], "May be used to populate a value into an SDTMIG relative "
                                               "timing variable such as AEENRF or AEENRTPT."),
    ]}


@pytest.fixture
def builder(mock_client, cdashig_fields, cdash_codelist, ae_fields, define_dds):
    dds = copy.deepcopy(define_dds)
    dds["itemGroups"].append({"OID": "IG.AE", "name": "AE", "domain": "AE", "items": [
        {"OID": f"IT.AE.{v}", "name": v} for v in ("AETERM", "AESTDTC", "AEENRF", "AEENRTPT", "AEENTPT")]})

    def get_api_json(path, *args, **kwargs):
        if "/domains/VS" in path:
            return cdashig_fields
        if "/domains/AE" in path:
            return ae_fields
        if "/codelists/C66770" in path:
            return cdash_codelist
        return {}
    mock_client.get_api_json.side_effect = get_api_json
    codelists = CodeListBuilder(CdashCtSource(mock_client, "2026-03-27"), "2026-03-27")
    return ItemBuilder(CdashigSource(mock_client, "2.3"), codelists, set(), L.DefineIndex(dds))


class TestItemBuilderLinks:
    def test_value_level_link_mapping_and_concept_variables_left_out(self, builder, spec_source):
        group = spec_source.groups()["SYSBP_DENORMALIZED"]
        built = {i["OID"]: i for i in builder.build_group_items(group)}
        target = built["IT.CRF.SYSBP_VSORRES"]["crfSdtmTarget"]
        assert target["links"] == [{"dataset": "VS", "variable": "VSORRES", "item": "IT.VS.VSORRES.SYSBP"}]
        assert target["mapping"] == L.DIRECT
        assert "_review" not in target
        # VSTESTCD/VSTEST are in variables but belong to the concept, not the item links
        assert {link["variable"] for link in target["links"]} == {"VSORRES"}

    def test_cdash_name_is_corrected_to_the_library_target(self, builder, spec_source):
        group = spec_source.groups()["AE_DENORMALIZED"]
        built = {i["OID"]: i for i in builder.build_group_items(group)}
        target = built["IT.CRF.AESTDAT"]["crfSdtmTarget"]
        assert target["annotation"] == "AESTDTC" and target["variables"] == ["AESTDTC"]
        assert target["links"][0]["item"] == "IT.AE.AESTDTC"
        assert target["mapping"] == L.CONCATENATED
        assert builder.corrections == ["IT.CRF.AESTDAT: AESTDAT -> AESTDTC (CDASHIG sdtmigDatasetMappingTargets)"]

    def test_relative_timing(self, builder, spec_source):
        group = spec_source.groups()["AE_DENORMALIZED"]
        built = {i["OID"]: i for i in builder.build_group_items(group)}
        target = built["IT.CRF.AEONGO"]["crfSdtmTarget"]
        assert target["mapping"] == L.RELATIVE_TIMING
        assert {link["item"] for link in target["links"]} == {"IT.AE.AEENRTPT", "IT.AE.AEENRF", "IT.AE.AEENTPT"}

    def test_unlinked_targets_go_to_mapping_review(self, builder, spec_source):
        group = spec_source.groups()["AE_DENORMALIZED"]
        builder.build_group_items(group)
        reviewed = {(e["item"], e["target"]) for e in builder.mapping_review}
        assert reviewed and all(e["reason"] for e in builder.mapping_review)
        assert all(not target.endswith(("AESTDTC", "AETERM")) for _, target in reviewed)

    def test_a_shared_item_with_a_different_prefilled_value_is_split(self, builder):
        from loaders.crf.sources.crf_specializations import CrfGroup, CrfItem

        def group(gid, dss, term):
            return CrfGroup(gid, vlm_group_id=dss, domain="DS", items=[
                CrfItem("DSCAT", "DSCAT", display_hidden="Y", prepopulated_term=term,
                        sdtm_annotation="DSCAT", sdtm_target_variable=["DSCAT"]),
                CrfItem("DSDECOD", "DSDECOD", sdtm_annotation="DSDECOD",
                        sdtm_target_variable=["DSDECOD"])])
        first = builder.build_group_items(group("ADVEVENT_CONT", "ADVEVENT", "DISPOSITION EVENT"))
        second = builder.build_group_items(group("CONSENT_CONT", "CONSENT", "PROTOCOL MILESTONE"))
        assert first[0]["OID"] == "IT.CRF.DSCAT" and second[0]["OID"] == "IT.CRF.CONSENT_CONT.DSCAT"
        assert first[1]["crfSdtmTarget"]["links"][0]["item"] == "IT.DS.DSDECOD"
        assert second[1]["OID"] == "IT.CRF.CONSENT_CONT.DSDECOD"
        assert second[1]["crfSdtmTarget"]["links"][0]["item"] == "IT.DS.DSDECOD.PROTOCOL-MILESTONE"


class TestConceptFixedValues:
    def test_test_code_and_name_become_concept_aliases(self, builder, spec_source, usdm_soa):
        group = spec_source.groups()["SYSBP_DENORMALIZED"]
        forms = FormBuilder(builder)
        concept = forms._build_concept({"group": group}, {})
        aliases = {a["context"]: a["name"] for a in concept["aliases"]}
        assert aliases["SDTM"] == "VSTESTCD = SYSBP; VSTEST = Systolic Blood Pressure"
        assert aliases["SDTMItemOIDs"] == "VS.VSTESTCD=IT.VS.VSTESTCD VS.VSTEST=IT.VS.VSTEST"

    def test_hidden_prefilled_items_are_stated_on_the_concept(self, builder):
        from loaders.crf.sources.crf_specializations import CrfGroup, CrfItem
        group = CrfGroup("CONSENT_CONT", vlm_group_id="CONSENT", domain="DS", items=[
            CrfItem("DSCAT", "DSCAT", display_hidden="Y", prepopulated_term="PROTOCOL MILESTONE",
                    sdtm_annotation="DSCAT", sdtm_target_variable=["DSCAT"]),
            CrfItem("DSSCAT", "DSSCAT", display_hidden="Y", sdtm_annotation="DSSCAT",
                    sdtm_target_variable=["DSSCAT"]),
            CrfItem("DSDECOD", "DSDECOD", display_hidden="Y", prepopulated_term="INFORMED CONSENT OBTAINED",
                    sdtm_annotation="DSDECOD", sdtm_target_variable=["DSDECOD"])])
        concept = FormBuilder(builder)._build_concept({"group": group}, {})
        aliases = {a["context"]: a["name"] for a in concept["aliases"]}
        assert aliases["SDTM"] == "DSCAT = PROTOCOL MILESTONE; DSDECOD = INFORMED CONSENT OBTAINED"
        assert aliases["SDTMItemOIDs"] == \
               "DS.DSCAT=IT.DS.DSCAT DS.DSDECOD=IT.DS.DSDECOD.PROTOCOL-MILESTONE"
        # DSSCAT is hidden but not prefilled: no value to state, so a person decides
        assert any(e["item"] == "IG.CON.CONSENT_CONT" and "DSSCAT" in e["reason"]
                   for e in builder.mapping_review)

    def test_a_hidden_prefilled_value_is_stated_only_when_it_maps_directly(self, builder):
        from loaders.crf.sources.crf_specializations import CrfGroup, CrfItem
        # MHONGO prefilled Y feeds the relative timing variables: Y is not their SDTM value
        group = CrfGroup("MEDHIST", domain="AE", items=[
            CrfItem("AEONGO", "AEONGO", display_hidden="Y", prepopulated_term="Y",
                    sdtm_annotation="AEENRF;AEENRTPT;AEENTPT",
                    sdtm_target_variable=["AEENRF", "AEENRTPT", "AEENTPT"])])
        concept = FormBuilder(builder)._build_concept({"group": group}, {})
        assert "aliases" not in concept
        assert any("does not map directly" in e["reason"] for e in builder.mapping_review)
