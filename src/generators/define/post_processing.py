from typing import Any
from odmlib.define_2_1 import model as DEFINE
import methods
import define_object

class PostProcessing:
    """
    Base class for post-processing Define-XML elements.
    """
    def __init__(self, define_objects: dict[str, list[Any]], lang: str):
        self.define_objects = define_objects
        self.lang = lang

    def process_define_objects(self) -> None:
        self._add_derived_methods()


    def _add_derived_methods(self) -> None:
        """
        Add methods to ItemDefs where the def:Origin Type="Derived".
        """
        for item_def in self.define_objects['ItemDef']:
            # TODO assumes we're only interested in the first origin
            if  item_def.Origin and item_def.Origin[0].Type == 'Derived':
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
        # TODO inefficient, but works for now
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
