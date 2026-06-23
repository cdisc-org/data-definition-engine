"""
Unit tests for Items._add_optional_itemdef_attributes, focused on the
displayFormat -> SignificantDigits/Length fallback (the issue-78 workaround).

The fallback parses obj['displayFormat'] (e.g. "8.3") into a Length /
SignificantDigits pair when the study JSON omits them. The hardened version must:
  * never raise when the format lacks exactly one dot (the old split(".")
    unpack raised ValueError for "8", "1.2.3", etc.), and
  * yield ints, matching the type of values that arrive straight from the JSON
    (the old code left the derived values as strings).
"""
import pytest


@pytest.fixture
def add_attrs():
    import items
    return items.Items._add_optional_itemdef_attributes


class TestExplicitValuesWin:
    def test_explicit_significant_digits_preserved_as_int(self, add_attrs):
        # An explicit significantDigits short-circuits the displayFormat fallback.
        attr = {}
        add_attrs(attr, {"significantDigits": 2, "dataType": "float", "displayFormat": "8.3"})
        assert attr["SignificantDigits"] == 2
        assert isinstance(attr["SignificantDigits"], int)

    def test_explicit_length_not_overridden_by_displayformat(self, add_attrs):
        attr = {}
        add_attrs(attr, {"dataType": "float", "length": 10, "displayFormat": "8.3"})
        assert attr["Length"] == 10            # explicit length wins
        assert attr["SignificantDigits"] == 3  # sig digits still derived from format
        assert isinstance(attr["SignificantDigits"], int)


class TestDisplayFormatFallback:
    def test_float_displayformat_yields_int_significant_digits_and_length(self, add_attrs):
        attr = {}
        add_attrs(attr, {"dataType": "float", "displayFormat": "8.3"})
        # Core regression: derived values must be ints, not the strings the old
        # split(".") branch produced.
        assert attr["SignificantDigits"] == 3
        assert isinstance(attr["SignificantDigits"], int)
        assert attr["Length"] == 8
        assert isinstance(attr["Length"], int)

    def test_displayformat_without_dot_does_not_raise(self, add_attrs):
        # "8" has no dot; old split(".") -> single element -> ValueError on unpack.
        attr = {}
        add_attrs(attr, {"dataType": "float", "displayFormat": "8"})
        assert "SignificantDigits" not in attr
        # The whole-number portion is still recovered into the placeholder slot.
        assert attr["Length"] == 8
        assert isinstance(attr["Length"], int)

    def test_displayformat_with_multiple_dots_does_not_raise(self, add_attrs):
        # "1.2.3" -> old split(".") -> three elements -> ValueError on unpack.
        attr = {}
        add_attrs(attr, {"dataType": "float", "displayFormat": "1.2.3"})
        # "2.3" is not a pure digit string, so no SignificantDigits is derived.
        assert "SignificantDigits" not in attr
        assert attr["Length"] == 1

    def test_non_numeric_displayformat_leaves_placeholder(self, add_attrs):
        attr = {}
        add_attrs(attr, {"dataType": "float", "displayFormat": "DATE9."})
        assert "SignificantDigits" not in attr
        assert attr["Length"] == "__PLACEHOLDER__"  # nothing numeric to recover
        assert attr["DisplayFormat"] == "DATE9."

    def test_fallback_only_applies_to_float_datatype(self, add_attrs):
        attr = {}
        add_attrs(attr, {"dataType": "text", "displayFormat": "8.3"})
        assert "SignificantDigits" not in attr
        assert attr["DisplayFormat"] == "8.3"
