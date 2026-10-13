"""Render a generated ODM CRF to HTML.

The ODM file always carries the SDTM annotations, so the blank CRF and the aCRF are the
same document transformed twice with a different ``displayAnnotations`` value.

The stylesheets themselves are milestone M6 and are not in this repo yet; until they
land, ``--html`` needs ``--stylesheet`` pointing at one. The transform runs under
saxonche (XSLT 2.0), matching the Phase 1 POCs.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

STYLESHEET_DIR = Path(__file__).parent / "stylesheets"
DEFAULT_STYLESHEET = {"1.3.2": "odm_1-3-2_crf.xsl", "2.0": "odm_2-0_crf.xsl"}

#: (filename suffix, displayAnnotations) for the two renderings.
RENDERINGS = (("_crf.html", 0), ("_acrf.html", 1))


def resolve_stylesheet(odm_version: str, stylesheet: str | None = None) -> Path:
    """Find the stylesheet for a version, or explain what is missing."""
    if stylesheet:
        path = Path(stylesheet)
        if not path.is_file():
            raise FileNotFoundError(f"stylesheet not found: {stylesheet}")
        return path
    path = STYLESHEET_DIR / DEFAULT_STYLESHEET[odm_version]
    if not path.is_file():
        raise FileNotFoundError(
            f"no bundled stylesheet for ODM {odm_version} yet (expected {path}). "
            "The CRF stylesheets are milestone M6; pass --stylesheet to use your own."
        )
    return path


def render_html(odm_file: str, out_dir: str, odm_version: str,
                stylesheet: str | None = None) -> list[Path]:
    """Render the blank CRF and the aCRF from one ODM file.

    :return: the paths written
    """
    try:
        from saxonche import PySaxonProcessor
    except ImportError as exc:
        raise RuntimeError(
            "rendering HTML needs saxonche (XSLT 2.0). Install it with "
            "`pip install saxonche`, or omit --html."
        ) from exc

    xsl = resolve_stylesheet(odm_version, stylesheet)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = Path(odm_file).stem
    written: list[Path] = []

    with PySaxonProcessor(license=False) as proc:
        logger.info("Saxon-HE version: %s", proc.version)
        xslt = proc.new_xslt30_processor()
        executable = xslt.compile_stylesheet(stylesheet_file=str(xsl))
        document = proc.parse_xml(xml_file_name=str(odm_file))
        for suffix, annotations in RENDERINGS:
            executable.set_parameter("displayAnnotations",
                                     proc.make_integer_value(annotations))
            target = out / f"{stem}{suffix}"
            executable.transform_to_file(output_file=str(target), xdm_node=document)
            written.append(target)
    return written
