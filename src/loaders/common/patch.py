"""Generic YAML refinement-file helpers shared by the DDE loaders.

The refinement (patch) file is the human-in-the-loop half of a loader run: the loader
writes every value it could not derive as ``__PLACEHOLDER__``, a person fills them in, and
``--apply_patch`` folds the answers back. The YAML is emitted as text lines rather than
via ``yaml.dump`` so the instructional comments survive a round trip — the same approach
``create_define_json.generate_patch_file`` takes.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PLACEHOLDER = "__PLACEHOLDER__"


def is_placeholder(value: Any) -> bool:
    """True when a value is the unfilled sentinel (or is empty)."""
    return value is None or value == PLACEHOLDER or value == ""


def load_patch(path: str | Path) -> dict[str, Any]:
    """Load a refinement YAML file. Returns ``{}`` for an empty file."""
    import yaml

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def apply_field_patches(obj: dict[str, Any], patch: dict[str, Any],
                        fields: tuple[str, ...]) -> list[str]:
    """Copy the named fields from ``patch`` onto ``obj``, skipping unfilled values.

    A value still set to ``__PLACEHOLDER__`` in the patch means the human has not answered
    yet, so it is never written back over the loader's own output.

    :return: names of the fields actually changed
    """
    changed = []
    for field in fields:
        if field not in patch:
            continue
        value = patch[field]
        if is_placeholder(value):
            continue
        if obj.get(field) != value:
            obj[field] = value
            changed.append(field)
    return changed


def yaml_scalar(value: Any) -> str:
    """Render a scalar for the hand-emitted YAML.

    A plain string is quoted whenever YAML would read it back as something other than
    that string. This is not a cosmetic concern: ``repeating: No`` round-trips to the
    boolean ``False`` under YAML 1.1 (the "Norway problem"), which then fails schema
    validation as a non-string. Rather than maintain a list of the reserved spellings,
    the rendered form is parsed back and quoted if it did not survive.
    """
    import yaml

    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)

    text = str(value)
    needs_quotes = (
        text == ""
        or text != text.strip()
        or any(c in text for c in ':#{}[],&*?|<>=!%@`"\'\n')
    )
    if not needs_quotes:
        try:
            needs_quotes = yaml.safe_load(text) != text
        except yaml.YAMLError:
            needs_quotes = True
    if needs_quotes:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'
    return text


def yaml_list(values: list[Any]) -> str:
    """Render a flow-style list for the hand-emitted YAML."""
    return "[" + ", ".join(yaml_scalar(v) for v in values) + "]"


def write_patch_file(path: str | Path, banner: list[str],
                     sections: list[tuple[str, list[str]]]) -> None:
    """Write a refinement YAML file from pre-rendered section line blocks.

    :param path: output path
    :param banner: comment lines for the file header (without the leading ``#``)
    :param sections: ``(section_name, lines)`` pairs; a section with no lines is written
        as an empty mapping so the key is still discoverable
    """
    lines: list[str] = [f"# {line}" if line else "#" for line in banner]
    lines.append("")
    for name, body in sections:
        if body:
            lines.append(f"{name}:")
            lines.extend(body)
        else:
            lines.append(f"{name}: {{}}")
        lines.append("")

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")
