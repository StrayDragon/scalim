# region imports

import unicodedata
from collections.abc import Callable
from typing import Any

from ..compact.typing_extensionsx import override

# endregion

TextAlign = str  # "left" | "center" | "right"


def _display_width(text: str) -> int:
    width = 0
    for char in text:
        if unicodedata.east_asian_width(char) in ("F", "W"):
            width += 2
        else:
            width += 1
    return width


def _pad_cell(text: str, width: int, align: TextAlign = "left") -> str:
    text_width = _display_width(text)
    padding = width - text_width
    if padding <= 0:
        return text
    if align == "center":
        left_pad = padding // 2
        right_pad = padding - left_pad
        return " " * left_pad + text + " " * right_pad
    if align == "right":
        return " " * padding + text
    return text + " " * padding


class Column:
    header: str
    min_width: int
    max_width: int
    align: TextAlign
    formatter: Callable[[Any], str] | None

    def __init__(
        self,
        header: str,
        *,
        min_width: int = 0,
        max_width: int = 50,
        align: TextAlign = "left",
        formatter: Callable[[Any], str] | None = None,
    ) -> None:
        self.header = header
        self.min_width = max(min_width, _display_width(header))
        self.max_width = max_width
        self.align = align
        self.formatter = formatter

    def format_value(self, value: Any) -> str:
        if self.formatter:
            return self.formatter(value)
        if value is None:
            return ""
        return str(value)


class Table:
    title: str | None
    columns: list[Column]
    rows: list[list[Any]]
    show_header: bool
    border_style: str  # "simple" | "box" | "none"
    _col_widths: list[int]

    def __init__(
        self,
        title: str | None = None,
        *,
        show_header: bool = True,
        border_style: str = "box",
    ) -> None:
        self.title = title
        self.columns = []
        self.rows = []
        self.show_header = show_header
        self.border_style = border_style
        self._col_widths = []

    def add_column(
        self,
        header: str,
        *,
        min_width: int = 0,
        max_width: int = 50,
        align: TextAlign = "left",
        formatter: Callable[[Any], str] | None = None,
    ) -> "Table":
        col = Column(
            header,
            min_width=min_width,
            max_width=max_width,
            align=align,
            formatter=formatter,
        )
        self.columns.append(col)
        return self

    def add_row(self, *values: Any) -> "Table":
        self.rows.append(list(values))
        return self

    def _compute_widths(self) -> None:
        self._col_widths = [col.min_width for col in self.columns]

        for col_idx, col in enumerate(self.columns):
            header_width = _display_width(col.header)
            if header_width > self._col_widths[col_idx]:
                self._col_widths[col_idx] = min(header_width, col.max_width)

        for row in self.rows:
            for col_idx, value in enumerate(row):
                if col_idx >= len(self.columns):
                    break
                col = self.columns[col_idx]
                cell_text = col.format_value(value)
                cell_width = _display_width(cell_text)
                if cell_width > self._col_widths[col_idx]:
                    self._col_widths[col_idx] = min(cell_width, col.max_width)

    def _truncate(self, text: str, width: int) -> str:
        if _display_width(text) <= width:
            return text
        if width <= 3:  # noqa: PLR2004
            return text[:width]
        result = ""
        current_width = 0
        for char in text:
            char_width = 2 if unicodedata.east_asian_width(char) in ("F", "W") else 1
            if current_width + char_width > width - 2:
                break
            result += char
            current_width += char_width
        return result + ".."

    def _render_box(self) -> str:  # noqa: C901
        self._compute_widths()
        lines: list[str] = []

        total_width = sum(self._col_widths) + len(self._col_widths) * 3 + 1

        if self.title:
            lines.append("┌" + "─" * (total_width - 2) + "┐")
            title_padded = _pad_cell(self.title, total_width - 4, "center")
            lines.append("│ " + title_padded + " │")
            lines.append("├" + "─" * (total_width - 2) + "┤")
        else:
            top_border = "┌"
            for i, w in enumerate(self._col_widths):
                top_border += "─" * (w + 2)
                if i < len(self._col_widths) - 1:
                    top_border += "┬"
            top_border += "┐"
            lines.append(top_border)

        if self.show_header:
            header_cells: list[str] = []
            for col_idx, col in enumerate(self.columns):
                w = self._col_widths[col_idx]
                cell = _pad_cell(self._truncate(col.header, w), w, col.align)
                header_cells.append(cell)
            lines.append("│ " + " │ ".join(header_cells) + " │")

            sep = "├"
            for i, w in enumerate(self._col_widths):
                sep += "─" * (w + 2)
                if i < len(self._col_widths) - 1:
                    sep += "┼"
            sep += "┤"
            lines.append(sep)

        for row in self.rows:
            row_cells: list[str] = []
            for col_idx, col in enumerate(self.columns):
                value = row[col_idx] if col_idx < len(row) else None
                w = self._col_widths[col_idx]
                cell_text = col.format_value(value)
                cell = _pad_cell(self._truncate(cell_text, w), w, col.align)
                row_cells.append(cell)
            lines.append("│ " + " │ ".join(row_cells) + " │")

        bottom_border = "└"
        for i, w in enumerate(self._col_widths):
            bottom_border += "─" * (w + 2)
            if i < len(self._col_widths) - 1:
                bottom_border += "┴"
        bottom_border += "┘"
        lines.append(bottom_border)

        return "\n".join(lines)

    def _render_simple(self) -> str:
        self._compute_widths()
        lines: list[str] = []

        if self.title:
            lines.append(self.title)
            lines.append("-" * _display_width(self.title))

        if self.show_header:
            header_cells: list[str] = []
            for col_idx, col in enumerate(self.columns):
                w = self._col_widths[col_idx]
                cell = _pad_cell(self._truncate(col.header, w), w, col.align)
                header_cells.append(cell)
            lines.append("  ".join(header_cells))
            lines.append("  ".join("-" * w for w in self._col_widths))

        for row in self.rows:
            row_cells: list[str] = []
            for col_idx, col in enumerate(self.columns):
                value = row[col_idx] if col_idx < len(row) else None
                w = self._col_widths[col_idx]
                cell_text = col.format_value(value)
                cell = _pad_cell(self._truncate(cell_text, w), w, col.align)
                row_cells.append(cell)
            lines.append("  ".join(row_cells))

        return "\n".join(lines)

    def _render_none(self) -> str:
        self._compute_widths()
        lines: list[str] = []

        if self.title:
            lines.append(self.title)

        if self.show_header:
            header_cells: list[str] = []
            for col_idx, col in enumerate(self.columns):
                w = self._col_widths[col_idx]
                cell = _pad_cell(self._truncate(col.header, w), w, col.align)
                header_cells.append(cell)
            lines.append(" ".join(header_cells))

        for row in self.rows:
            row_cells: list[str] = []
            for col_idx, col in enumerate(self.columns):
                value = row[col_idx] if col_idx < len(row) else None
                w = self._col_widths[col_idx]
                cell_text = col.format_value(value)
                cell = _pad_cell(self._truncate(cell_text, w), w, col.align)
                row_cells.append(cell)
            lines.append(" ".join(row_cells))

        return "\n".join(lines)

    def render(self) -> str:
        if self.border_style == "simple":
            return self._render_simple()
        if self.border_style == "none":
            return self._render_none()
        return self._render_box()

    @override
    def __str__(self) -> str:
        return self.render()


class Panel:
    title: str
    content: str
    width: int
    padding: int

    def __init__(
        self,
        content: str,
        *,
        title: str = "",
        width: int = 60,
        padding: int = 1,
    ) -> None:
        self.content = content
        self.title = title
        self.width = width
        self.padding = padding

    def render(self) -> str:
        lines: list[str] = []
        inner_width = self.width - 2

        lines.append("┌" + "─" * inner_width + "┐")

        if self.title:
            title_padded = _pad_cell(self.title, inner_width, "center")
            lines.append("│" + title_padded + "│")
            lines.append("├" + "─" * inner_width + "┤")

        pad = " " * self.padding
        for line in self.content.split("\n"):
            text_width = inner_width - self.padding * 2
            text_padded = _pad_cell(line, text_width, "left")
            lines.append("│" + pad + text_padded + pad + "│")

        lines.append("└" + "─" * inner_width + "┘")

        return "\n".join(lines)

    @override
    def __str__(self) -> str:
        return self.render()


__all__ = [
    "Column",
    "Panel",
    "Table",
]
