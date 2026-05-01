from odmlib.define_2_1 import model as DEFINE
import define_object
import items


class ValueLevel(define_object.DefineObject):
    """ create a Define-XML v2.1 ValueListDef element template """
    def __init__(self):
        super().__init__()
        self.lookup_oid = None
        self.vld = None

    def create_define_objects(self, slice, define_objects, lang, acrf):
        """
        parse the define-template and create a odmlib define_objects to return in the define_objects dictionary
        """
        self.lang = lang
        self.acrf = acrf
        vld_obj = self._create_valuelistdef_object(slice["OID"])
        define_objects["ValueListDef"].append(vld_obj)

        for item in slice["items"]:
            itr = self._create_itemref_object(item)
            vld_obj.ItemRef.append(itr)

        # create ItemDefs referenced by ValueListDef ItemRefs; Items.create_define_objects
        # now dedups by OID, so slice items that share an OID with their parent column
        # ItemDef no longer land duplicated in the output.
        items.Items().create_define_objects(slice["items"], define_objects, lang, acrf)

    @staticmethod
    def _create_valuelistdef_object(oid):
        return DEFINE.ValueListDef(OID=oid)

    @staticmethod
    def _create_itemref_object(item):
        attr = {"ItemOID": item["OID"]}
        if item.get("order"):
            attr["OrderNumber"] = int(item["order"])
        if item.get("method"):
            attr["MethodOID"] = item["method"]
        attr["Mandatory"] = "Yes" if item.get("mandatory", False) else "No"
        ir = DEFINE.ItemRef(**attr)
        applicable_when = item.get("applicableWhen") or []
        if applicable_when:
            # TODO when there are multiple applicableWhen values only the first is wired up
            ir.WhereClauseRef.append(DEFINE.WhereClauseRef(WhereClauseOID=applicable_when[0]))
        return ir
