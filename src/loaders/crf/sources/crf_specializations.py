"""Read CRF Specializations, the item-level source for CRF metadata.

No CDISC Library endpoint for CRF Specializations exists today (the COSMoS OpenAPI has
only Biomedical Concept and SDTM Dataset Specialization paths), so the draft CSV/XLSX
export is the source. :class:`CrfSpecializationSource` is the seam: when the Library
publishes the endpoint, :class:`LibraryCrfSpecializationSource` is filled in and the
change is a ``--crf_spec_source library`` config flip, not a code change.
"""
from __future__ import annotations

import csv
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

#: Columns that describe the group, repeated on every row of that group.
GROUP_COLUMNS = ("package_date", "bc_id", "vlm_group_id", "standard",
                 "standard_start_version", "standard_end_version", "domain",
                 "crf_group_id", "implementation_option", "scenario", "categories",
                 "short_name")

LIST_SEPARATOR = ";"


@dataclass
class CrfItem:
    """One row of the CRF specialization file: a single collected field."""

    crf_item: str
    variable_name: str = ""
    dec_id: str = ""
    question_text: str = ""
    prompt: str = ""
    completion_instructions: str = ""
    order_number: int = 0
    mandatory_variable: str = "N"
    data_type: str = "text"
    length: str = ""
    significant_digits: str = ""
    display_hidden: str = "N"
    derived_variable: str = "N"
    derivation_description: str = ""
    codelist: str = ""
    codelist_submission_value: str = ""
    value_list: list[str] = field(default_factory=list)
    value_display_list: list[str] = field(default_factory=list)
    selection_type: str = ""
    prepopulated_term: str = ""
    prepopulated_code: str = ""
    sdtm_target_variable: list[str] = field(default_factory=list)
    sdtm_annotation: str = ""
    sdtm_mapping: str = ""


@dataclass
class CrfGroup:
    """A CRF specialization group: the collected form of one Biomedical Concept."""

    crf_group_id: str
    bc_id: str = ""
    vlm_group_id: str = ""
    standard: str = ""
    standard_start_version: str = ""
    domain: str = ""
    implementation_option: str = ""
    scenario: str = ""
    short_name: str = ""
    package_date: str = ""
    categories: str = ""
    items: list[CrfItem] = field(default_factory=list)

    @property
    def is_normalized(self) -> bool:
        return (self.implementation_option or "").lower() == "normalized"


class CrfSpecializationSource(ABC):
    """Abstract source of CRF specialization groups."""

    @abstractmethod
    def groups(self) -> dict[str, CrfGroup]:
        """Return every group, keyed by ``crf_group_id``."""

    def index_by_bc(self) -> dict[str, list[CrfGroup]]:
        """Group ids indexed by ``bc_id`` (the NCI C-code of the concept)."""
        index: dict[str, list[CrfGroup]] = {}
        for group in self.groups().values():
            if group.bc_id:
                index.setdefault(group.bc_id, []).append(group)
        return index

    def index_by_vlm(self) -> dict[str, list[CrfGroup]]:
        """Group ids indexed by ``vlm_group_id`` (the SDTM dataset specialization id)."""
        index: dict[str, list[CrfGroup]] = {}
        for group in self.groups().values():
            if group.vlm_group_id:
                index.setdefault(group.vlm_group_id, []).append(group)
        return index


class _RowSource(CrfSpecializationSource):
    """Shared row-to-group assembly for the file-backed sources."""

    def __init__(self) -> None:
        self._groups: dict[str, CrfGroup] | None = None

    @abstractmethod
    def _rows(self) -> Iterable[dict[str, Any]]:
        """Yield raw rows as dicts keyed by column name."""

    def groups(self) -> dict[str, CrfGroup]:
        if self._groups is None:
            self._groups = self._build()
        return self._groups

    def _build(self) -> dict[str, CrfGroup]:
        groups: dict[str, CrfGroup] = {}
        for row in self._rows():
            group_id = _text(row.get("crf_group_id"))
            if not group_id:
                continue
            group = groups.get(group_id)
            if group is None:
                group = CrfGroup(
                    crf_group_id=group_id,
                    bc_id=_text(row.get("bc_id")),
                    vlm_group_id=_text(row.get("vlm_group_id")),
                    standard=_text(row.get("standard")),
                    standard_start_version=_text(row.get("standard_start_version")),
                    domain=_text(row.get("domain")),
                    implementation_option=_text(row.get("implementation_option")),
                    scenario=_text(row.get("scenario")),
                    short_name=_text(row.get("short_name")),
                    package_date=_text(row.get("package_date")),
                    categories=_text(row.get("categories")),
                )
                groups[group_id] = group
            item_name = _text(row.get("crf_item"))
            if item_name:
                group.items.append(_to_item(row, item_name))

        for group in groups.values():
            group.items.sort(key=lambda i: (i.order_number, i.crf_item))
        logger.info("read %d CRF specialization groups", len(groups))
        return groups


def _to_item(row: dict[str, Any], item_name: str) -> CrfItem:
    return CrfItem(
        crf_item=item_name,
        variable_name=_text(row.get("variable_name")),
        dec_id=_text(row.get("dec_id")),
        question_text=_text(row.get("question_text")),
        prompt=_text(row.get("prompt")),
        completion_instructions=_text(row.get("completion_instructions")),
        order_number=_int(row.get("order_number")),
        mandatory_variable=_text(row.get("mandatory_variable")) or "N",
        data_type=_text(row.get("data_type")) or "text",
        length=_text(row.get("length")),
        significant_digits=_text(row.get("significant_digits")),
        display_hidden=_text(row.get("display_hidden")) or "N",
        derived_variable=_text(row.get("derived_variable")) or "N",
        derivation_description=_text(row.get("derivation_description")),
        codelist=_text(row.get("codelist")),
        codelist_submission_value=_text(row.get("codelist_submission_value")),
        value_list=_split(row.get("value_list")),
        value_display_list=_split(row.get("value_display_list")),
        selection_type=_text(row.get("selection_type")),
        prepopulated_term=_text(row.get("prepopulated_term")),
        prepopulated_code=_text(row.get("prepopulated_code")),
        sdtm_target_variable=_split(row.get("sdtm_target_variable")),
        sdtm_annotation=_text(row.get("sdtm_annotation")),
        sdtm_mapping=_text(row.get("sdtm_mapping")),
    )


class CsvCrfSpecializationSource(_RowSource):
    """CRF specializations from the draft CSV export."""

    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self.path = Path(path)

    def _rows(self) -> Iterable[dict[str, Any]]:
        with open(self.path, "r", encoding="utf-8-sig", newline="") as f:
            yield from csv.DictReader(f)


class XlsxCrfSpecializationSource(_RowSource):
    """CRF specializations from the draft XLSX export (needs pandas + openpyxl)."""

    def __init__(self, path: str | Path, sheet: int | str = 0) -> None:
        super().__init__()
        self.path = Path(path)
        self.sheet = sheet

    def _rows(self) -> Iterable[dict[str, Any]]:
        try:
            import pandas as pd
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "reading .xlsx CRF specializations needs pandas and openpyxl; "
                "install them or use the .csv export"
            ) from exc
        frame = pd.read_excel(self.path, sheet_name=self.sheet, dtype=str).fillna("")
        yield from frame.to_dict(orient="records")


class LibraryCrfSpecializationSource(CrfSpecializationSource):
    """Placeholder for the CDISC Library CRF Specializations endpoint.

    The endpoint does not exist yet. This class marks where it will plug in so the
    swap stays a configuration change.
    """

    def __init__(self, client: Any, version: str | None = None) -> None:
        self.client = client
        self.version = version

    def groups(self) -> dict[str, CrfGroup]:
        raise NotImplementedError(
            "The CDISC Library has no CRF Specializations endpoint yet. Use "
            "--crf_spec_source csv (or xlsx) with the draft export in "
            "data/crf_specializations/."
        )


def open_source(path: str | Path | None, kind: str = "auto",
                client: Any = None) -> CrfSpecializationSource:
    """Build the right source for a path and ``--crf_spec_source`` value."""
    if kind == "library":
        return LibraryCrfSpecializationSource(client)
    if path is None:
        raise ValueError("--crf_spec_file is required unless --crf_spec_source library")
    suffix = Path(path).suffix.lower()
    if kind == "csv" or (kind == "auto" and suffix == ".csv"):
        return CsvCrfSpecializationSource(path)
    if kind == "xlsx" or (kind == "auto" and suffix in (".xlsx", ".xlsm")):
        return XlsxCrfSpecializationSource(path)
    raise ValueError(f"cannot determine CRF specialization source type for {path}")


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _split(value: Any) -> list[str]:
    text = _text(value)
    if not text:
        return []
    return [part.strip() for part in text.split(LIST_SEPARATOR) if part.strip()]
