from odmlib.define_2_1 import model as DEFINE
import define_object


class WhereClauses(define_object.DefineObject):
    """ create a Define-XML v2.1 WhereClauseDef element objects """
    def __init__(self):
        super().__init__()

    def create_define_objects(self, template, define_objects, lang, acrf):
        """
        parse the DDS template and create WhereClauseDef odmlib objects
        :param template: content from the define-template
        :param define_objects: dictionary of odmlib define_objects updated by this method
        :param lang: xml:lang setting for TranslatedText
        :param acrf: part of the common interface but not used by this class
        """
        self.lang = lang
        # read conditions from define_objects (stored by conditions.py)
        range_checks = define_objects.get("_conditions", [])
        for wc_obj in template:
            wc = self._create_whereclausedef_object(wc_obj, range_checks)
            define_objects["WhereClauseDef"].append(wc)

    def _create_whereclausedef_object(self, wc_obj, range_checks):
        attr = {"OID": wc_obj["OID"]}
        where_clause = DEFINE.WhereClauseDef(**attr)
        for condition_oid in wc_obj["conditions"]:
            stashed_rc = self._get_range_checks(range_checks, condition_oid)
            cond = stashed_rc[condition_oid]
            rc_list = cond["RangeCheck"]
            for rc_obj in rc_list:
                rc_attr = {"SoftHard": "Soft", "ItemOID": rc_obj["ItemOID"], "Comparator": rc_obj["Comparator"]}
                rc = DEFINE.RangeCheck(**rc_attr)
                for value in rc_obj["CheckValue"]:
                    cv = DEFINE.CheckValue(_content=value)
                    rc.CheckValue.append(cv)
                where_clause.RangeCheck.append(rc)
        return where_clause

    @staticmethod
    def _get_range_checks(range_checks, condition_oid):
        for rc in range_checks:
            oid = list(rc.keys())[0]
            if oid == condition_oid:
                return rc
        return None