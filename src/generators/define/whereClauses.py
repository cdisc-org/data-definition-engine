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
        range_checks = define_objects.get("_conditions", [])
        for wc_obj in template:
            wc_oid = self.require_key(wc_obj, "OID", "WhereClauseDef")
            if self.find_object(define_objects["WhereClauseDef"], wc_oid) is not None:
                continue
            wc = self._create_whereclausedef_object(wc_obj, range_checks)
            define_objects["WhereClauseDef"].append(wc)

    def _create_whereclausedef_object(self, wc_obj, range_checks):
        where_clause = DEFINE.WhereClauseDef(OID=wc_obj["OID"])
        for condition_oid in wc_obj.get("conditions", []):
            stashed_rc = self._get_range_checks(range_checks, condition_oid)
            if stashed_rc is None:
                raise ValueError(
                    f"WhereClauseDef {wc_obj['OID']} references unknown condition {condition_oid}"
                )
            cond = stashed_rc[condition_oid]
            for rc_obj in cond["RangeCheck"]:
                rc = DEFINE.RangeCheck(
                    SoftHard=rc_obj.get("SoftHard", "Soft"),
                    ItemOID=rc_obj["ItemOID"],
                    Comparator=rc_obj["Comparator"],
                )
                for value in rc_obj["CheckValue"]:
                    rc.CheckValue.append(DEFINE.CheckValue(_content=value))
                where_clause.RangeCheck.append(rc)
        return where_clause

    @staticmethod
    def _get_range_checks(range_checks, condition_oid):
        for rc in range_checks:
            oid = next(iter(rc.keys()))
            if oid == condition_oid:
                return rc
        return None
