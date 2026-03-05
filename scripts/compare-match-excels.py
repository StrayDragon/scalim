# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "openpyxl>=3.1.5",
#     "pandas>=2.3.3",
#     "rich>=13.7.0",
# ]
# ///
# ruff: noqa: T201
"""
`Excel` 文件对比工具 - 快速发现两个 `Excel` 文件的关键差异

基础用法:

```bash
uv run scripts/compare-match-excels.py a.xlsx b.xlsx
```

指定工作表:

```bash
uv run scripts/compare-match-excels.py a.xlsx b.xlsx --sheet Data
uv run scripts/compare-match-excels.py a.xlsx b.xlsx -s1 Sheet1 -s2 Raw
```

按关键列对齐行:

```bash
uv run scripts/compare-match-excels.py a.xlsx b.xlsx -k id,name
```

差异样本追加上下文:

```bash
uv run scripts/compare-match-excels.py a.xlsx b.xlsx -k id --context order_count_all,order_count_7_all
```

导出差异报告:

```bash
uv run scripts/compare-match-excels.py a.xlsx b.xlsx -o report.xlsx
```

组合使用:

```bash
uv run scripts/compare-match-excels.py a.xlsx b.xlsx -k id,name -n 20 -o report.xlsx
```
"""

import argparse
import difflib
import json
import numbers
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
LIST_FIELDS = {"true_name", "department_desc"}


def normalize_value(val: Any, column: Optional[str] = None) -> Any:
    if val is None or val is pd.NA:
        return None
    try:
        if pd.isna(val):
            return None
    except Exception:
        pass
    if not isinstance(val, str) and hasattr(val, "isoformat"):
        try:
            return val.isoformat(sep=" ", timespec="seconds")
        except TypeError:
            return val.isoformat()
    if isinstance(val, str):
        stripped = val.strip()
        if not stripped:
            return None
        if column in LIST_FIELDS:
            parts = [part.strip() for part in stripped.split(",") if part.strip()]
            parts.sort()
            return ",".join(parts) if parts else None
        return stripped
    return val


def format_display_value(val: Any) -> str:
    if val is None or val is pd.NA:
        return "∅"
    if hasattr(val, "isoformat"):
        try:
            return val.isoformat(sep=" ", timespec="seconds")
        except TypeError:
            return val.isoformat()
    return str(val)


def escape_invisibles(text: str) -> str:
    try:
        return text.encode("unicode_escape").decode("ascii")
    except Exception:
        return repr(text)


def is_number(val: Any) -> bool:
    return isinstance(val, numbers.Number) and not isinstance(val, bool)


def build_key_display(df: pd.DataFrame, key_cols: List[str], index: int) -> str:
    parts = []
    for kc in key_cols:
        val = normalize_value(df[kc].iloc[index], kc) if kc in df.columns else None
        parts.append("{}={}".format(kc, format_display_value(val)))
    return "; ".join(parts)


def build_cell_text(old_val: Any, new_val: Any, mode: str) -> "Text":
    from rich.text import Text

    if old_val is None and new_val is None:
        return Text(format_display_value(old_val), style="dim")

    if is_number(old_val) and is_number(new_val):
        if old_val == new_val:
            return Text(format_display_value(old_val), style="dim")
        style = "red" if mode == "old" else "green"
        return Text(format_display_value(old_val if mode == "old" else new_val), style=style)

    s_old = format_display_value(old_val)
    s_new = format_display_value(new_val)
    if s_old == s_new:
        n_old = normalize_value(old_val)
        n_new = normalize_value(new_val)
        if n_old != n_new:
            s_old = escape_invisibles(s_old)
            s_new = escape_invisibles(s_new)
        else:
            return Text(s_old, style="dim")

    matcher = difflib.SequenceMatcher(None, s_old, s_new)
    text = Text()
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            segment = s_old[i1:i2] if mode == "old" else s_new[j1:j2]
            text.append(segment, style="dim")
        elif tag == "delete":
            if mode == "old":
                text.append(s_old[i1:i2], style="red")
        elif tag == "insert":
            if mode == "new":
                text.append(s_new[j1:j2], style="green")
        elif tag == "replace":
            if mode == "old" and s_old[i1:i2]:
                text.append(s_old[i1:i2], style="red")
            if mode == "new" and s_new[j1:j2]:
                text.append(s_new[j1:j2], style="green")
    return text


def get_sheet_names(excel_path: Path) -> List[str]:
    xl = pd.ExcelFile(excel_path)
    return xl.sheet_names


def load_sheet(excel_path: Path, sheet: Optional[str] = None) -> Tuple[pd.DataFrame, str]:
    sheets = get_sheet_names(excel_path)
    if not sheets:
        raise ValueError(f"文件没有任何工作表: {excel_path}")
    target_sheet = sheet if sheet else sheets[0]
    if target_sheet not in sheets:
        raise ValueError(f"工作表 '{target_sheet}' 不存在于文件 {excel_path}, 可用工作表: {sheets}")
    df = pd.read_excel(excel_path, sheet_name=target_sheet)
    return df, target_sheet


def build_summary(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    sheet1: str,
    sheet2: str,
    file1: Path,
    file2: Path,
) -> Dict[str, Any]:
    cols1 = set(df1.columns)
    cols2 = set(df2.columns)
    common_cols = cols1 & cols2
    only_in_1 = cols1 - cols2
    only_in_2 = cols2 - cols1

    return {
        "file1": str(file1),
        "file2": str(file2),
        "sheet1": sheet1,
        "sheet2": sheet2,
        "rows1": len(df1),
        "rows2": len(df2),
        "cols1": len(df1.columns),
        "cols2": len(df2.columns),
        "common_cols": sorted(common_cols),
        "only_in_file1": sorted(only_in_1),
        "only_in_file2": sorted(only_in_2),
    }


def align_by_keys(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    key_cols: List[str],
) -> Tuple[pd.DataFrame, pd.DataFrame, List[Tuple], List[Tuple]]:
    def row_key(df: pd.DataFrame, cols: List[str]) -> List[Tuple]:
        return [tuple(normalize_value(row[c], c) for c in cols) for _, row in df.iterrows()]

    keys1 = row_key(df1, key_cols)
    keys2 = row_key(df2, key_cols)

    df1_tagged = df1.copy()
    df2_tagged = df2.copy()
    df1_tagged["_key"] = keys1
    df2_tagged["_key"] = keys2
    df1_tagged["_key_n"] = df1_tagged.groupby("_key").cumcount()
    df2_tagged["_key_n"] = df2_tagged.groupby("_key").cumcount()

    idx1 = df1_tagged.set_index(["_key", "_key_n"])
    idx2 = df2_tagged.set_index(["_key", "_key_n"])

    common_idx = idx1.index.intersection(idx2.index)
    only1 = [k for k in idx1.index.difference(idx2.index)]
    only2 = [k for k in idx2.index.difference(idx1.index)]

    aligned1 = idx1.loc[common_idx].reset_index(drop=True)
    aligned2 = idx2.loc[common_idx].reset_index(drop=True)

    for df in (aligned1, aligned2):
        df.drop(columns=["_key", "_key_n"], errors="ignore", inplace=True)

    return aligned1, aligned2, only1[:10], only2[:10]


def compare_columns(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    common_cols: List[str],
) -> Tuple[List[Dict[str, Any]], int]:
    n = min(len(df1), len(df2))
    results = []
    for col in common_cols:
        s1 = df1[col].iloc[:n]
        s2 = df2[col].iloc[:n]
        v1 = [normalize_value(v, col) for v in s1]
        v2 = [normalize_value(v, col) for v in s2]

        diffs = sum(a != b for a, b in zip(v1, v2))
        missing_in_2 = sum(a is not None and b is None for a, b in zip(v1, v2))
        missing_in_1 = sum(a is None and b is not None for a, b in zip(v1, v2))
        results.append(
            {
                "column": col,
                "diff_count": diffs,
                "missing_in_file2": missing_in_2,
                "missing_in_file1": missing_in_1,
            }
        )
    return sorted(results, key=lambda x: x["diff_count"], reverse=True), n


def sample_diffs(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    col: str,
    key_cols: Optional[List[str]],
    file1: Path,
    file2: Path,
    limit: int = 5,
    context_cols: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    n = min(len(df1), len(df2))
    samples = []
    file1_label = file1.name
    file2_label = file2.name
    for i in range(n):
        raw1 = df1[col].iloc[i]
        raw2 = df2[col].iloc[i]
        v1 = normalize_value(raw1, col)
        v2 = normalize_value(raw2, col)
        if v1 != v2:
            row = {"row": i}
            if key_cols:
                row["key"] = build_key_display(df1, key_cols, i)
            row[file1_label] = raw1
            row[file2_label] = raw2
            if context_cols:
                for ctx in context_cols:
                    ctx_val1 = df1[ctx].iloc[i] if ctx in df1.columns else None
                    ctx_val2 = df2[ctx].iloc[i] if ctx in df2.columns else None
                    row[f"context.{ctx}.file1"] = ctx_val1
                    row[f"context.{ctx}.file2"] = ctx_val2
            samples.append(row)
            if len(samples) >= limit:
                break
    return samples


def print_summary(summary: Dict[str, Any]) -> None:
    console.print()
    console.print(Panel.fit("[bold cyan]Excel 对比摘要[/bold cyan]"))

    table = Table(show_header=False, box=None)
    table.add_column("项目", style="dim")
    table.add_column("文件1", style="green")
    table.add_column("文件2", style="yellow")

    table.add_row("文件", Path(summary["file1"]).name, Path(summary["file2"]).name)
    table.add_row("Sheet", summary["sheet1"], summary["sheet2"])
    table.add_row("行数", str(summary["rows1"]), str(summary["rows2"]))
    table.add_row("列数", str(summary["cols1"]), str(summary["cols2"]))
    console.print(table)

    if summary["only_in_file1"]:
        console.print(f"\n[red]仅在文件1中的列:[/red] {', '.join(summary['only_in_file1'][:10])}")
    if summary["only_in_file2"]:
        console.print(f"\n[yellow]仅在文件2中的列:[/yellow] {', '.join(summary['only_in_file2'][:10])}")


def print_column_diffs(
    col_diffs: List[Dict[str, Any]],
    total_rows: int,
    file1: Path,
    file2: Path,
    top_n: int = 10,
) -> None:
    console.print()
    console.print(Panel.fit("[bold cyan]列差异统计 (Top {})[/bold cyan]".format(top_n)))

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("列名")
    table.add_column("差异行数", justify="right")
    table.add_column("差异/总行", justify="right")
    table.add_column(file2.name, justify="right")
    table.add_column(file1.name, justify="right")

    for item in col_diffs[:top_n]:
        diff_style = "red" if item["diff_count"] > 0 else "green"
        ratio_str = f"{item['diff_count']}/{total_rows}"
        table.add_row(
            item["column"],
            f"[{diff_style}]{item['diff_count']}[/{diff_style}]",
            ratio_str,
            str(item["missing_in_file2"]),
            str(item["missing_in_file1"]),
        )
    console.print(table)


def print_samples(
    col: str,
    samples: List[Dict[str, Any]],
    file1: Path,
    file2: Path,
    context_cols: Optional[List[str]] = None,
) -> None:
    if not samples:
        return
    console.print(f"\n[bold]'{col}' 差异样本:[/bold]")
    table = Table(show_header=True, header_style="bold")
    file1_label = file1.name
    file2_label = file2.name
    headers = ["row"]
    if any("key" in row for row in samples):
        headers.append("key")
    headers.extend([file1_label, file2_label])
    if context_cols:
        for ctx in context_cols:
            headers.append(f"{ctx} ({file1_label})")
            headers.append(f"{ctx} ({file2_label})")

    for key in headers:
        if key == "key":
            table.add_column(key, overflow="fold", max_width=80)
        elif key in (file1_label, file2_label):
            table.add_column(key, overflow="fold", max_width=40)
        elif context_cols and any(key.startswith(f"{ctx} (") for ctx in context_cols):
            table.add_column(key, overflow="fold", max_width=32)
        else:
            table.add_column(key)

    for row in samples:
        v1 = row.get(file1_label)
        v2 = row.get(file2_label)
        cells = []
        for key in headers:
            if key == "row":
                cells.append(str(row.get(key)))
            elif key == "key":
                cells.append(format_display_value(row.get(key)))
            elif key == file1_label:
                cells.append(build_cell_text(v1, v2, "old"))
            elif key == file2_label:
                cells.append(build_cell_text(v1, v2, "new"))
            elif context_cols and key.endswith(f"({file1_label})"):
                ctx = key[: -len(f" ({file1_label})")]
                ctx_val1 = row.get(f"context.{ctx}.file1")
                ctx_val2 = row.get(f"context.{ctx}.file2")
                cells.append(build_cell_text(ctx_val1, ctx_val2, "old"))
            elif context_cols and key.endswith(f"({file2_label})"):
                ctx = key[: -len(f" ({file2_label})")]
                ctx_val1 = row.get(f"context.{ctx}.file1")
                ctx_val2 = row.get(f"context.{ctx}.file2")
                cells.append(build_cell_text(ctx_val1, ctx_val2, "new"))
            else:
                cells.append(format_display_value(row.get(key)))
        table.add_row(*cells)
    console.print(table)


def export_report(
    output: Path,
    summary: Dict[str, Any],
    col_diffs: List[Dict[str, Any]],
    aligned_only1: List[Tuple],
    aligned_only2: List[Tuple],
    key_cols: Optional[List[str]],
) -> None:
    def extract_key_tuple(key_item: Tuple) -> Tuple:
        if isinstance(key_item, tuple) and len(key_item) == 2 and isinstance(key_item[0], tuple):
            return key_item[0]
        return key_item

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_df = pd.DataFrame(
            [
                {"项目": "文件1", "值": summary["file1"]},
                {"项目": "文件2", "值": summary["file2"]},
                {"项目": "Sheet1", "值": summary["sheet1"]},
                {"项目": "Sheet2", "值": summary["sheet2"]},
                {"项目": "行数(文件1)", "值": summary["rows1"]},
                {"项目": "行数(文件2)", "值": summary["rows2"]},
                {"项目": "列数(文件1)", "值": summary["cols1"]},
                {"项目": "列数(文件2)", "值": summary["cols2"]},
                {"项目": "仅文件1的列", "值": ", ".join(summary["only_in_file1"])},
                {"项目": "仅文件2的列", "值": ", ".join(summary["only_in_file2"])},
            ]
        )
        summary_df.to_excel(writer, sheet_name="摘要", index=False)

        diff_df = pd.DataFrame(col_diffs)
        diff_df.to_excel(writer, sheet_name="列差异", index=False)

        if key_cols and (aligned_only1 or aligned_only2):
            only1_data = [
                {f"key.{kc}": extract_key_tuple(k)[i] for i, kc in enumerate(key_cols)} | {"来源": "仅文件1"} for k in aligned_only1
            ]
            only2_data = [
                {f"key.{kc}": extract_key_tuple(k)[i] for i, kc in enumerate(key_cols)} | {"来源": "仅文件2"} for k in aligned_only2
            ]
            missing_df = pd.DataFrame(only1_data + only2_data)
            if not missing_df.empty:
                missing_df.to_excel(writer, sheet_name="缺失行", index=False)

    console.print(f"\n[green]✓ 报告已导出到: {output}[/green]")


def export_llm_report(
    output: Path,
    summary: Dict[str, Any],
    col_diffs: List[Dict[str, Any]],
    total_rows: int,
    top_diff_samples: Dict[str, List[Dict[str, Any]]],
    aligned_only1: List[Tuple],
    aligned_only2: List[Tuple],
    key_cols: Optional[List[str]],
) -> None:
    def extract_key_tuple(key_item: Tuple) -> Tuple:
        if isinstance(key_item, tuple) and len(key_item) == 2 and isinstance(key_item[0], tuple):
            return key_item[0]
        return key_item

    report = {
        "summary": {
            "file1": Path(summary["file1"]).name,
            "file2": Path(summary["file2"]).name,
            "sheet1": summary["sheet1"],
            "sheet2": summary["sheet2"],
            "rows": {"file1": summary["rows1"], "file2": summary["rows2"], "compared": total_rows},
            "cols": {"file1": summary["cols1"], "file2": summary["cols2"], "common": len(summary["common_cols"])},
            "cols_only_in_file1": summary["only_in_file1"][:20],
            "cols_only_in_file2": summary["only_in_file2"][:20],
        },
        "column_diffs": [
            {
                "column": d["column"],
                "diff_rows": d["diff_count"],
                "total_rows": total_rows,
                "file2_nulls": d["missing_in_file2"],
                "file1_nulls": d["missing_in_file1"],
            }
            for d in col_diffs[:20]
            if d["diff_count"] > 0
        ],
        "samples": top_diff_samples,
    }

    if key_cols and (aligned_only1 or aligned_only2):
        report["missing_rows"] = {
            "only_in_file1": [{kc: extract_key_tuple(k)[i] for i, kc in enumerate(key_cols)} for k in aligned_only1[:10]],
            "only_in_file2": [{kc: extract_key_tuple(k)[i] for i, kc in enumerate(key_cols)} for k in aligned_only2[:10]],
        }

    def serialize(obj: Any) -> Any:
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        if hasattr(obj, "item"):
            return obj.item()
        return str(obj)

    with open(output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=serialize)
    console.print(f"\n[green]✓ LLM 友好报告已导出到: {output}[/green]")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Excel 文件对比工具 - 快速发现两个 Excel 文件的关键差异",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基础对比
  %(prog)s a.xlsx b.xlsx                      # 对比第一个 sheet

  # 指定 Sheet
  %(prog)s a.xlsx b.xlsx --sheet Data         # 两个文件使用同名 sheet
  %(prog)s a.xlsx b.xlsx -s1 Sheet1 -s2 Raw   # 分别指定不同 sheet

  # 按关键列对齐行 (处理行数或顺序不同的情况)
  %(prog)s a.xlsx b.xlsx -k id,name           # 按 id,name 对齐后对比

  # 导出报告
  %(prog)s a.xlsx b.xlsx -o report.xlsx       # 导出详细差异报告 (Excel)
  %(prog)s a.xlsx b.xlsx --llm diff.json      # 导出 LLM 友好的 JSON 报告

  # 组合使用
  %(prog)s a.xlsx b.xlsx -k id -n 20 -o report.xlsx
""",
    )
    parser.add_argument("file1", type=Path, help="第一个 Excel 文件")
    parser.add_argument("file2", type=Path, help="第二个 Excel 文件")
    parser.add_argument("-s", "--sheet", type=str, help="两个文件使用相同的 sheet 名 (默认: 第一个 sheet)")
    parser.add_argument("-s1", "--sheet1", type=str, help="文件1的 sheet 名")
    parser.add_argument("-s2", "--sheet2", type=str, help="文件2的 sheet 名")
    parser.add_argument("-k", "--key-cols", type=str, help="用于对齐行的关键列 (逗号分隔)")
    parser.add_argument("--context", type=str, help="差异样本中追加的上下文字段 (逗号分隔)")
    parser.add_argument("-n", "--top", type=int, default=10, help="显示差异最多的前 N 列 (默认: 10)")
    parser.add_argument("--sample", type=int, default=5, help="每列显示的差异样本数 (默认: 5)")
    parser.add_argument("-o", "--output", type=Path, help="导出差异报告到 Excel 文件")
    parser.add_argument("--llm", type=Path, help="导出 LLM 友好的 JSON 报告")
    parser.add_argument("--list-sheets", action="store_true", help="仅列出两个文件的 sheet 名称")

    args = parser.parse_args()

    if not args.file1.exists():
        console.print(f"[red]错误: 文件不存在 {args.file1}[/red]")
        sys.exit(1)
    if not args.file2.exists():
        console.print(f"[red]错误: 文件不存在 {args.file2}[/red]")
        sys.exit(1)

    if args.list_sheets:
        console.print(f"\n[bold]{args.file1}[/bold] 的 sheets: {get_sheet_names(args.file1)}")
        console.print(f"[bold]{args.file2}[/bold] 的 sheets: {get_sheet_names(args.file2)}")
        sys.exit(0)

    sheet1 = args.sheet1 or args.sheet
    sheet2 = args.sheet2 or args.sheet

    console.print(f"[dim]加载 {args.file1}...[/dim]")
    df1, actual_sheet1 = load_sheet(args.file1, sheet1)
    console.print(f"[dim]加载 {args.file2}...[/dim]")
    df2, actual_sheet2 = load_sheet(args.file2, sheet2)
    orig_rows1, orig_rows2 = len(df1), len(df2)
    orig_cols1, orig_cols2 = len(df1.columns), len(df2.columns)
    if orig_rows1 != orig_rows2 or orig_cols1 != orig_cols2:
        console.print(
            "[yellow]检测到原始行数/列数不一致: rows {} vs {}, cols {} vs {}[/yellow]".format(
                orig_rows1,
                orig_rows2,
                orig_cols1,
                orig_cols2,
            )
        )

    def parse_cols(raw: Optional[str]) -> Optional[List[str]]:
        if not raw:
            return None
        cols = [c.strip() for c in raw.split(",") if c.strip()]
        return cols or None

    key_cols = parse_cols(args.key_cols)
    context_cols = parse_cols(args.context)
    only1, only2 = [], []
    if key_cols:
        missing = [c for c in key_cols if c not in df1.columns or c not in df2.columns]
        if missing:
            console.print(f"[red]错误: 关键列不存在于两个文件中: {missing}[/red]")
            sys.exit(1)
        df1, df2, only1, only2 = align_by_keys(df1, df2, key_cols)
        console.print(f"[dim]已按关键列 {key_cols} 对齐行[/dim]")
        if only1:
            console.print(f"[yellow]仅文件1有的行 (样本): {only1[:5]}[/yellow]")
        if only2:
            console.print(f"[yellow]仅文件2有的行 (样本): {only2[:5]}[/yellow]")

    summary = build_summary(df1, df2, actual_sheet1, actual_sheet2, args.file1, args.file2)
    print_summary(summary)

    common_cols = summary["common_cols"]
    if not common_cols:
        console.print("[red]没有共同的列可以对比[/red]")
        sys.exit(1)

    col_diffs, total_rows = compare_columns(df1, df2, common_cols)
    print_column_diffs(col_diffs, total_rows, args.file1, args.file2, args.top)

    top_diff_cols = [c["column"] for c in col_diffs if c["diff_count"] > 0]
    top_diff_samples: Dict[str, List[Dict[str, Any]]] = {}
    for col in top_diff_cols:
        samples = sample_diffs(df1, df2, col, key_cols, args.file1, args.file2, args.sample, context_cols)
        top_diff_samples[col] = samples
        print_samples(col, samples, args.file1, args.file2, context_cols)

    if args.output:
        export_report(args.output, summary, col_diffs, only1, only2, key_cols)

    if args.llm:
        export_llm_report(args.llm, summary, col_diffs, total_rows, top_diff_samples, only1, only2, key_cols)


if __name__ == "__main__":
    main()
