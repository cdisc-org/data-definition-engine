from typing import Any

from odmlib.define_2_1 import model as DEFINE
import define_object

# Define-XML 2.1 rule 209: MethodDef/@Type is Computation or Imputation.
DEFINE_METHOD_TYPES = ("Computation", "Imputation")
# DDS MethodType values mapped onto a Define-XML 2.1 type, with a warning.
MAPPED_METHOD_TYPES = {"Transformation": "Computation"}
# DDS MethodType values that belong to ADaM / ARS, not to a Define-XML MethodDef.
REFUSED_METHOD_TYPES = ("Analysis", "Display")

# define_objects key for the downgrade counts the generator summary reports.
DOWNGRADE_KEY = "_method_downgrades"


class Methods(define_object.DefineObject):
    """
    Create Define-XML v2.1 MethodDef elements from the DDS methods section.

    A DDS Method may carry ODM v2.0 content that Define-XML 2.1 cannot hold: a MethodSignature
    and FormalExpressions that reference an ExternalCodeLib instead of inline code. Those are
    dropped (downgraded) and counted in define_objects[DOWNGRADE_KEY].
    """
    def __init__(self):
        super().__init__()

    def create_define_objects(self, template, define_objects, lang, acrf):
        """
        parse the define-template dictionary and create a odmlib define_objects to return in the define_objects dictionary
        :param template: define-template dictionary metadata
        :param define_objects: dictionary of odmlib define_objects updated by this method
        :param lang: xml:lang setting for TranslatedText
        :param acrf: part of the common interface but not used by this class
        """
        self.lang = lang
        downgrades = define_objects.setdefault(DOWNGRADE_KEY, {"signatures": [], "externalCodeLibs": []})
        for method in template:
            method_oid = self.require_key(method, "OID", "MethodDef")
            if self.find_object(define_objects["MethodDef"], method_oid) is not None:
                continue
            item = self._create_methoddef_object(method, downgrades)
            define_objects["MethodDef"].append(item)
        if downgrades["signatures"] or downgrades["externalCodeLibs"]:
            self.logger.info(
                "Define-XML 2.1 downgrade: dropped %d MethodSignature(s) and %d ExternalCodeLib expression(s)",
                len(downgrades["signatures"]), len(downgrades["externalCodeLibs"]),
            )

    def _create_methoddef_object(self, method, downgrades=None):
        """
        use the values from the Methods section of the define-template to create a MethodDef odmlib ojbect
        :param method: Methods define-template dictionary section
        :param downgrades: counts of dropped ODM v2.0 content, updated by this method
        :return: a MethodDef odmlib template
        """
        if downgrades is None:
            downgrades = {"signatures": [], "externalCodeLibs": []}
        oid = method["OID"]
        name = self.require_key(method, "name", f"MethodDef {oid}")
        mtype = self._define_method_type(self.require_key(method, "type", f"MethodDef {oid}"), oid)
        methoddef = DEFINE.MethodDef(OID=oid, Name=name, Type=mtype)
        methoddef.Description = DEFINE.Description()
        for tt in self.translated_text(method.get("description", "")):
            methoddef.Description.TranslatedText.append(tt)

        if self._signature_has_content(method.get("signature")):
            downgrades["signatures"].append(oid)

        # The DDS shape: expressions[] (ODM v2.0 style, inline code or an ExternalCodeLib).
        for expr in method.get("expressions") or []:
            fe = self._formal_expression(expr, oid, downgrades)
            if fe is not None:
                methoddef.FormalExpression.append(fe)
        # The legacy flat shape: context + code beside the method.
        if not method.get("expressions") and method.get("context"):
            methoddef.FormalExpression.append(
                DEFINE.FormalExpression(Context=method["context"], _content=method.get("code", ""))
            )

        # The DDS shape: documents[] (DocumentReference with leafID and integer pages).
        for doc in method.get("documents") or []:
            dr = self.document_ref(doc) if isinstance(doc, dict) else None
            if dr is None:
                self.logger.warning(f"MethodDef {oid}: skipped a document reference without a leafID")
                continue
            methoddef.DocumentRef.append(dr)
        # The legacy flat shape: document (leaf ID) + pages beside the method.
        if not method.get("documents") and method.get("document"):
            self._add_document(method, methoddef)
        return methoddef

    def _define_method_type(self, mtype: str, oid: str) -> str:
        """
        The Define-XML 2.1 MethodDef/@Type for a DDS MethodType (rule 209).
        Transformation maps to Computation with a warning; Analysis, Display and anything
        else Define-XML 2.1 rejects raise a ValueError.
        """
        if mtype in DEFINE_METHOD_TYPES:
            return mtype
        if mtype in MAPPED_METHOD_TYPES:
            mapped = MAPPED_METHOD_TYPES[mtype]
            self.logger.warning(f"MethodDef {oid}: Type {mtype} written as {mapped} (Define-XML 2.1 rule 209)")
            return mapped
        if mtype in REFUSED_METHOD_TYPES:
            raise ValueError(
                f"MethodDef {oid}: Type '{mtype}' belongs to ADaM or ARS, not to a Define-XML 2.1 MethodDef "
                f"(rule 209 allows {' or '.join(DEFINE_METHOD_TYPES)})"
            )
        raise ValueError(
            f"MethodDef {oid}: Type '{mtype}' is not valid in Define-XML 2.1 "
            f"(rule 209 allows {' or '.join(DEFINE_METHOD_TYPES)})"
        )

    def _formal_expression(self, expr: dict[str, Any], oid: str, downgrades: dict[str, list[str]]) -> Any | None:
        """
        A Define-XML FormalExpression for one DDS FormalExpression, or None when it has no inline
        code. An ExternalCodeLib reference cannot be carried by Define-XML 2.1 and is dropped.
        """
        if expr.get("externalCodeLib"):
            downgrades["externalCodeLibs"].append(oid)
        code = expr.get("expression")
        if code is None:
            if not expr.get("externalCodeLib"):
                self.logger.warning(f"MethodDef {oid}: skipped a FormalExpression with no expression")
            return None
        context = self.require_key(expr, "context", f"FormalExpression of MethodDef {oid}")
        return DEFINE.FormalExpression(Context=context, _content=code)

    @staticmethod
    def _signature_has_content(signature: Any) -> bool:
        """True when a DDS MethodSignature names at least one parameter or return value."""
        return isinstance(signature, dict) and bool(signature.get("parameters") or signature.get("returnValues"))

    def _add_document(self, method, methoddef):
        """
        creates a DocumentRef from the legacy flat keys: document (leaf ID) and pages, either a
        string of named destinations or a list of integer pages
        :param method: Methods section in the define-template dictionary
        :param methoddef: odmlib MethodDef template that gets updated with a DocumentRef template
        """
        pages = method.get("pages")
        if isinstance(pages, list):
            methoddef.DocumentRef.append(self.document_ref({"leafID": method["document"], "pages": pages}))
            return
        dr = DEFINE.DocumentRef(leafID=method["document"])
        if pages:
            # Define-XML 2.1 rule 45: PDFPageRef/@Type is PhysicalRef or NamedDestination.
            dr.PDFPageRef.append(DEFINE.PDFPageRef(PageRefs=str(pages), Type="NamedDestination"))
        methoddef.DocumentRef.append(dr)
