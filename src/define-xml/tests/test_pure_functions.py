"""
Tests for pure / stateless methods in USDMDefineJSONProcessor.

These methods perform only local computation — no file I/O, no CDISC API calls.
All tests use the shared `processor` fixture from conftest.py.
"""

import hashlib


class TestValidateDateFormat:
    """_validate_date_format(date_string) -> bool"""

    def test_valid_date_returns_true(self, processor):
        assert processor._validate_date_format("2025-03-28") is True

    def test_valid_leap_day_returns_true(self, processor):
        assert processor._validate_date_format("2024-02-29") is True

    def test_no_dashes_returns_false(self, processor):
        assert processor._validate_date_format("20250328") is False

    def test_slash_separated_returns_false(self, processor):
        assert processor._validate_date_format("2025/03/28") is False

    def test_month_13_returns_false(self, processor):
        assert processor._validate_date_format("2025-13-01") is False

    def test_day_32_returns_false(self, processor):
        assert processor._validate_date_format("2025-01-32") is False

    def test_feb_30_returns_false(self, processor):
        assert processor._validate_date_format("2025-02-30") is False

    def test_non_leap_feb_29_returns_false(self, processor):
        assert processor._validate_date_format("2025-02-29") is False

    def test_empty_string_returns_false(self, processor):
        assert processor._validate_date_format("") is False

    def test_partial_date_returns_false(self, processor):
        assert processor._validate_date_format("2025-03") is False

    def test_datetime_string_returns_false(self, processor):
        assert processor._validate_date_format("2025-03-28T12:00:00") is False

    def test_single_digit_month_returns_false(self, processor):
        assert processor._validate_date_format("2025-3-28") is False


class TestConvertDataType:
    """_convert_data_type(var) -> str"""

    def test_char_returns_text(self, processor):
        assert processor._convert_data_type({"name": "AEDECOD", "simpleDatatype": "Char"}) == "text"

    def test_num_returns_integer(self, processor):
        assert processor._convert_data_type({"name": "VISITNUM", "simpleDatatype": "Num"}) == "integer"

    def test_dtc_suffix_returns_datetime(self, processor):
        assert processor._convert_data_type({"name": "AESTDTC", "simpleDatatype": "Char"}) == "datetime"

    def test_dtc_suffix_overrides_num_mapping(self, processor):
        # DTC check runs before the type mapping lookup
        assert processor._convert_data_type({"name": "RFSTDTC", "simpleDatatype": "Num"}) == "datetime"

    def test_dur_suffix_returns_duration_datetime(self, processor):
        assert processor._convert_data_type({"name": "EXDUR", "simpleDatatype": "Char"}) == "durationDatetime"

    def test_dur_suffix_overrides_num_mapping(self, processor):
        assert processor._convert_data_type({"name": "EXDUR", "simpleDatatype": "Num"}) == "durationDatetime"

    def test_unknown_datatype_returns_placeholder(self, processor):
        assert processor._convert_data_type({"name": "AEVAL", "simpleDatatype": "Unknown"}) == "????"

    def test_normal_char_variable_not_dtc_or_dur(self, processor):
        assert processor._convert_data_type({"name": "STUDYID", "simpleDatatype": "Char"}) == "text"

    def test_num_variable_not_dtc_or_dur(self, processor):
        assert processor._convert_data_type({"name": "VSSEQ", "simpleDatatype": "Num"}) == "integer"


class TestCreateConditionKey:
    """_create_condition_key(range_checks) -> str"""

    def test_key_contains_item_comparator_and_value(self, processor):
        checks = [{"item": "IT.VS.VSTESTCD", "comparator": "EQ", "checkValues": ["SYSBP"]}]
        key = processor._create_condition_key(checks)
        assert "IT.VS.VSTESTCD" in key
        assert "EQ" in key
        assert "SYSBP" in key

    def test_values_are_sorted_so_order_does_not_matter(self, processor):
        checks_abc = [{"item": "IT.VS.VSTESTCD", "comparator": "IN", "checkValues": ["BMI", "HEIGHT", "WEIGHT"]}]
        checks_zyx = [{"item": "IT.VS.VSTESTCD", "comparator": "IN", "checkValues": ["WEIGHT", "HEIGHT", "BMI"]}]
        assert processor._create_condition_key(checks_abc) == processor._create_condition_key(checks_zyx)

    def test_multiple_checks_sorted_by_item_name(self, processor):
        checks_fwd = [
            {"item": "IT.VS.VSTESTCD", "comparator": "EQ", "checkValues": ["SYSBP"]},
            {"item": "IT.VS.VISITNUM", "comparator": "EQ", "checkValues": ["1"]},
        ]
        checks_rev = [
            {"item": "IT.VS.VISITNUM", "comparator": "EQ", "checkValues": ["1"]},
            {"item": "IT.VS.VSTESTCD", "comparator": "EQ", "checkValues": ["SYSBP"]},
        ]
        assert processor._create_condition_key(checks_fwd) == processor._create_condition_key(checks_rev)

    def test_spaces_stripped_from_concatenated_values(self, processor):
        checks = [{"item": "IT.LB.LBTESTCD", "comparator": "EQ", "checkValues": ["GLUCOSE FASTING"]}]
        key = processor._create_condition_key(checks)
        # ''.join(values).replace(' ', '') removes spaces
        assert "GLUCOSEFASTING" in key

    def test_empty_check_values_produces_stable_key(self, processor):
        checks = [{"item": "IT.VS.VSTESTCD", "comparator": "EQ", "checkValues": []}]
        key = processor._create_condition_key(checks)
        assert isinstance(key, str)
        assert "IT.VS.VSTESTCD" in key

    def test_returns_string(self, processor):
        checks = [{"item": "IT.VS.VSTESTCD", "comparator": "EQ", "checkValues": ["SYSBP"]}]
        assert isinstance(processor._create_condition_key(checks), str)

    def test_different_values_produce_different_keys(self, processor):
        k1 = processor._create_condition_key([{"item": "IT.VS.VSTESTCD", "comparator": "EQ", "checkValues": ["SYSBP"]}])
        k2 = processor._create_condition_key([{"item": "IT.VS.VSTESTCD", "comparator": "EQ", "checkValues": ["DIABP"]}])
        assert k1 != k2


class TestGenerateHexOid:
    """_generate_hex_oid(content, prefix) -> str"""

    def test_result_starts_with_prefix(self, processor):
        assert processor._generate_hex_oid("some content", "COND").startswith("COND.")

    def test_hash_portion_is_exactly_8_characters(self, processor):
        result = processor._generate_hex_oid("some content", "COND")
        hash_part = result.split(".", 1)[1]
        assert len(hash_part) == 8

    def test_hash_portion_is_lowercase_hex(self, processor):
        result = processor._generate_hex_oid("some content", "X")
        hash_part = result.split(".", 1)[1]
        assert all(c in "0123456789abcdef" for c in hash_part)

    def test_deterministic_for_identical_content(self, processor):
        r1 = processor._generate_hex_oid("same content", "PREFIX")
        r2 = processor._generate_hex_oid("same content", "PREFIX")
        assert r1 == r2

    def test_different_content_produces_different_hash(self, processor):
        assert processor._generate_hex_oid("content a", "X") != processor._generate_hex_oid("content b", "X")

    def test_known_md5_hash(self, processor):
        content = "VSTESTCD.EQ.SYSBP"
        expected = "COND." + hashlib.md5(content.encode("utf-8")).hexdigest()[:8]
        assert processor._generate_hex_oid(content, "COND") == expected

    def test_empty_prefix_produces_dot_prefixed_hash(self, processor):
        result = processor._generate_hex_oid("content", "")
        assert result.startswith(".")
        assert len(result) == 9  # "." + 8 hex chars
