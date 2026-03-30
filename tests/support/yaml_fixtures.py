from textwrap import dedent, indent
from typing import Optional


def make_yaml_config(
    *,
    name: str,
    sources: str,
    fields: Optional[str] = None,
    description: Optional[str] = None,
    main_source: Optional[str] = None,
    relations: Optional[str] = None,
) -> str:
    header_lines = [f"name: {name}"]
    if description:
        header_lines.append(f"description: {description}")

    parts = ["\n".join(header_lines)]
    if main_source:
        parts.append("main_source:\n" + indent(dedent(main_source).strip(), "  "))
    if relations:
        parts.append("relations:\n" + indent(dedent(relations).strip(), "  "))
    parts.append("sources:\n" + indent(dedent(sources).strip(), "  "))
    if fields:
        parts.append("fields:\n" + indent(dedent(fields).strip(), "  "))

    return "\n\n".join(parts) + "\n"
