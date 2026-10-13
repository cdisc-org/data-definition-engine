"""
Tests for nested def:SubClass support in itemGroups.ItemGroups.

Define-XML v2.1 represents nested SubClasses as flat siblings under def:Class
with the ParentClass attribute referencing the parent SubClass's Name. These
tests verify that the JSON subClasses tree is flattened correctly and that
nesting is capped at MAX_SUBCLASS_DEPTH levels under Class.
"""
import json
import xml.etree.ElementTree as ET

import pytest
from odmlib.define_2_1 import model as DEFINE


@pytest.fixture
def item_groups():
    import itemGroups
    return itemGroups.ItemGroups()


@pytest.fixture
def fresh_class():
    return DEFINE.Class(Name="FINDINGS")


def _names_and_parents(class_obj):
    return [(sc.Name, getattr(sc, "ParentClass", None)) for sc in class_obj.SubClass]


class TestAppendSubclasses:
    """Unit tests for the recursive flattener."""

    def test_single_subclass_no_parent(self, item_groups, fresh_class):
        item_groups._append_subclasses(
            fresh_class,
            [{"name": "LABORATORY"}],
            parent_name=None,
            depth=1,
        )
        assert _names_and_parents(fresh_class) == [("LABORATORY", None)]

    def test_two_level_nesting_assigns_parent(self, item_groups, fresh_class):
        item_groups._append_subclasses(
            fresh_class,
            [{"name": "LAB", "subClasses": [{"name": "CHEM"}]}],
            parent_name=None,
            depth=1,
        )
        assert _names_and_parents(fresh_class) == [
            ("LAB", None),
            ("CHEM", "LAB"),
        ]

    def test_four_level_chain_fully_emitted(self, item_groups, fresh_class):
        tree = [
            {
                "name": "L1",
                "subClasses": [
                    {
                        "name": "L2",
                        "subClasses": [
                            {
                                "name": "L3",
                                "subClasses": [{"name": "L4"}],
                            }
                        ],
                    }
                ],
            }
        ]
        item_groups._append_subclasses(fresh_class, tree, parent_name=None, depth=1)
        assert _names_and_parents(fresh_class) == [
            ("L1", None),
            ("L2", "L1"),
            ("L3", "L2"),
            ("L4", "L3"),
        ]

    def test_fifth_level_is_dropped(self, item_groups, fresh_class):
        tree = [
            {
                "name": "L1",
                "subClasses": [
                    {
                        "name": "L2",
                        "subClasses": [
                            {
                                "name": "L3",
                                "subClasses": [
                                    {
                                        "name": "L4",
                                        "subClasses": [{"name": "L5_dropped"}],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
        item_groups._append_subclasses(fresh_class, tree, parent_name=None, depth=1)
        emitted = _names_and_parents(fresh_class)
        assert ("L5_dropped", "L4") not in emitted
        assert [name for name, _ in emitted] == ["L1", "L2", "L3", "L4"]

    def test_explicit_parent_overrides_walked_parent(self, item_groups, fresh_class):
        tree = [
            {
                "name": "LAB",
                "subClasses": [
                    {"name": "CHEM", "parentClass": "EXPLICIT_PARENT"},
                ],
            }
        ]
        item_groups._append_subclasses(fresh_class, tree, parent_name=None, depth=1)
        assert _names_and_parents(fresh_class) == [
            ("LAB", None),
            ("CHEM", "EXPLICIT_PARENT"),
        ]

    def test_empty_and_missing_subclasses_are_safe(self, item_groups, fresh_class):
        item_groups._append_subclasses(fresh_class, [], parent_name=None, depth=1)
        assert _names_and_parents(fresh_class) == []
        item_groups._append_subclasses(
            fresh_class,
            [{"name": "ONLY"}, {"name": "NEXT", "subClasses": None}],
            parent_name=None,
            depth=1,
        )
        assert _names_and_parents(fresh_class) == [("ONLY", None), ("NEXT", None)]

    def test_entry_missing_name_is_skipped(self, item_groups, fresh_class):
        item_groups._append_subclasses(
            fresh_class,
            [{"name": "A"}, {"parentClass": "A"}, {"name": "B"}],
            parent_name=None,
            depth=1,
        )
        assert _names_and_parents(fresh_class) == [("A", None), ("B", None)]


class TestGenerateDatasetIntegration:
    """Exercise observationClass handling through _generate_dataset."""

    def _make_define_objects(self):
        return {
            "ItemGroupDef": [],
            "ItemDef": [],
            "ValueListDef": [],
            "WhereClauseDef": [],
            "CodeList": [],
            "MethodDef": [],
            "CommentDef": [],
            "leaf": [],
        }

    def _minimal_dataset(self, observation_class=None):
        dataset = {
            "name": "AE",
            "description": "Adverse Events",
            "structure": "One record per adverse event per subject",
            "items": [
                {
                    "OID": "IT.AE.STUDYID",
                    "name": "STUDYID",
                    "description": "Study Identifier",
                    "role": "Identifier",
                    "dataType": "text",
                    "mandatory": True,
                }
            ],
        }
        if observation_class is not None:
            dataset["observationClass"] = observation_class
        return dataset

    def test_nested_subclasses_emit_flat_siblings(self, item_groups):
        item_groups.lang = "en"
        define_objects = self._make_define_objects()
        dataset = self._minimal_dataset(
            observation_class={
                "name": "Findings",
                "subClasses": [
                    {
                        "name": "LAB",
                        "subClasses": [{"name": "CHEM"}],
                    }
                ],
            }
        )
        item_groups._generate_dataset(dataset, define_objects, "en", "LF.acrf")
        itg = define_objects["ItemGroupDef"][0]
        assert itg.Class.Name == "FINDINGS"
        assert _names_and_parents(itg.Class) == [
            ("LAB", None),
            ("CHEM", "LAB"),
        ]

    def test_observation_class_without_subclasses(self, item_groups):
        item_groups.lang = "en"
        define_objects = self._make_define_objects()
        dataset = self._minimal_dataset(observation_class={"name": "Events"})
        item_groups._generate_dataset(dataset, define_objects, "en", "LF.acrf")
        itg = define_objects["ItemGroupDef"][0]
        assert itg.Class.Name == "EVENTS"
        assert itg.Class.SubClass == []

    def test_no_observation_class_emits_no_class(self, item_groups):
        item_groups.lang = "en"
        define_objects = self._make_define_objects()
        dataset = self._minimal_dataset(observation_class=None)
        item_groups._generate_dataset(dataset, define_objects, "en", "LF.acrf")
        itg = define_objects["ItemGroupDef"][0]
        assert itg.Class is None


class TestEndToEndGenerator:
    """Run the full generator pipeline with nested subClasses in the DDS JSON."""

    def _minimal_dds(self):
        return {
            "OID": "MDV.NESTED",
            "name": "MDV NESTED",
            "description": "Nested SubClass smoke test",
            "fileOID": "ODM.NESTED",
            "creationDateTime": "2026-06-16T00:00:00+00:00",
            "odmVersion": "1.3.2",
            "fileType": "Snapshot",
            "originator": "test",
            "context": "Other",
            "defineVersion": "2.1.0",
            "studyOID": "ODM.NESTED.Study",
            "studyName": "Nested Study",
            "studyDescription": "Nested SubClass smoke test",
            "protocolName": "NESTED",
            "itemGroups": [
                {
                    "OID": "IG.AE",
                    "name": "AE",
                    "description": "Adverse Events",
                    "domain": "AE",
                    "purpose": "Tabulation",
                    "structure": "One record per adverse event per subject",
                    "observationClass": {
                        "name": "Findings",
                        "subClasses": [
                            {
                                "name": "LAB",
                                "subClasses": [
                                    {
                                        "name": "CHEM",
                                        "subClasses": [
                                            {
                                                "name": "ALK",
                                                "subClasses": [
                                                    {
                                                        "name": "L4",
                                                        "subClasses": [
                                                            {"name": "DROPPED"}
                                                        ],
                                                    }
                                                ],
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    },
                    "items": [
                        {
                            "OID": "IT.AE.STUDYID",
                            "name": "STUDYID",
                            "description": "Study Identifier",
                            "role": "Identifier",
                            "dataType": "text",
                            "mandatory": True,
                        }
                    ],
                }
            ],
        }

    def test_pipeline_emits_flattened_subclasses(self, temp_output_dir):
        from define_generator import DefineGenerator

        dds_path = temp_output_dir / "nested_subclasses.json"
        with open(dds_path, "w") as f:
            json.dump(self._minimal_dds(), f)
        output_xml = temp_output_dir / "nested_subclasses.xml"

        dg = DefineGenerator(
            dds_file=str(dds_path),
            define_file=str(output_xml),
            log_level="WARNING",
        )
        dg.create()

        assert output_xml.exists()
        tree = ET.parse(output_xml)
        ns = {"def": "http://www.cdisc.org/ns/def/v2.1"}
        class_elems = tree.getroot().findall(".//def:Class", ns)
        assert len(class_elems) == 1
        class_elem = class_elems[0]
        assert class_elem.get("Name") == "FINDINGS"
        sub_elems = class_elem.findall("def:SubClass", ns)
        assert [(sc.get("Name"), sc.get("ParentClass")) for sc in sub_elems] == [
            ("LAB", None),
            ("CHEM", "LAB"),
            ("ALK", "CHEM"),
            ("L4", "ALK"),
        ]
        assert all(sc.get("Name") != "DROPPED" for sc in sub_elems)
