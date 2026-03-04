from odmlib.define_2_1 import model as DEFINE
import define_object
import whereClauses as WC
import items

# TODO
"""
- Value List definitions are created for variables like VSORRES - this name is referenced in the items and should have the OID of the original variable being redefined
- we have "VL.VS.TEMP" under itemGroups - but this OID isn't used anywhere is it? The value list is V:.VS.VSORRES
- we have itemGroup types, but just one for DataSpecialization. We should have one for datasets as well.
- DataSpecialization should be DatasetSpecialization
"""

class ValueLevel(define_object.DefineObject):
    """ create a Define-XML v2.0 ValueListDef element template """
    def __init__(self):
        super().__init__()
        self.lookup_oid = None
        self.vld = None

    # def create_define_objects(self, template, define_objects, oid, item_oids, lang, acrf):
    def create_define_objects(self, slice, define_objects, lang, acrf):
        """
        parse the define-template and create a odmlib define_objects to return in the define_objects dictionary
                    {
                      "OID": "IT.VS.VSORRES.TEMP",
                      "mandatory": false,
                      "name": "VSORRES",
                      "dataType": "float",
                      "applicableWhen": [
                        "WC.VS.df8e6ed8"
                      ],
                      "displayFormat": "8.3",
                      "significantDigits": 3,
                      "origin": {
                        "type": "Collected",
                        "source": "Investigator"
                      }
                    },
        """
        self.lang = lang
        self.acrf = acrf
        # create ValueListDef
        vld_obj = self._create_valuelistdef_object(slice["OID"], define_objects)
        define_objects["ValueListDef"].append(vld_obj)

        # create ItemRefs in ValueListDef
        for item in slice["items"]:
            itr = self._create_itemref_object(vld_obj, item)
            vld_obj.ItemRef.append(itr)

        # create ItemDefs referenced by ValueListDef ItemRefs
        itd = items.Items()
        itd.create_define_objects(slice["items"], define_objects, lang, acrf)

    def _create_whereclause_object(self, object, define_objects, wc, wc_oid, dataset):
        where_clause = WC.WhereClauses()
        where_clause.create_define_objects(object, define_objects, wc, wc_oid, dataset, self.lang, self.acrf)


    def _get_vld(self, vld_oid, item, define_objects):
        for vld in define_objects["ValueListDef"]:
            if vld.OID == vld_oid:
                return vld
        return None

    def _create_valuelistdef_object(self, oid, define_objects):
        """
        use the values from the VLM define-template to create a ValueListDef odmlib template
        """
        vld = DEFINE.ValueListDef(OID=oid)
        return vld

    def _create_itemref_object(self, vld_obj, item): #   wc, dataset, variable, it_oid):
        attr = {"ItemOID": item["OID"]}
        if item.get("order"):
            attr["Order"] = item["order"]
        if item.get("method"):
            attr["MethodOID"] = item["method"]
        if item.get("mandatory", False):
            attr["Mandatory"] = "Yes"
        else:
            attr["Mandatory"] = "No"
        ir = DEFINE.ItemRef(**attr)
        # TODO determine how to process when there are multiple applicableWhen values
        wc = DEFINE.WhereClauseRef(WhereClauseOID=item["applicableWhen"][0])
        ir.WhereClauseRef.append(wc)
        return ir
