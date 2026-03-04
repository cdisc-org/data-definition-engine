from odmlib.define_2_1 import model as DEFINE
import define_object

class Conditions(define_object.DefineObject):
    """ create a Define-XML v2.1 WhereClauseDef element objects """
    def __init__(self):
        super().__init__()

    def create_define_objects(self, template, define_objects, lang, acrf):
        """
        parse the DDS template and create condition objects for use by WhereClauseDef generation
        :param template: content from the define-template
        :param define_objects: dictionary of odmlib define_objects updated by this method
        :param lang: xml:lang setting for TranslatedText
        :param acrf: part of the common interface but not used by this class
        """
        self.lang = lang
        conditions = []
        # store the conditions in define_objects for use when generating WhereClauseDef
        for condition in template:
            rc = self._create_condition(condition)
            conditions.append({rc["OID"]: rc})
        # store in define_objects with underscore prefix to indicate internal use
        define_objects["_conditions"] = conditions

    @staticmethod
    def _create_condition(condition):
        condition_obj = {"OID": condition["OID"]}
        range_checks = []
        for rc in condition["rangeChecks"]:
            rc_attr = {"SoftHard": "Soft", "ItemOID": rc["item"], "Comparator": rc["comparator"]}
            check_values = []
            for value in rc["checkValues"]:
                check_values.append(value)
            rc_attr["CheckValue"] = check_values
            range_checks.append(rc_attr)
        condition_obj["RangeCheck"] = range_checks
        return condition_obj

    def _create_rangecheck(self, wc, dataset):
        """
        use the values from the conditions section of the DDS JSON to create a RangeCheck odmlib template
        :param wc: WhereClause dictionary from the DDS JSON
        :param dataset: dataset name
        :return: a RangeCheck odmlib template
        """
        item_oid = self.generate_oid(["IT", dataset, wc["Variable"]])
        rc_attr = {"SoftHard": "Soft", "ItemOID": item_oid, "Comparator": wc["Comparator"]}
        rc = DEFINE.RangeCheck(**rc_attr)
        for value in wc["Values"]:
            cv = DEFINE.CheckValue(_content=value)
            rc.CheckValue.append(cv)
        return rc
