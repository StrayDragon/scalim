import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Tuple

from scalim.ob.structured_logging import normalize_keys_to_full

_LOG_LEVEL_ERROR = 40
_MAX_JOINED_CHARS = 1024 * 1024
_MAX_BUFFER_LINES = 200


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser("log", help="Structured log utilities (JSONL)")
    _set_help_default(parser)
    log_subparsers = parser.add_subparsers(dest="log_command")

    fmt_parser = log_subparsers.add_parser("fmt", help="Render structured logs (human-friendly)")
    _add_input_arg(fmt_parser)
    _ = fmt_parser.add_argument("--max-fields", type=int, default=12, help="Max number of fields to show per record")
    _ = fmt_parser.add_argument("--max-value-chars", type=int, default=120, help="Max characters per value when rendering")
    fmt_parser.set_defaults(func=_run_fmt)

    summarize_parser = log_subparsers.add_parser("summarize", help="Summarize structured logs (llm-friendly)")
    _add_input_arg(summarize_parser)
    _ = summarize_parser.add_argument("--budget-chars", type=int, default=8000, help="Max characters in output")
    summarize_parser.set_defaults(func=_run_summarize)


def _set_help_default(parser: argparse.ArgumentParser) -> None:
    def _show_help(_args: argparse.Namespace) -> int:
        parser.print_help()
        return 2

    parser.set_defaults(func=_show_help)


def _add_input_arg(parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument(
        "input",
        nargs="?",
        default="-",
        type=str,
        help="Input JSONL or mixed log file. Use '-' for stdin.",
    )


def _iter_input_lines(path: str) -> Iterator[str]:
    if path == "-" or not path:
        for line in sys.stdin:
            yield line
        return
    with Path(path).open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            yield line


def _iter_json_objects(lines: Iterable[str]) -> Iterator[Dict[str, Any]]:
    """Best-effort JSON object scanner with multiline recovery.

    Strategy:
    - Ignore non-JSON lines.
    - When a line looks like a JSON object start, try parse; if fails, keep buffering until parse succeeds.
    """
    buf: List[str] = []
    for raw in lines:
        line = raw.rstrip("\n")
        if not buf:
            stripped = line.lstrip()
            if not stripped.startswith("{"):
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                buf.append(stripped)
                continue
            if isinstance(obj, dict):
                yield normalize_keys_to_full(obj)  # type: ignore[arg-type]
            continue

        buf.append(line)
        joined = "\n".join(buf)
        try:
            obj = json.loads(joined)
        except json.JSONDecodeError:
            if len(joined) > _MAX_JOINED_CHARS or len(buf) > _MAX_BUFFER_LINES:
                buf = []
            continue
        buf = []
        if isinstance(obj, dict):
            yield normalize_keys_to_full(obj)  # type: ignore[arg-type]


def _shorten(value: object, *, max_chars: int) -> str:
    text = str(value)
    if max_chars <= 0:
        return text
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def _format_kv(items: Dict[str, Any], *, max_fields: int, max_value_chars: int) -> str:
    parts: List[str] = []
    for key in sorted(items.keys()):
        if max_fields > 0 and len(parts) >= max_fields:
            parts.append("…")
            break
        val = items[key]
        if val is None:
            continue
        parts.append("{}={}".format(key, _shorten(val, max_chars=max_value_chars)))
    return ", ".join(parts)


def _format_human(record: Dict[str, Any], *, max_fields: int, max_value_chars: int) -> str:
    level = int(record.get("level") or 0)
    logger = str(record.get("logger") or "")
    kind = str(record.get("kind") or "")
    message = str(record.get("message") or "")

    ctx = record.get("context") or {}
    fields = record.get("fields") or {}
    err = record.get("error") or {}

    ctx_text = ""
    if isinstance(ctx, dict) and ctx:
        picked: Dict[str, Any] = {}
        for k in ("demand", "workflow_node_id", "run_id", "demand_path"):
            if k in ctx and ctx[k] not in (None, ""):
                picked[k] = ctx[k]
        if picked:
            ctx_text = " ctx({})".format(_format_kv(picked, max_fields=6, max_value_chars=max_value_chars))

    fields_text = ""
    if isinstance(fields, dict) and fields:
        fields_text = " {}".format(_format_kv(fields, max_fields=max_fields, max_value_chars=max_value_chars))

    err_text = ""
    if isinstance(err, dict) and err:
        err_text = " err({})".format(_format_kv(err, max_fields=6, max_value_chars=max_value_chars))

    head = kind or message or "<log>"
    if logger:
        head = "{} {}".format(logger, head)

    prefix = "ERROR " if level >= _LOG_LEVEL_ERROR else ""
    return "{}{}{}{}{}".format(prefix, head, ctx_text, fields_text, err_text).strip()


def _run_fmt(args: argparse.Namespace) -> int:
    path = str(getattr(args, "input", "-") or "-")
    max_fields = int(getattr(args, "max_fields", 12) or 12)
    max_value_chars = int(getattr(args, "max_value_chars", 120) or 120)
    for record in _iter_json_objects(_iter_input_lines(path)):
        sys.stdout.write(_format_human(record, max_fields=max_fields, max_value_chars=max_value_chars) + "\n")
    return 0


def _summarize_kinds(records: List[Dict[str, Any]]) -> List[Tuple[str, int]]:
    counts: Dict[str, int] = {}
    for r in records:
        kind = str(r.get("kind") or "")
        if not kind:
            continue
        counts[kind] = int(counts.get(kind, 0)) + 1
    return sorted(counts.items(), key=lambda kv: (-int(kv[1]), kv[0]))


def _run_summarize(args: argparse.Namespace) -> int:
    path = str(getattr(args, "input", "-") or "-")
    budget = int(getattr(args, "budget_chars", 8000) or 8000)
    records = list(_iter_json_objects(_iter_input_lines(path)))

    lines: List[str] = []
    lines.append("records={}".format(len(records)))

    for kind, count in _summarize_kinds(records)[:20]:
        lines.append("{}={}".format(kind, count))

    # best-effort: show last performance/relations summaries if present
    for want_kind in ("performance.summary", "performance.loader_breakdown", "relations.summary"):
        picked = None
        for r in reversed(records):
            if str(r.get("kind") or "") == want_kind:
                picked = r
                break
        if picked and isinstance(picked.get("fields"), dict):
            lines.append("{} {}".format(want_kind, _format_kv(picked["fields"], max_fields=12, max_value_chars=120)))  # type: ignore[index]

    text = "\n".join(lines)
    if budget > 0 and len(text) > budget:
        text = text[: max(0, budget - 1)] + "…"
    sys.stdout.write(text + "\n")
    return 0


__all__ = ("register",)
