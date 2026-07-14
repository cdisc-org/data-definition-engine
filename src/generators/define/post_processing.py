from typing import Any
from odmlib.define_2_1 import model as DEFINE
import methods
import define_object

class PostProcessing:
    """
    Base class for post-processing Define-XML elements.
    """
    def __init__(self, define_objects: dict[str, list[Any]], template_objects: dict[str, list[Any]], is_xpt: bool, lang: str):
        self.define_objects = define_objects
        self.template_objects = template_objects
        self.is_xpt = is_xpt
        self.lang = lang

    def process_define_objects(self) -> None:
        self._add_derived_methods()
        self._add_key_sequences()
        if self.is_xpt:
            self._update_dataset_file_type_to_xpt()


    def _add_key_sequences(self):
        """
        go through all item groups and find and assign key sequences
        """
        for igd in self.define_objects['ItemGroupDef']:
            for tgd in self.template_objects['itemGroups']:
                if igd.OID == tgd["OID"]:
                    if tgd.get("keySequence"):
                        self._add_item_ref_key_sequences(igd, tgd)

    @staticmethod
    def _add_item_ref_key_sequences(igd: Any, tgd: Any) -> None:
        """
        once an item group with a key sequence is found, assign the key sequence to the item ref
        :param igd: define-xml ItemGroupDef object
        :param tgd: template item group object
        """
        key_sequence = tgd["keySequence"]
        for ir in igd.ItemRef:
            oid_parts = ir.ItemOID.split('.')
            if oid_parts and (oid_parts[-1].upper() in key_sequence):
                ir.KeySequence = key_sequence.index(oid_parts[-1].upper()) + 1

    def _update_dataset_file_type_to_xpt(self) -> None:
        """
        Update the ItemGroupDef dataset extension .xpt if is_xpt is True.
        <def:leaf ID="LF.SUPPDM" xlink:href="suppdm.xpt">
          <def:title>suppdm.xpt</def:title>
        </def:leaf>
        """
        for igd in self.define_objects['ItemGroupDef']:
            if igd.leaf.href.endswith('.ndjson'):
                igd.leaf.href = igd.leaf.href.replace('.ndjson', '.xpt')
                igd.leaf.title._content = igd.leaf.title._content.replace('.ndjson', '.xpt')


    def _add_derived_methods(self) -> None:
        """
        Add methods to ItemDefs where the def:Origin Type="Derived".
        """
        for item_def in self.define_objects['ItemDef']:
            if any(getattr(o, "Type", None) == "Derived" for o in (item_def.Origin or [])):
                # generate the MethodOID
                method_oid = self._generate_method_oid(item_def.OID)
                # find the ItemRef and add a MethodOID attribute
                is_new_method = self._update_item_ref(item_def, method_oid)
                # create the MethodDef with the MethodOID attribute
                if is_new_method:
                    self._create_method_def(method_oid, item_def)

    def _create_method_def(self, method_oid, item_def) -> None:
        item_oid_parts = item_def.OID.split('.')
        item_name = " ".join(item_oid_parts[-2:])
        attr = {"OID": method_oid, "Name": "Derive " + item_name, "Type": "Computation"}
        method_def = DEFINE.MethodDef(**attr)
        tt = DEFINE.TranslatedText(_content="__PLACEHOLDER__ for derivation of " + item_name, lang=self.lang)
        method_def.Description = DEFINE.Description()
        method_def.Description.TranslatedText.append(tt)
        self.define_objects['MethodDef'].append(method_def)

    def _update_item_ref(self, item_def, method_oid) -> bool:
        # inefficient, but works for now
        is_new_method = False
        for ir_group in ["ItemGroupDef", "ValueListDef"]:
            # check ItemGroupDefs
            for igd in self.define_objects[ir_group]:
                for ir in igd.ItemRef:
                    if ir.ItemOID == item_def.OID:
                        if ir.MethodOID is None:
                            ir.MethodOID = method_oid
                            is_new_method = True
        return is_new_method

    def _generate_method_oid(self, item_oid) -> str:
        do = define_object.DefineObject()
        item_oid_parts = item_oid.split('.')
        if item_oid_parts[0] == 'IT':
            item_oid_parts.pop(0)
        item_oid_parts.insert(0, 'MT')
        method_oid = do.generate_oid(item_oid_parts)
        return method_oid
