"""Walk the DDS Form -> Section -> Concept tree and emit the version's group elements.

This is the CRF generator's most complex loader, the counterpart of the Define
generator's ``itemGroups.py``. It owns the ``slices`` recursion and is the only place
that knows a 1.3.2 document has no Section level: the target returns ``None`` from
:meth:`section`, and the Form is wired straight to the flattened Concepts instead.

ItemDefs are deduplicated by OID because an item shared by several concepts is inlined
once per concept in the DDS — the same dedup the Define generator does for value-list
slices.
"""
from __future__ import annotations

from typing import Any

from generators.crf.constants import CRF_GROUP_TYPES
from generators.crf.crf_object import CrfObject


class ItemGroups(CrfObject):
    """Create Form, Section and Concept group elements plus their ItemDefs."""

    def create_crf_objects(self, template: list[dict[str, Any]],
                           crf_objects: dict[str, Any], target: Any, lang: str) -> None:
        """
        :param template: the DDS ``itemGroups`` list (Define groups included)
        :param crf_objects: shared dict of lists, mutated in place
        :param target: the :class:`OdmTarget`
        :param lang: xml:lang for TranslatedText
        """
        self.lang = lang
        forms = [g for g in template if g.get("type") == "Form"]
        if not forms:
            self.logger.warning(
                "no Form itemGroups in the DDS - run crf_loader.py first to add CRF metadata")
        wanted = crf_objects.get("_form_filter")
        for form in forms:
            if wanted and form.get("OID") not in wanted:
                continue
            self._build_form(form, crf_objects, target, lang)

        skipped = [g.get("OID") for g in template
                   if g.get("type") not in CRF_GROUP_TYPES]
        if skipped:
            self.logger.info("ignored %d non-CRF itemGroup(s) owned by the Define "
                             "generator: %s", len(skipped), ", ".join(map(str, skipped[:5])))

    def _build_form(self, form: dict[str, Any], crf_objects: dict[str, Any],
                    target: Any, lang: str) -> None:
        sections = [s for s in form.get("slices") or [] if s.get("type") == "Section"]
        form_children: list[tuple[str, bool]] = []
        section_oids: list[str] = []

        for section in sections:
            concepts = [c for c in section.get("slices") or [] if c.get("type") == "Concept"]
            concept_children: list[tuple[str, bool]] = []

            for concept in concepts:
                self._build_concept(concept, section, crf_objects, target, lang)
                concept_children.append((concept["OID"], bool(concept.get("mandatory", True))))

            section_element = target.section(section, concept_children, lang)
            if section_element is not None:
                # ODM 2.0: the Form references Sections, which reference Concepts.
                crf_objects["ItemGroupDef"].append(section_element)
                form_children.append((section["OID"], bool(section.get("mandatory", True))))
            else:
                # ODM 1.3.2: no Section level, so the Form references Concepts directly.
                form_children.extend(concept_children)
            section_oids.append(section["OID"])

        # Concepts sitting directly on the Form, with no Section between.
        for concept in (c for c in form.get("slices") or [] if c.get("type") == "Concept"):
            self._build_concept(concept, None, crf_objects, target, lang)
            form_children.append((concept["OID"], bool(concept.get("mandatory", True))))

        form_copy = dict(form)
        form_copy["_sectionOrder"] = section_oids
        form_element = target.form(form_copy, form_children, lang)
        key = "FormDef" if target.version == "1.3.2" else "ItemGroupDef"
        crf_objects.setdefault(key, []).append(form_element)

    def _build_concept(self, concept: dict[str, Any], section: dict[str, Any] | None,
                       crf_objects: dict[str, Any], target: Any, lang: str) -> None:
        items = self.require_key(concept, "items", f"Concept {concept.get('OID')}")
        include_hidden = crf_objects.get("_include_hidden", False)

        item_refs = []
        order = 0
        for item in items:
            if item.get("crfDisplayHidden") and not include_hidden:
                continue
            order += 1
            item_refs.append(target.item_ref(item, order))
            # An item shared by several concepts is inlined in each; emit the ItemDef once.
            if self.find_object(crf_objects["ItemDef"], item["OID"]) is None:
                crf_objects["ItemDef"].append(target.item_def(item, lang))

        concept_element = target.concept(concept, item_refs, lang, section)
        crf_objects["ItemGroupDef"].append(concept_element)
