import define_object


class Conditions(define_object.DefineObject):
    """ cache DDS conditions for use by WhereClauses to build RangeCheck elements """
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
        for condition in template:
            rc = self._create_condition(condition)
            conditions.append({rc["OID"]: rc})
        define_objects["_conditions"] = conditions

    @staticmethod
    def _create_condition(condition):
        condition_obj = {"OID": condition["OID"]}
        range_checks = []
        for rc in condition["rangeChecks"]:
            rc_attr = {
                "SoftHard": rc.get("softHard", "Soft"),
                "ItemOID": rc["item"],
                "Comparator": rc["comparator"],
                "CheckValue": list(rc.get("checkValues", [])),
            }
            range_checks.append(rc_attr)
        condition_obj["RangeCheck"] = range_checks
        return condition_obj
