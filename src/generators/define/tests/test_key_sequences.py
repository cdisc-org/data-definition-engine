"""
Tests for PostProcessing key-sequence handling.

``PostProcessing._add_key_sequences`` walks the finished ``ItemGroupDef`` objects,
matches each to its template item group by ``OID``, and — when the template item
group carries a ``keySequence`` (an ordered list of variable names) — assigns
``ItemRef.KeySequence`` to the 1-based position of the variable within that list.
Variables not named in the ``keySequence`` are left untouched.
"""
import pytest


def _new_item_group_def(oid, item_oids):
    """Build a permissive ItemGroupDef with one ItemRef per item OID."""
    from odmlib.define_2_1 import model as DEFINE
    from odmlib import permissive

    with permissive():
        igd = DEFINE.ItemGroupDef(OID=oid)
        igd.ItemRef = [DEFINE.ItemRef(ItemOID=item_oid) for item_oid in item_oids]
    return igd


def _define_objects(item_group_defs):
    """A minimal define_objects dict with the containers process_define_objects touches."""
    return {
        "ItemDef": [],
        "ItemGroupDef": list(item_group_defs),
        "ValueListDef": [],
        "MethodDef": [],
    }


def _key_seq_by_name(igd):
    """Map the trailing token of each ItemRef's ItemOID to its assigned KeySequence."""
    return {ir.ItemOID.split(".")[-1]: ir.KeySequence for ir in igd.ItemRef}


class TestAddItemRefKeySequences:
    """The static core: assign KeySequence from a single (igd, template group) pair."""

    def test_assigns_one_based_index_for_key_variables(self):
        import post_processing
        igd = _new_item_group_def(
            "IG.DS", ["IT.DS.STUDYID", "IT.DS.DOMAIN", "IT.DS.USUBJID", "IT.DS.DSSEQ"]
        )
        tgd = {"OID": "IG.DS", "keySequence": ["STUDYID", "USUBJID", "DSSEQ"]}

        post_processing.PostProcessing._add_item_ref_key_sequences(igd, tgd)

        seqs = _key_seq_by_name(igd)
        assert seqs["STUDYID"] == 1
        assert seqs["USUBJID"] == 2
        assert seqs["DSSEQ"] == 3

    def test_non_key_variables_are_left_untouched(self):
        import post_processing
        igd = _new_item_group_def(
            "IG.DS", ["IT.DS.STUDYID", "IT.DS.DOMAIN", "IT.DS.USUBJID", "IT.DS.DSSEQ"]
        )
        tgd = {"OID": "IG.DS", "keySequence": ["STUDYID", "USUBJID", "DSSEQ"]}

        post_processing.PostProcessing._add_item_ref_key_sequences(igd, tgd)

        # DOMAIN is not part of the key sequence, so its KeySequence stays unset.
        assert _key_seq_by_name(igd)["DOMAIN"] is None

    def test_item_oid_trailing_token_is_matched_case_insensitively(self):
        import post_processing
        # Lower-case variable token in the OID must still match the upper-case key list.
        igd = _new_item_group_def("IG.DS", ["IT.DS.studyid", "IT.DS.usubjid"])
        tgd = {"OID": "IG.DS", "keySequence": ["STUDYID", "USUBJID"]}

        post_processing.PostProcessing._add_item_ref_key_sequences(igd, tgd)

        seqs = _key_seq_by_name(igd)
        assert seqs["studyid"] == 1
        assert seqs["usubjid"] == 2

    def test_placeholder_key_sequence_matches_nothing(self):
        import post_processing
        # The loader emits ['__PLACEHOLDER__'] when the real key sequence is unknown.
        igd = _new_item_group_def("IG.SC", ["IT.SC.STUDYID", "IT.SC.SCSEQ"])
        tgd = {"OID": "IG.SC", "keySequence": ["__PLACEHOLDER__"]}

        post_processing.PostProcessing._add_item_ref_key_sequences(igd, tgd)

        assert all(seq is None for seq in _key_seq_by_name(igd).values())


class TestAddKeySequences:
    """The instance driver: match ItemGroupDefs to template groups by OID."""

    def _pp(self, define_objects, template_objects):
        import post_processing
        return post_processing.PostProcessing(
            define_objects, template_objects, is_xpt=False, lang="en"
        )

    def test_matching_item_group_receives_key_sequences(self):
        igd = _new_item_group_def("IG.DM", ["IT.DM.STUDYID", "IT.DM.DOMAIN", "IT.DM.USUBJID"])
        define_objects = _define_objects([igd])
        template_objects = {
            "itemGroups": [{"OID": "IG.DM", "keySequence": ["STUDYID", "USUBJID"]}]
        }

        self._pp(define_objects, template_objects)._add_key_sequences()

        seqs = _key_seq_by_name(igd)
        assert seqs == {"STUDYID": 1, "DOMAIN": None, "USUBJID": 2}

    def test_item_group_without_key_sequence_is_skipped(self):
        igd = _new_item_group_def("IG.DM", ["IT.DM.STUDYID", "IT.DM.USUBJID"])
        define_objects = _define_objects([igd])
        # keySequence absent entirely -> nothing assigned.
        template_objects = {"itemGroups": [{"OID": "IG.DM"}]}

        self._pp(define_objects, template_objects)._add_key_sequences()

        assert all(seq is None for seq in _key_seq_by_name(igd).values())

    def test_none_key_sequence_is_skipped(self):
        igd = _new_item_group_def("IG.DM", ["IT.DM.STUDYID", "IT.DM.USUBJID"])
        define_objects = _define_objects([igd])
        # A falsy keySequence (None) must not trigger assignment.
        template_objects = {"itemGroups": [{"OID": "IG.DM", "keySequence": None}]}

        self._pp(define_objects, template_objects)._add_key_sequences()

        assert all(seq is None for seq in _key_seq_by_name(igd).values())

    def test_item_group_without_matching_template_is_unchanged(self):
        igd = _new_item_group_def("IG.DM", ["IT.DM.STUDYID", "IT.DM.USUBJID"])
        define_objects = _define_objects([igd])
        # Template describes a different item group; OIDs never match.
        template_objects = {
            "itemGroups": [{"OID": "IG.DS", "keySequence": ["STUDYID", "USUBJID"]}]
        }

        self._pp(define_objects, template_objects)._add_key_sequences()

        assert all(seq is None for seq in _key_seq_by_name(igd).values())

    def test_only_matching_group_is_affected_among_many(self):
        igd_dm = _new_item_group_def("IG.DM", ["IT.DM.STUDYID", "IT.DM.USUBJID"])
        igd_ds = _new_item_group_def("IG.DS", ["IT.DS.STUDYID", "IT.DS.DSSEQ"])
        define_objects = _define_objects([igd_dm, igd_ds])
        template_objects = {
            "itemGroups": [
                {"OID": "IG.DM", "keySequence": ["STUDYID", "USUBJID"]},
                {"OID": "IG.DS"},  # no keySequence -> untouched
            ]
        }

        self._pp(define_objects, template_objects)._add_key_sequences()

        assert _key_seq_by_name(igd_dm) == {"STUDYID": 1, "USUBJID": 2}
        assert all(seq is None for seq in _key_seq_by_name(igd_ds).values())


class TestProcessDefineObjectsAppliesKeySequences:
    """process_define_objects() must run key-sequence assignment as part of the pipeline."""

    def test_key_sequences_applied_end_to_end(self):
        import post_processing
        igd = _new_item_group_def(
            "IG.DS", ["IT.DS.STUDYID", "IT.DS.DOMAIN", "IT.DS.USUBJID", "IT.DS.DSSEQ"]
        )
        define_objects = _define_objects([igd])
        template_objects = {
            "itemGroups": [{"OID": "IG.DS", "keySequence": ["STUDYID", "USUBJID", "DSSEQ"]}]
        }

        post_processing.PostProcessing(
            define_objects, template_objects, is_xpt=False, lang="en"
        ).process_define_objects()

        seqs = _key_seq_by_name(igd)
        assert seqs["STUDYID"] == 1
        assert seqs["USUBJID"] == 2
        assert seqs["DSSEQ"] == 3
        assert seqs["DOMAIN"] is None
