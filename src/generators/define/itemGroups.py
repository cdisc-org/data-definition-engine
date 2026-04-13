from typing import Any
from odmlib.define_2_1 import model as DEFINE
import define_object
import itemRefs
import items
import valueLevel as VL
from constants import TRIAL_DESIGN_DOMAINS, NON_REPEATING_DOMAINS, DEFAULT_PURPOSE


class ItemGroups(define_object.DefineObject):
    """ create a Define-XML v2.1 ItemGroupDef element template """
    def __init__(self):
        super().__init__()

    def create_define_objects(
        self,
        template: list[dict[str, Any]],
        define_objects: dict[str, list[Any]],
        lang: str,
        acrf: str
    ) -> None:
        """
        Create ItemGroupDef objects from the DDS template.

        :param template: list of dataset definitions from the DDS JSON
        :param define_objects: dictionary of odmlib objects updated by this method
        :param lang: xml:lang setting for TranslatedText
        :param acrf: annotated case report form leaf ID
        """
        self.lang = lang
        for dataset in template:
            self._generate_dataset(dataset, define_objects, lang, acrf)
            if dataset.get("slices"):
                self._generate_vlm(dataset, define_objects, lang, acrf)


    def _generate_vlm(self, dataset, define_objects, lang, acrf):
        for slice in dataset["slices"]:
            if slice["type"] == "ValueList":
                vlm = VL.ValueLevel()
                vlm.create_define_objects(slice, define_objects, lang, acrf)

    def _generate_dataset(self, dataset, define_objects, lang, acrf):
        itg = self._create_itemgroupdef_object(dataset)
        define_objects["ItemGroupDef"].append(itg)
        dataset_name = dataset.get("name", "unknown")
        items_list = self.require_key(dataset, "items", f"ItemGroupDef {dataset_name}")
        # ItemRefs
        itemRefs.ItemRefs().create_define_objects(items_list, define_objects, lang, acrf, item_group=itg)
        # ItemDefs
        slices = dataset.get("slices")
        items.Items().create_define_objects(items_list, define_objects, lang, acrf, slice=slices)

        # TODO review this assumption that we have 1 class per dataset
        # assumption: 1 class per dataset - many need to expand this for ADaM
        if dataset.get("observationClass", {}).get("name", ""):
            ds_class = dataset["observationClass"]["name"].upper().replace("-", " ")
            itg.Class = DEFINE.Class(Name=ds_class)

        # TODO - where should we set the dataset file extension? (e.g., ndjson, xpt, etc.)
        leaf = DEFINE.leaf(ID="LF." + dataset_name, href=dataset_name.lower() + ".ndjson")
        leaf.title = DEFINE.title(_content=dataset_name.lower() + ".ndjson")
        itg.leaf = leaf

    def _create_itemgroupdef_object(self, obj):
        name = self.require_key(obj, "name", "ItemGroupDef")
        oid = self.generate_oid(["IG", name])
        attr = {"OID": oid, "Name": name, "Domain": name, "SASDatasetName": name}
        if obj.get("archiveLocationID"):
            attr["ArchiveLocationID"] = ".".join(["LF", obj["archiveLocationID"]])
        attr["Structure"] = obj.get("structure", "NA")
        # if obj.get("sasDatasetName"):
        #     attr["SASDatasetName"] = obj["sasDatasetName"]
        if "isReferenceData" in obj:
            attr["IsReferenceData"] = "Yes" if obj["isReferenceData"] else "No"
        attr["Repeating"] = self._generate_repeating_value(attr)
        attr["Purpose"] = self._resolve_purpose(obj)
        if obj.get("comment"):
            attr["CommentOID"] = obj["comment"]
        if "isNonStandard" in obj:
            attr["IsNonStandard"] = "Yes"
        if obj.get("standard"):
            attr["StandardOID"] = obj["standard"]
        if obj.get("hasNoData"):
            attr["HasNoData"] = obj["hasNoData"]
        igd = DEFINE.ItemGroupDef(**attr)
        description = self.require_key(obj, "description", f"ItemGroupDef {name}")
        tt = DEFINE.TranslatedText(_content=description, lang=self.lang)
        igd.Description = DEFINE.Description()
        igd.Description.TranslatedText.append(tt)
        return igd

    @staticmethod
    def _resolve_purpose(obj: dict[str, Any]) -> str:
        """
        Resolve the ItemGroupDef Purpose from the dataset definition.
        Prefers an explicit purpose, falls back to a standard-driven default
        (ADaM standards use Analysis; everything else uses Tabulation).
        """
        if obj.get("purpose"):
            return obj["purpose"]
        standard = (obj.get("standard") or "").upper()
        if "ADAM" in standard:
            return "Analysis"
        dataset_name = (obj.get("name") or "").upper()
        if dataset_name.startswith("AD"):
            return "Analysis"
        return DEFAULT_PURPOSE

    def _generate_repeating_value(self, attributes: dict[str, str]) -> str:
        """
        Determine if the dataset has repeating records.

        :param attributes: ItemGroupDef attributes dictionary
        :return: "Yes" if dataset has repeating records, "No" otherwise
        """
        if attributes.get("IsReferenceData") == "Yes":
            return "No"
        if attributes["Domain"] in NON_REPEATING_DOMAINS:
            # TODO check for presence of -PARMCD for DI/OI domains
            return "No"
        if attributes["Structure"] != "NA" and attributes["Structure"].count("per") == 1:
            return "No"
        return "Yes"
