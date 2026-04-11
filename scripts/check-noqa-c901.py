import argparse
import io
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

_ALLOW_MARK = "pragma: allow-c901"
_ALLOW_FILE_MARK = "pragma: allow-c901-file"


@dataclass(frozen=True)
class _Hit:
    path: str
    line: int
    text: str


def _iter_py_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        rel = path.relative_to(root)
        if "vendor" in rel.parts:
            continue
        yield path


def _reason_after_marker(text: str, marker: str) -> str:
    if marker not in text:
        return ""
    tail = text.split(marker, 1)[1].strip()
    return tail


def _parse_allow_file_reason(source: str) -> str:
    allow_file_reason = ""
    in_header = True

    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            stripped = token.string.lstrip("#").strip()
            if in_header and _ALLOW_FILE_MARK in stripped:
                reason = _reason_after_marker(stripped, _ALLOW_FILE_MARK)
                if reason:
                    allow_file_reason = reason
            continue

        if token.type in (tokenize.NL, tokenize.NEWLINE, tokenize.ENDMARKER):
            continue
        if token.type == tokenize.STRING and int(token.start[0]) == 1:
            continue
        in_header = False

    return allow_file_reason


def _line_has_noqa_c901(line: str) -> bool:
    marker = "# noqa:"
    if marker not in line:
        return False
    tail = line.split(marker, 1)[1]
    codes_part = tail.split("#", 1)[0]
    codes = [c.strip() for c in codes_part.split(",") if c.strip()]
    return "C901" in codes


def _line_has_allow_c901_plan(line: str) -> bool:
    if _ALLOW_MARK not in line:
        return False
    reason = _reason_after_marker(line, _ALLOW_MARK)
    return "plan:" in reason


def scan_noqa_c901(repo_root: Path) -> List[_Hit]:
    root = repo_root / "src" / "scalim"
    hits: List[_Hit] = []
    for path in _iter_py_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            continue

        allow_file_reason = _parse_allow_file_reason(text)
        allow_file = bool(allow_file_reason and "plan:" in allow_file_reason)

        for lineno, line in enumerate(text.splitlines(), start=1):
            if not _line_has_noqa_c901(line):
                continue
            if allow_file:
                continue
            if _line_has_allow_c901_plan(line):
                continue
            hits.append(_Hit(path=str(path.relative_to(repo_root)), line=int(lineno), text=str(line).rstrip("\n")))

    hits.sort(key=lambda h: (h.path, h.line))
    return hits


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="检查: `# noqa: C901` 需携带可追踪的 `allow-c901` `plan` 标记.")
    p.add_argument("--check", action="store_true", help="发现违规时返回非 0 退出码.")
    args = p.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    hits = scan_noqa_c901(repo_root)

    if not args.check:
        print("`noqa` `C901` 扫描报告")
        print("")
        print("摘要: 总计={}".format(len(hits)))
        for hit in hits[:50]:
            print("  - {}:{}".format(hit.path, hit.line))
        if len(hits) > 50:
            print("  ... (还有 {} 条)".format(len(hits) - 50))
        print("")
        print("规则:")
        print("  - 行级: `# noqa: C901 ...  # pragma: allow-c901 plan: <ref>`")
        print("  - 文件级(注释区): `# pragma: allow-c901-file plan: <ref>`")
        return 0

    if hits:
        print("[错误] 发现未标注 `plan` 的 `# noqa: C901` 放行点:", file=sys.stderr)
        for hit in hits[:50]:
            print("  - {}:{}: {}".format(hit.path, hit.line, hit.text), file=sys.stderr)
        if len(hits) > 50:
            print("  ... (还有 {} 条)".format(len(hits) - 50), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
