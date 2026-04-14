from odmlib.define_2_1 import model as DEFINE
import define_object


class ItemRefs(define_object.DefineObject):
    """ create a Define-XML v2.1 ItemRef element objects """
    def __init__(self):
        super().__init__()
        self.lookup_oid = None
        self.igd = None
        self.item_def_oids = []
        self.vlm_oids = []

    def create_define_objects(self, template, define_objects, lang, acrf, item_group=None):
        self.lang = lang
        self.acrf = acrf
        for order, variable in enumerate(template, start=1):
            self._create_itemref_object(variable, define_objects, item_group, variable.get("OID"), order)

    def _create_itemref_object(self, obj, define_objects, igd, it_oid, order):
        if not it_oid:
            raise ValueError("Required field OID is missing in ItemRef")
        # TODO fix as this mandatory can also be set in optional attributes
        if "mandatory" not in obj:
            mandatory = "No"
        else:
            if obj["mandatory"]:
                mandatory = "Yes"
            else:
                mandatory = "No"
        attr = {"ItemOID": it_oid, "Mandatory": mandatory}
        self._add_optional_itemref_attributes(attr, obj, order)
        # Bypass odmlib descriptor validation to allow __PLACEHOLDER__ values
        # item = DEFINE.ItemRef(**attr)
        # TODO a hack to allow the KeySequence to be set to __PLACEHOLDER__ that will be replaced with odmlib v0.2.0
        item = object.__new__(DEFINE.ItemRef)
        for key, value in attr.items():
            item.__dict__[key] = value

        igd.ItemRef.append(item)

    @staticmethod
    def _add_optional_itemref_attributes(attr, obj, order):
        """
        use the values from the variable definition in the DDS JSON to add the optional attributes to the attr dictionary
        :param attr: ItemRef template attributes to update with optional values
        :param obj: variable definition dictionary from the DDS JSON
        """
        # TODO does method exist on items in the DDS?
        if obj.get("method"):
            attr["MethodOID"] = obj["method"]
        if obj.get("order"):
            attr["OrderNumber"] = int(obj["order"])
        else:
            attr["OrderNumber"] = order
        # KeySequence is not in DDS, so a placeholder is added to the first ItemRef
        if obj.get("keySequence"):
            attr["KeySequence"] = int(obj["keySequence"])
        elif order == 1:
            attr["KeySequence"] = "__PLACEHOLDER__"
        if obj.get("role"):
            attr["Role"] = obj["role"]
        if obj.get("isNonStandard"):
            attr["IsNonStandard"] = obj["isNonStandard"]
        if obj.get("hasNoData"):
            attr["HasNoData"] = obj["hasNoData"]
