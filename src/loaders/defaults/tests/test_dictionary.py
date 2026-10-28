"""Tests for the defaults dictionary: the schema, the seed, duplicates and the ranking."""
from __future__ import annotations

import json

import pytest

from loaders.defaults.defaults_loader import DEFAULT_DICTIONARY
from loaders.defaults.dictionary import Dictionary, DictionaryError, Entry


def _write(tmp_path, content, name="d.json"):
    path = tmp_path / name
    path.write_text(json.dumps(content), encoding="utf-8")
    return str(path)


class TestSeed:
    def test_the_seed_validates_and_loads(self):
        loaded = Dictionary.load([DEFAULT_DICTIONARY])
        assert len(loaded.entries) == 95
        assert {e.section for e in loaded.entries} == {"items"}

    def test_every_seed_entry_states_its_basis(self):
        seed = json.loads(DEFAULT_DICTIONARY.read_text(encoding="utf-8"))
        assert all(entry.get("description") for entry in seed["items"])


class TestInvalid:
    @pytest.mark.parametrize("content, message", [
        ({"schemaVersion": "1.0", "items": [{"name": "X", "values": {"origin": [
            {"type": "Typed", "source": "Sponsor"}]}}]}, "items/0/values/origin/0/type"),
        ({"schemaVersion": "1.0", "crfSections": [{"name": "S", "values": {"length": 3}}]},
         "'length' was unexpected"),
        ({"schemaVersion": "1.0", "items": [{"name": "X", "values": {"keySequence": ["A"]}}]},
         "'keySequence' was unexpected"),
        ({"schemaVersion": "1.0", "variables": []}, "'variables' was unexpected"),
        ({"schemaVersion": "1.0", "items": [{"name": "*", "values": {"length": 1}}]},
         "'domains' is a required property"),
        ({"schemaVersion": "1.0", "items": [{"name": "--", "values": {"length": 1}}]}, "items/0/name"),
        ({"schemaVersion": "1.0", "items": [{"name": "X", "values": {"length": {"lengthOf": "title"}}}]},
         "items/0/values/length"),
        ({"schemaVersion": "2.0", "items": []}, "schemaVersion 2.0 is not supported"),
        ({"items": []}, "'schemaVersion' is a required property"),
    ])
    def test_invalid_content_is_rejected(self, tmp_path, content, message):
        with pytest.raises(DictionaryError, match="not usable") as excinfo:
            Dictionary.load([_write(tmp_path, content)])
        assert message in str(excinfo.value)

    def test_an_unreadable_file_is_rejected(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{", encoding="utf-8")
        with pytest.raises(DictionaryError, match="broken.json"):
            Dictionary.load([str(path)])

    def test_a_repeated_entry_in_one_section_is_rejected(self, tmp_path):
        entry = {"name": "--SEQ", "values": {"length": 3}}
        with pytest.raises(DictionaryError, match="two entries for --SEQ"):
            Dictionary.load([_write(tmp_path, {"schemaVersion": "1.0", "items": [entry, entry]})])

    def test_the_same_name_in_two_sections_or_with_other_domains_is_allowed(self, tmp_path):
        content = {"schemaVersion": "1.0",
                   "items": [{"name": "AETERM", "values": {"length": 200}},
                             {"name": "AETERM", "domains": ["AE"], "values": {"length": 100}}],
                   "crfItems": [{"name": "AETERM", "values": {"length": 50}}]}
        assert len(Dictionary.load([_write(tmp_path, content)]).entries) == 3


class TestRanking:
    def _best(self, entries, name, domain, section="items"):
        found = Dictionary(entries, []).candidates(section, name, domain)
        return [e.label for e in found]

    def test_exact_then_longer_suffix_then_shorter_suffix_then_star(self):
        entries = [Entry("items", "*", {}, domains=frozenset({"LB"})), Entry("items", "--CAT", {}),
                   Entry("items", "--SCAT", {}), Entry("items", "LBSCAT", {})]
        assert self._best(entries, "LBSCAT", "LB") == ["LBSCAT", "--SCAT", "--CAT", "* [LB]"]

    def test_a_domain_filter_wins_at_equal_rank(self):
        entries = [Entry("items", "--DTC", {}), Entry("items", "--DTC", {}, domains=frozenset({"SE", "SV"}))]
        assert self._best(entries, "SESTDTC", "SE") == ["--DTC [SE, SV]", "--DTC"]
        assert self._best(entries, "AESTDTC", "AE") == ["--DTC"]

    def test_a_later_file_wins_at_equal_rank(self):
        entries = [Entry("items", "STUDYID", {}, file="a.json", order=0),
                   Entry("items", "STUDYID", {}, file="b.json", order=1)]
        assert [e.file for e in Dictionary(entries, []).candidates("items", "STUDYID", "LB")] == ["b.json", "a.json"]

    def test_a_suffix_needs_a_longer_name(self):
        assert self._best([Entry("items", "--SEQ", {})], "SEQ", "LB") == []
        assert self._best([Entry("items", "--SEQ", {})], "LBSEQ", "LB") == ["--SEQ"]

    def test_exclude_domains(self):
        entries = [Entry("items", "EPOCH", {}, exclude=frozenset({"TA"}))]
        assert self._best(entries, "EPOCH", "TA") == []
        assert self._best(entries, "EPOCH", "SE") == ["EPOCH [not TA]"]

    def test_sections_stay_apart(self):
        entries = [Entry("crfItems", "AETERM", {})]
        assert self._best(entries, "AETERM", "AE", section="items") == []
        assert self._best(entries, "AETERM", "AE", section="crfItems") == ["AETERM"]

    def test_entries_that_match_nothing_are_unmatched(self):
        dictionary = Dictionary([Entry("items", "--SEQ", {}), Entry("items", "NOSUCH", {})], [])
        dictionary.candidates("items", "LBSEQ", "LB")
        assert [e.name for e in dictionary.unmatched()] == ["NOSUCH"]
