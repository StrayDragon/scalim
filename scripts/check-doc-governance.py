# ruff: noqa: T201
from __future__ import annotations

import sys
from pathlib import Path

from scalim_misc.yaml_dsl_cli_snippet_governance import check_yaml_dsl_cli_snippet_governance


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _check_claude_redirect(root: Path) -> list[str]:
    claude = root / "CLAUDE.md"
    agents = root / "AGENTS.md"
    if not claude.exists():
        return ["missing file: {}".format(claude)]
    if not agents.exists():
        return ["missing file: {}".format(agents)]

    if claude.is_symlink():
        # 论坛取证: CLAUDE.md 不能依赖软链接(部分平台/打包产物不生效),
        # 因此治理规则只接受 “单行 @ 重定向” 作为 SSOT 入口.
        return ["`CLAUDE.md` MUST be a regular file containing a single-line '@AGENTS.md' redirect (symlink is not supported)."]

    # 约定: 文件内容必须严格为 `@AGENTS.md`(忽略首尾空白).
    redirect = _read_text(claude).strip()
    if redirect == "@AGENTS.md":
        return []
    return ["`CLAUDE.md` MUST contain a single-line '@AGENTS.md' redirect."]


def _check_repo_guide_single_link(root: Path) -> list[str]:
    repo_guide = root / "docs" / "doc" / "dev" / "repo-guide.md"
    if not repo_guide.exists():
        return ["missing file: {}".format(repo_guide)]

    text = _read_text(repo_guide)
    if "repo:AGENTS.md" not in text:
        return ["`docs/doc/dev/repo-guide.md` MUST link to `AGENTS.md` via `repo:AGENTS.md`."]

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
    ssot_dir = root / "agentdev" / "skills" / "scalim-yaml-dsl" / "references" / "upgrades"

    if not docs_dir.exists():
        return ["missing directory: {}".format(docs_dir)]
    if not ssot_dir.exists():
        return ["missing directory: {}".format(ssot_dir)]

    index_md = docs_dir / "index.md"
    if not index_md.exists():
        errors.append("missing file: {}".format(index_md))
        return errors
    if index_md.is_symlink():
        errors.append("`{}` MUST be a regular file (zensical does not build symlinked markdown).".format(index_md))
        return errors

    unexpected = sorted(p.name for p in docs_dir.glob("*.md") if p.is_file() and p.name != "index.md")
    if unexpected:
        errors.append(
            "unexpected markdown files under {} (upgrades pages SSOT lives under skills; keep docs dir index-only):\n{}".format(
                docs_dir,
                "\n".join("- {}".format(name) for name in unexpected),
            )
        )

    text = _read_text(index_md)
    if "<!-- BEGIN AUTOGEN:yaml-dsl-upgrades-index -->" not in text or "<!-- END AUTOGEN:yaml-dsl-upgrades-index -->" not in text:
        errors.append("`{}` MUST include injected upgrades index block markers.".format(index_md))

    ssot_dir_rel = "agentdev/skills/scalim-yaml-dsl/references/upgrades/"
    if "repo:{}".format(ssot_dir_rel) not in text:
        errors.append("`{}` upgrades links MUST point to SSOT under `repo:{}`.".format(index_md, ssot_dir_rel))

    return errors


def main() -> int:
    root = _repo_root()
    errors: list[str] = []
    errors.extend(_check_claude_redirect(root))
    errors.extend(_check_repo_guide_single_link(root))
    errors.extend(_check_yaml_dsl_upgrades_ssot(root))
    errors.extend(check_yaml_dsl_cli_snippet_governance(root))

    if errors:
        sys.stderr.write("文档治理一致性检查失败:\n")
        for item in errors:
            sys.stderr.write("- {}\n".format(item))
        return 1

    sys.stdout.write("OK: 文档治理一致性检查通过.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
