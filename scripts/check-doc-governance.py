# ruff: noqa: T201
from __future__ import annotations

import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _check_claude_symlink(root: Path) -> list[str]:
    claude = root / "CLAUDE.md"
    agents = root / "AGENTS.md"
    if not claude.exists():
        return ["missing file: {}".format(claude)]
    if not agents.exists():
        return ["missing file: {}".format(agents)]

    if not claude.is_symlink():
        return ["`CLAUDE.md` MUST be a symlink to `AGENTS.md` (got regular file)."]

    try:
        resolved = claude.resolve()
    except Exception as exc:  # pragma: no cover
        return ["failed to resolve `CLAUDE.md` symlink: {}".format(exc)]

    if resolved != agents.resolve():
        try:
            raw = claude.readlink()
        except Exception:  # pragma: no cover
            raw = None
        hint = " (readlink={!r})".format(str(raw)) if raw is not None else ""
        return ["`CLAUDE.md` MUST point to `AGENTS.md`{}.".format(hint)]

    return []


def _check_repo_guide_single_link(root: Path) -> list[str]:
    repo_guide = root / "docs" / "doc" / "dev" / "repo-guide.md"
    if not repo_guide.exists():
        return ["missing file: {}".format(repo_guide)]

    text = _read_text(repo_guide)
    if "#code=AGENTS.md" not in text:
        return ["`docs/doc/dev/repo-guide.md` MUST link to `AGENTS.md` via `#code=AGENTS.md`."]

    # 保持为“单链接入口页”,避免在 `docs-site` 内重复维护 `SSOT` 规则.
    if "## " in text:
        return ["`docs/doc/dev/repo-guide.md` MUST be a single-link page (no `##` sections)."]

    non_empty_lines = [line for line in text.splitlines() if line.strip()]
    if len(non_empty_lines) > 20:
        return ["`docs/doc/dev/repo-guide.md` is too long; keep it minimal and link to `AGENTS.md`."]

    return []


def _check_yaml_dsl_upgrades_ssot(root: Path) -> list[str]:
    errors: list[str] = []

    docs_dir = root / "docs" / "doc" / "yaml-dsl" / "upgrades"
    ssot_dir = root / "artifacts" / "skills" / "scalim-yaml-dsl" / "references" / "upgrades"

    if not docs_dir.exists():
        return ["missing directory: {}".format(docs_dir)]
    if not ssot_dir.exists():
        return ["missing directory: {}".format(ssot_dir)]

    ssot_files = sorted(p for p in ssot_dir.glob("*.md") if p.is_file())
    expected_docs_names = {"{}.gen.md".format(p.stem) for p in ssot_files}

    docs_files = sorted(p for p in docs_dir.glob("*.md") if p.exists())

    docs_names = {p.name for p in docs_files if p.name != "index.md"}

    missing_pages = sorted(expected_docs_names - docs_names)
    if missing_pages:
        errors.append(
            "missing docs pages under {}:\n{}".format(
                docs_dir,
                "\n".join("- {}".format(name) for name in missing_pages),
            )
        )

    unexpected = sorted(docs_names - expected_docs_names)
    if unexpected:
        errors.append(
            "unexpected markdown files under {} (expected generated copies from SSOT):\n{}".format(
                docs_dir,
                "\n".join("- {}".format(name) for name in unexpected),
            )
        )

    for name in sorted(expected_docs_names & docs_names):
        doc_path = docs_dir / name
        if doc_path.is_symlink():
            errors.append("`{}` MUST be a regular file (zensical does not build symlinked markdown).".format(doc_path))
            continue
        if not doc_path.is_file():
            errors.append("`{}` MUST be a file.".format(doc_path))

    return errors


def main() -> int:
    root = _repo_root()
    errors: list[str] = []
    errors.extend(_check_claude_symlink(root))
    errors.extend(_check_repo_guide_single_link(root))
    errors.extend(_check_yaml_dsl_upgrades_ssot(root))

    if errors:
        sys.stderr.write("文档治理一致性检查失败:\n")
        for item in errors:
            sys.stderr.write("- {}\n".format(item))
        return 1

    sys.stdout.write("OK: 文档治理一致性检查通过.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
