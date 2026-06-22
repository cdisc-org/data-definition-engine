"""
Tests for ItemDef Origin generation under both the current (dict) and future
(list-of-dicts) shapes of `origin` in the DDS JSON.
"""
import pytest


@pytest.fixture
def items_instance():
    import items
    inst = items.Items()
    inst.lang = "en"
    inst.acrf = "LF.ACRF"
    return inst


def _new_itemdef():
    """Mirror the descriptor-bypass pattern used in Items._create_itemdef_object."""
    from odmlib.define_2_1 import model as DEFINE
    item = object.__new__(DEFINE.ItemDef)
    item.__dict__["Origin"] = []
    return item


class TestOriginDictShape:
    """Today's shape: obj['origin'] is a single dict, predecessor/pages live on obj."""

    def test_single_origin_dict_produces_one_origin(self, items_instance):
        item = _new_itemdef()
        obj = {"origin": {"type": "Collected", "source": "Investigator"}}
        items_instance._add_origin(item, obj)
        assert len(item.Origin) == 1
        assert item.Origin[0].Type == "Collected"
        assert item.Origin[0].Source == "Investigator"

    def test_collected_investigator_attaches_acrf_documentref(self, items_instance):
        item = _new_itemdef()
        obj = {"origin": {"type": "Collected", "source": "Investigator"}}
        items_instance._add_origin(item, obj)
        assert len(item.Origin[0].DocumentRef) == 1
        assert item.Origin[0].DocumentRef[0].leafID == "LF.ACRF"

    def test_item_level_predecessor_folded_into_wrapped_origin(self, items_instance):
        item = _new_itemdef()
        obj = {
            "origin": {"type": "Predecessor"},
            "predecessor": "DM.USUBJID",
        }
        items_instance._add_origin(item, obj)
        assert item.Origin[0].Description.TranslatedText[0]._content == "DM.USUBJID"

    def test_item_level_pages_folded_into_wrapped_origin(self, items_instance):
        item = _new_itemdef()
        obj = {
            "origin": {"type": "Collected", "source": "Investigator"},
            "pages": "5-7",
        }
        items_instance._add_origin(item, obj)
        page_refs = [
            pr for dr in item.Origin[0].DocumentRef for pr in dr.PDFPageRef
            if pr.PageRefs == "5-7"
        ]
        assert page_refs


class TestOriginDictFolding:
    """Edge cases in folding item-level predecessor/pages into the single dict shape."""

    def test_predecessor_and_pages_folded_together(self, items_instance):
        item = _new_itemdef()
        obj = {
            "origin": {"type": "Collected", "source": "Investigator"},
            "predecessor": "DM.USUBJID",
            "pages": "5-7",
        }
        items_instance._add_origin(item, obj)
        assert item.Origin[0].Description.TranslatedText[0]._content == "DM.USUBJID"
        page_refs = [
            pr.PageRefs for dr in item.Origin[0].DocumentRef for pr in dr.PDFPageRef
        ]
        assert "5-7" in page_refs

    def test_origin_own_predecessor_wins_over_item_level(self, items_instance):
        # The wrapped dict already carries a predecessor, so the item-level sibling
        # must NOT clobber it ("predecessor not in wrapped" guard).
        item = _new_itemdef()
        obj = {
            "origin": {"type": "Predecessor", "predecessor": "ORIGIN.LEVEL"},
            "predecessor": "ITEM.LEVEL",
        }
        items_instance._add_origin(item, obj)
        assert item.Origin[0].Description.TranslatedText[0]._content == "ORIGIN.LEVEL"

    def test_origin_own_pages_wins_over_item_level(self, items_instance):
        item = _new_itemdef()
        obj = {
            "origin": {"type": "Collected", "source": "Investigator", "pages": "99"},
            "pages": "5-7",
        }
        items_instance._add_origin(item, obj)
        page_refs = [
            pr.PageRefs for dr in item.Origin[0].DocumentRef for pr in dr.PDFPageRef
        ]
        assert "99" in page_refs
        assert "5-7" not in page_refs


class TestOriginListShape:
    """Future shape: obj['origin'] is a list of origin dicts, each self-contained."""

    def test_single_element_list_equivalent_to_dict(self, items_instance):
        item = _new_itemdef()
        obj = {"origin": [{"type": "Collected", "source": "Investigator"}]}
        items_instance._add_origin(item, obj)
        assert len(item.Origin) == 1
        assert item.Origin[0].Type == "Collected"
        assert item.Origin[0].Source == "Investigator"

    def test_empty_list_produces_no_origins(self, items_instance):
        item = _new_itemdef()
        items_instance._add_origin(item, {"origin": []})
        assert item.Origin == []

    def test_item_level_predecessor_not_folded_into_list_shape(self, items_instance):
        # Folding is intentionally dict-shape only. In the list shape each origin is
        # self-contained, so an item-level predecessor sibling must be ignored.
        item = _new_itemdef()
        obj = {
            "origin": [{"type": "Predecessor"}],
            "predecessor": "ITEM.LEVEL",
        }
        items_instance._add_origin(item, obj)
        # No predecessor text should have been emitted for the origin.
        assert item.Origin[0].Description.TranslatedText == []

    def test_item_level_pages_not_folded_into_list_shape(self, items_instance):
        item = _new_itemdef()
        obj = {
            "origin": [{"type": "Predecessor"}],
            "pages": "5-7",
        }
        items_instance._add_origin(item, obj)
        page_refs = [
            pr.PageRefs for dr in item.Origin[0].DocumentRef for pr in dr.PDFPageRef
        ]
        assert "5-7" not in page_refs

    def test_multiple_origins_produce_multiple_elements(self, items_instance):
        item = _new_itemdef()
        obj = {
            "origin": [
                {"type": "Derived"},
                {"type": "Predecessor", "predecessor": "DM.USUBJID"},
            ]
        }
        items_instance._add_origin(item, obj)
        assert len(item.Origin) == 2
        assert item.Origin[0].Type == "Derived"
        assert item.Origin[1].Type == "Predecessor"
        assert item.Origin[1].Description.TranslatedText[0]._content == "DM.USUBJID"

    def test_per_origin_pages_in_list_shape(self, items_instance):
        item = _new_itemdef()
        obj = {
            "origin": [
                {"type": "Collected", "source": "Investigator", "pages": "10"},
                {"type": "Collected", "source": "Investigator", "pages": "20"},
            ]
        }
        items_instance._add_origin(item, obj)
        # Each origin gets the acrf DocumentRef (Collected/Investigator rule) plus its own pages DocumentRef.
        page_refs_per_origin = [
            sorted(pr.PageRefs for dr in o.DocumentRef for pr in dr.PDFPageRef)
            for o in item.Origin
        ]
        assert "10" in page_refs_per_origin[0]
        assert "20" in page_refs_per_origin[1]
        assert "10" not in page_refs_per_origin[1]


class TestPostProcessingMultiOrigin:
    """post_processing._add_derived_methods must trigger when ANY origin is Derived."""

    def _build_objects(self, origin_value):
        from odmlib.define_2_1 import model as DEFINE
        item = _new_itemdef()
        item.__dict__["OID"] = "IT.DM.USUBJID"

        items_inst_module = __import__("items")
        inst = items_inst_module.Items()
        inst.lang = "en"
        inst.acrf = "LF.ACRF"
        inst._add_origin(item, {"origin": origin_value})

        igd = object.__new__(DEFINE.ItemGroupDef)
        ir = object.__new__(DEFINE.ItemRef)
        ir.__dict__["ItemOID"] = item.OID
        ir.__dict__["MethodOID"] = None
        igd.__dict__["ItemRef"] = [ir]

        return {
            "ItemDef": [item],
            "ItemGroupDef": [igd],
            "ValueListDef": [],
            "MethodDef": [],
        }, ir

    def test_derived_in_first_origin_triggers_method(self):
        import post_processing
        objects, ir = self._build_objects([{"type": "Derived"}, {"type": "Predecessor"}])
        post_processing.PostProcessing(objects, is_xpt=False, lang="en").process_define_objects()
        assert ir.MethodOID is not None
        assert len(objects["MethodDef"]) == 1

    def test_derived_in_later_origin_still_triggers_method(self):
        import post_processing
        objects, ir = self._build_objects(
            [{"type": "Collected", "source": "Investigator"}, {"type": "Derived"}]
        )
        post_processing.PostProcessing(objects, is_xpt=False, lang="en").process_define_objects()
        assert ir.MethodOID is not None
        assert len(objects["MethodDef"]) == 1

    def test_no_derived_origin_skips_method(self):
        import post_processing
        objects, ir = self._build_objects(
            [{"type": "Collected", "source": "Investigator"}, {"type": "Predecessor"}]
        )
        post_processing.PostProcessing(objects, is_xpt=False, lang="en").process_define_objects()
        assert ir.MethodOID is None
        assert objects["MethodDef"] == []
