# ruff: noqa: T201
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


_TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
_CAPABILITY_TOKEN_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)+$")


@dataclass(frozen=True)
class _Change:
    change_id: str
    proposal_text: str
    keyword: str
    is_yaml: bool
    highlight: str
    has_breaking: bool
    breaking_instructions: Tuple[str, ...]
    example_priority: int


def _run_git(args: Sequence[str], *, cwd: Path) -> str:
    return subprocess.check_output(["git", *args], cwd=str(cwd), text=True)


def _try_run_git(args: Sequence[str], *, cwd: Path) -> Optional[str]:
    try:
        return _run_git(args, cwd=cwd)
    except subprocess.CalledProcessError:
        return None


def _parse_semver_tag(tag: str) -> Optional[Tuple[int, int, int]]:
    match = _TAG_RE.fullmatch(tag.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _list_semver_tags(root: Path) -> List[str]:
    out = _run_git(["tag", "--list", "v*.*.*"], cwd=root)
    tags: List[Tuple[Tuple[int, int, int], str]] = []
    for raw in out.splitlines():
        tag = raw.strip()
        if not tag:
            continue
        parsed = _parse_semver_tag(tag)
        if parsed is None:
            continue
        tags.append((parsed, tag))
    tags.sort(key=lambda x: x[0])
    return [t for _v, t in tags]


def _dirs_in_archive(tag: str, *, root: Path) -> Set[str]:
    out = _try_run_git(["ls-tree", "-d", "--name-only", tag, "openspec/changes/archive/"], cwd=root)
    if out is None:
        return set()

    dirs: Set[str] = set()
    prefix = "openspec/changes/archive/"
    for line in out.splitlines():
        path = line.strip()
        if not path:
            continue
        if path.startswith(prefix):
            path = path[len(prefix) :]
        dirs.add(path)
    return dirs


def _read_file_at_tag(tag: str, relpath: str, *, root: Path) -> Optional[str]:
    # 只读取文件快照；不读取 `patch/diff`。
    return _try_run_git(["show", "{}:{}".format(tag, relpath)], cwd=root)


def _extract_section_lines(text: str, heading: str) -> List[str]:
    lines = text.splitlines()
    start = None
    # 兼容标题带后缀的写法，例如：
    # - `## What Changes（推荐方案）`
    # - `## What Changes: ...`
    # - `## Capabilities（v2）`
    pattern = re.compile(r"^##\s+{}\s*(?:$|[（(：:])".format(re.escape(heading)))
    for i, line in enumerate(lines):
        if pattern.match(line.strip()):
            start = i + 1
            break
    if start is None:
        return []
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return lines[start:end]


def _extract_section_lines_any(text: str, headings: Sequence[str]) -> List[str]:
    for heading in headings:
        got = _extract_section_lines(text, heading)
        if got:
            return got
    return []


def _parse_top_level_bullet_blocks(lines: Iterable[str]) -> List[List[str]]:
    blocks: List[List[str]] = []
    current: Optional[List[str]] = None
    for raw in lines:
        line = raw.rstrip("\n")
        if line.startswith("- "):
            if current:
                blocks.append(current)
            current = [line[2:].strip()]
            continue
        if current is None:
            continue
        if line.startswith("  ") or line.startswith("\t"):
            stripped = line.strip()
            if stripped:
                current.append(stripped)
            continue
        # 把非空且非标题的行视为条目续行。
        stripped = line.strip()
        if stripped and not stripped.startswith("## "):
            current.append(stripped)

    if current:
        blocks.append(current)
    return blocks


def _clean_inline_markers(s: str) -> str:
    out = s.strip()
    out = re.sub(r"\s+", " ", out)
    out = re.sub(r"^-\s+", "", out)
    out = re.sub(r"^\*\*BREAKING\*\*:\s*", "", out, flags=re.I)
    out = re.sub(r"^\*\*BREAKING\*\*：\s*", "", out, flags=re.I)
    out = re.sub(r"^\*\*NON-BREAKING\*\*:\s*", "", out, flags=re.I)
    out = re.sub(r"^\*\*NON-BREAKING\*\*：\s*", "", out, flags=re.I)
    out = re.sub(r"^BREAKING:\s*", "", out, flags=re.I)
    out = re.sub(r"^BREAKING：\s*", "", out, flags=re.I)
    out = out.strip()
    return out


def _is_capability_token(tok: str) -> bool:
    t = tok.strip()
    lower = t.lower()
    if not t or " " in t:
        return False
    if "." in t or "$" in t or "[*]" in t:
        return False
    if not _CAPABILITY_TOKEN_RE.fullmatch(lower):
        return False
    # `OpenSpec` 的 `capability` 多为 `kebab-case`；避免把它们当成 `YAML` 编写面 `token`。
    if lower.startswith(("yaml-dsl-", "yaml-source-", "openspec-", "docs-", "output-", "lsp-", "frontend-", "cli-", "qa-")):
        return True
    return False


def _score_highlight(text: str) -> int:
    # 评分时也做一次轻量清洗，避免 `**BREAKING**:` 之类的标记影响规则（例如“移除/删除”检测）。
    raw = text
    s = _clean_inline_markers(text)
    lower = s.lower()
    raw_lower = raw.lower()
    score = 0
    if "non-goals" in lower or "non goals" in lower or "non-goal" in lower or "非目标" in s or "不做" in s or "明确不做" in s:
        score -= 50
    # `Highlights` 避免把 “不做的事/非目标” 当成主线变化（例如“**不引入**抽象层”）。
    if s.strip().startswith(("不引入", "不增加", "不在")):
        score -= 12

    if "新增" in s or ("引入" in s and "不引入" not in s) or "扩展" in s or ("增加" in s and "不增加" not in s) or "new" in lower:
        score += 3
    if "统一" in s or "收敛" in s or "单一" in s or "单入口" in s:
        score += 2
    # 对 `Highlights` 来说，“只写移除/删除”信息密度通常不如“引入/统一/收敛”的主线变化；
    # 破坏性细节留给 `Breaking / Upgrade` 段。
    if s.strip().startswith(("移除", "删除", "弃用", "废弃")):
        score -= 4
    # `Highlights` 避免挑到 `Non-goals`/约束口径（例如“不会改变/保持不变”），它们通常不是版本主线变化。
    if s.strip().startswith(("不改变", "不变", "保持不变", "不引入", "不增加", "不在")):
        score -= 6
    if "支持" in s:
        score += 1
    # `Highlights` 优先保留用户会“立刻感知”的破坏性变更；否则容易被“同步文档/示例”等条目抢走。
    if "BREAKING" in raw or "breaking" in raw_lower or "破坏性" in raw:
        score += 6
    # 作者可感知的 `authoring surface` 变化（尤其是“YAML 不再允许/不再支持”的语义），比纯 `API` 细节更适合进 `Highlights`。
    if ("不再允许" in s or "不再支持" in s or "不再允许声明" in s) and ("yaml" in lower or "YAML" in s):
        score += 4
    # 更偏向“作者/用户可感知”的说明，而不是内部实现口径。
    if "yaml" in lower or "YAML" in s:
        score += 1
    if "runtime" in lower or "编译" in s or "compile" in lower:
        score -= 1
    if "dataclass" in lower or "dataclasses" in lower or "数据类" in s:
        score += 2
    if "导入路径" in s or "_internal" in s or "modulenotfounderror" in lower or "内部实现" in s:
        score -= 3
    if "runoverrides" in lower or "overrides." in lower or "by_yaml runtime" in lower or "yaml_dsl runtime" in lower:
        score -= 2
    if "重构" in s or "refactor" in lower:
        score += 2
    if "工作流" in s or "workflow" in lower or "质量" in s or "qa" in lower:
        score += 2
    # `版本化输出/manifest/latest.json` 通常是用户立刻能感知的主线变化，优先上榜。
    if "版本化" in s or "manifest" in lower or "latest.json" in lower:
        score += 5
    if "保持" in s or "不变" in s or "non-breaking" in lower:
        score -= 1
    if "schema" in lower or "hover" in lower or "description" in lower or "markdowndescription" in lower or "编辑器" in s:
        score -= 2
    if "non-breaking" in lower:
        score -= 2
    if "不在本变更范围" in s or "后续" in s:
        score -= 1
    if "文档" in s or "docs" in lower:
        score += 1
    return score


def _extract_meta_topic(proposal_text: str) -> Optional[str]:
    for line in _extract_section_lines(proposal_text, "Meta"):
        match = re.search(r"-\s*Topic[:：]\s*(.+)$", line.strip())
        if match:
            topic = match.group(1).strip()
            if topic:
                return _clean_inline_markers(topic)
    return None


def _choose_highlight_from_proposal(proposal_text: str, change_id: str) -> str:
    what_changes_lines = _extract_section_lines_any(proposal_text, ["What Changes", "变更内容"])
    if what_changes_lines:
        return _choose_highlight(what_changes_lines)

    topic = _extract_meta_topic(proposal_text)
    if topic:
        return topic

    # 最后兜底：取正文中第一句非标题内容，避免输出“（无）”。
    for raw in proposal_text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        return _clean_inline_markers(stripped)
    return change_id


def _choose_highlight(what_changes_lines: List[str]) -> str:
    blocks = _parse_top_level_bullet_blocks(what_changes_lines)
    if not blocks:
        for line in what_changes_lines:
            stripped = line.strip()
            if stripped:
                return _clean_inline_markers(stripped)
        return "（无）"

    def _score_block(block: List[str]) -> Tuple[int, int]:
        blob = " ".join(block)
        head = block[0].strip()
        score = _score_highlight(blob)
        # 避免挑到 `- **BREAKING**：` 这种“只有标记没有信息量”的条目（清洗后会变成空串）。
        cleaned_head = _clean_inline_markers(head)
        if not cleaned_head:
            score -= 10_000
        if head.endswith(":") or head.endswith("："):
            score -= 2
        # 同分时偏向更靠前的条目。
        return score, -blocks.index(block)

    best = max(blocks, key=_score_block)
    head = _clean_inline_markers(best[0])
    if (head.endswith(":") or head.endswith("：")) and len(best) > 1:
        head = head.rstrip(":：").rstrip()
        tail = _clean_inline_markers(best[1])
        tail = re.sub(r"^-\s+", "", tail)
        if tail:
            tail = tail.rstrip("。")
            if "例如" in tail or "比如" in tail:
                return "{}（{}）".format(head, tail)
            return "{}（例如：{}）".format(head, tail)
    return head


def _extract_keyword(proposal_text: str, *, fallback_change_id: str) -> str:
    cap_lines = _extract_section_lines(proposal_text, "Capabilities")
    for line in cap_lines:
        match = re.search(r"-\s+`([^`]+)`\s*[:：]", line)
        if match:
            keyword = match.group(1).strip()
            if keyword:
                return keyword

    # 兜底：取 `YYYY-MM-DD-` 后的 1~2 个片段。
    rest = fallback_change_id
    if re.match(r"^\d{4}-\d{2}-\d{2}-", rest):
        rest = rest[11:]
    tokens = [t for t in rest.split("-") if t]
    if not tokens:
        return fallback_change_id
    if len(tokens) == 1:
        return tokens[0]
    return "{}-{}".format(tokens[0], tokens[1])


def _example_priority(change_id: str, proposal_text: str) -> int:
    cid = change_id.lower()
    if "versioned-outputs" in cid or "versioned_outputs" in cid:
        return 0
    if "normalize" in cid:
        return 1
    # `resources.books` / `workflow IO` 收敛：属于 `outputs/IO` 编写面的核心变化。
    if "books-resources" in cid or "io-books-resources" in cid:
        return 5
    # 字段级：`extract` / `value_cast` / 显式 `decimal` 等都归为同一档（`field-level authoring surface`）。
    if "value-cast" in cid or "value_cast" in cid or ("decimal" in cid and "value" in cid):
        return 2
    if "extract" in cid:
        # 避免误判类似 `extract-scalim-cli-to-package` 这种“动词 `extract`”（不是 `YAML DSL` 的 `extract:` 写法）。
        # 只在变更 ID 或提案正文里能看到明确的 `YAML` 编写面线索时，才把它当成“字段级 `extract`”主题。
        lower = proposal_text.lower()
        if ("yaml" in cid or "yaml-dsl" in cid or "dsl" in cid) or ("extract:" in lower) or ("`extract`" in proposal_text):
            return 2
    if (
        "template-vars" in cid
        or "template_vars" in cid
        or "inline-dynamic-params" in cid
        or "params-template" in cid
        or "init-vars" in cid
        or "init-var" in cid
        or "runtime-vars" in cid
    ):
        return 3
    # `imports`（YAML `$import`/`imports`/项目配置等编写面）
    if "imports" in cid or "import" in cid or "relative-import" in cid:
        return 4
    if "outputs" in cid or "aggregate" in cid or "derived-outputs" in cid:
        return 5
    if "output-fields-alias" in cid or "fields-alias" in cid:
        return 6
    if "comment-style" in cid:
        return 7
    # `workflow` 的 `authoring surface`（迁出/运行期边界收敛）属于 YAML 作者会立刻感知的变化，但优先级低于核心语法主题。
    if "workflow-options-runtime" in cid or ("workflow.options" in proposal_text and "workflow_runtime_options" in proposal_text):
        return 90
    # 回退：当 `change_id` 不带明确 `token` 时，用提案正文推断作者写法主题；避免错过 “YAML DSL 写法变化”
    # 但 ID 命名偏实现细节的变更（例如 `...-callable-precheck-fast-fail` / `...-lsp-sugar-support`）。
    lower = proposal_text.lower()
    if "normalize.call_by" in lower or re.search(r"\bnormalize\b", lower):
        return 1
    if re.search(r"(?<![a-z0-9_])extract(?![a-z0-9_])", lower) or "value_cast" in lower or "value-cast" in lower:
        return 2
    if (
        "$init_var" in proposal_text
        or "$runtime" in proposal_text
        or "template_vars" in lower
        or "template-vars" in lower
        or "{{" in proposal_text
    ):
        return 3
    if "imports" in lower or "$import" in proposal_text or "scalim://" in lower or "import_roots" in lower or "import-roots" in lower:
        return 4
    if "outputs" in lower or "aggregate" in lower or "group_by" in lower or "dedup_by" in lower:
        return 5
    if "output-fields-alias" in lower or "fields-alias" in lower:
        return 6
    if "comment" in lower or "注释" in proposal_text:
        return 7
    # `call_by`/`callable` 往往是用户要改写法的核心点（即便没有写进 `change_id`）。
    if "call_by" in lower or "callable" in lower:
        return 1
    return 99


_CALL_BY_TOKEN_RE = re.compile(r"`call_by:\s*\"([^\"]+)\"`")


def _extract_yaml_code_blocks(proposal_text: str) -> List[List[str]]:
    lines = proposal_text.splitlines()
    blocks: List[List[str]] = []
    in_block = False
    is_yaml = False
    current: List[str] = []

    fence_re = re.compile(r"^```(?:\s*([a-zA-Z0-9_-]+))?\s*$")
    for raw in lines:
        line = raw.rstrip("\n")
        if not in_block:
            match = fence_re.match(line.strip())
            if not match:
                continue
            lang = (match.group(1) or "").strip().lower()
            in_block = True
            is_yaml = lang in ("yaml", "yml")
            current = []
            continue

        if line.strip().startswith("```"):
            if is_yaml:
                # 去掉首尾空行，保持 `snippet` 更紧凑。
                while current and not current[0].strip():
                    current.pop(0)
                while current and not current[-1].strip():
                    current.pop()
                if current:
                    blocks.append(list(current))
            in_block = False
            is_yaml = False
            current = []
            continue

        if is_yaml:
            current.append(line)

    return blocks


def _render_workflow_demand_path_example(proposal_text: str) -> Optional[List[str]]:
    # 目标：当变更涉及工作流 `YAML` 的 `workflow.runs[*].demand`（例如 `LSP` `definition` 跳转支持）时，
    # 提供一个最小的“`demand` 路径写法”示例，并明确这是语义示意（避免被当成可直接运行配置）。
    lower = proposal_text.lower()
    if "workflow.runs[*].demand" not in lower and "workflow.runs[" not in lower:
        return None
    if "demand" not in lower:
        return None
    # 至少要在提案里出现过路径形态提示（避免对不相关变更硬塞示例）。
    if "@/..." not in proposal_text and "alias:/" not in lower and "path alias" not in lower and "path_alias" not in lower:
        return None

    return [
        "# 示例为提案语义示意（不保证可直接运行）",
        "# 重点：workflow.runs[*].demand 支持相对路径、@/... 与 ALIAS:/...（解析规则与 runtime 一致）",
        "workflow:",
        "  runs:",
        "    - id: daily",
        "      demand: ./demand/daily.yaml",
        "    - id: nightly",
        '      demand: "@/demand/nightly.yaml"',
        "    - id: adhoc",
        '      demand: "app:/demand/adhoc.yaml"',
    ]


def _render_workflow_runtime_options_migration_example(proposal_text: str) -> Optional[List[str]]:
    lower = proposal_text.lower()
    if "workflow_runtime_options" not in lower and "workflow.options" not in lower:
        return None
    # 目标：当变更涉及 `workflow` `YAML` 的 `workflow.options.*` 迁出 `YAML` 时，给一个最小“删掉旧字段”的示意，
    # 并明确运行期走 `workflow_runtime_options`。
    return [
        "# 示例为提案语义示意（不保证可直接运行）",
        "# 重点：workflow.options.* 已迁出 YAML；运行期改用 workflow_runtime_options",
        "workflow:",
        "  runs:",
        "    - id: extract",
        "      demand: ./demand/extract.yaml",
        "    - id: report",
        "      demand: ./demand/report.yaml",
        "      depends_on: [extract]",
        "  # ✅ YAML 只写 DAG/资源引用；并发/失败策略等在运行入口配置",
        "  # ❌ 不要再写 workflow.options.max_concurrency / failure_policy / ctx / cache_pool",
    ]


def _render_call_by_upgrade_example(proposal_text: str) -> Optional[List[str]]:
    # 目标：从提案里提炼出 “位置参数写法 -> 显式 `kwargs` 写法” 的最小示例（并明确这是语义示意）。
    forms = [m.group(1).strip() for m in _CALL_BY_TOKEN_RE.finditer(proposal_text)]
    if not forms:
        return None

    # 选一个同名函数的一对写法：`fn(x)` + `fn(x=x)`。
    # - `=` 作为关键字参数的稳定信号
    # - 仅基于提案文本，不做代码推断
    by_base: Dict[str, Dict[str, str]] = {}
    for raw in forms:
        val = raw.strip()
        match = re.match(r"^([^\s()]+)\((.*)\)$", val)
        if not match:
            continue
        base = match.group(1).strip()
        args = match.group(2)
        if not base:
            continue
        slot = "kw" if "=" in args else "pos"
        by_base.setdefault(base, {})[slot] = val

    chosen_old = None
    chosen_new = None
    for base in sorted(by_base.keys()):
        pair = by_base[base]
        if "pos" in pair and "kw" in pair:
            chosen_old = pair["pos"]
            chosen_new = pair["kw"]
            break

    if not chosen_old or not chosen_new:
        return None

    return [
        "# 示例为提案语义示意（不保证可直接运行）",
        "# 重点：call_by 参数绑定不匹配现在会在编译期 fail-fast",
        "sources:",
        "  demo:",
        "    normalize:",
        '      call_by: "{}"'.format(chosen_new),
        '      # 旧写法：call_by: "{}" 将直接失败'.format(chosen_old),
        "fields:",
        "  demo_field:",
        '    call_by: "{}"'.format(chosen_new),
    ]


def _render_example_snippet_for_change(change: _Change) -> Optional[List[str]]:
    # 优先：若提案正文自带 YAML 片段，则直接复用（更贴题、更“像人写的说明”）。
    # 约束：尽量把代码块控制在 10–20 行内（包含我们追加的 1 行“语义示意”注释）。
    if change.is_yaml:
        yaml_blocks = _extract_yaml_code_blocks(change.proposal_text)
        if yaml_blocks:
            # 选择最适合 `release notes` 的块：优先 9–19 行（加 1 行注释后变成 10–20）。
            scored_blocks: List[Tuple[int, int, int, List[str]]] = []
            for idx, block in enumerate(yaml_blocks):
                n = len(block)
                in_range = 1 if 9 <= n <= 19 else 0
                # 更短更易读；同分时用出现顺序保证稳定。
                scored_blocks.append((in_range, -n, -idx, block))
            best = max(scored_blocks)[-1]
            if 1 <= len(best) <= 19:
                return ["# 示例为提案语义示意（不保证可直接运行）", *best]

    # 优先：从提案正文里直接提炼（避免纯模板“看起来像对但不贴题”）。
    workflow_runtime = _render_workflow_runtime_options_migration_example(change.proposal_text)
    if workflow_runtime:
        return workflow_runtime
    demand = _render_workflow_demand_path_example(change.proposal_text)
    if demand:
        return demand
    call_by = _render_call_by_upgrade_example(change.proposal_text)
    if call_by:
        return call_by
    # 回退：用已知的主题模板。
    return _render_example_snippet(change.change_id, change.example_priority)


def _render_example_snippet(change_id: str, priority: int) -> Optional[List[str]]:
    cid = change_id.lower()
    if "schema-merge-key" in cid or "merge-key" in cid or "merge_key" in cid:
        return [
            "# 示例为提案语义示意（不保证可直接运行）",
            "# 重点：fields mapping 支持 YAML merge key `<<`（编辑器 schema 校验不再报错）",
            "common_fields: &common_fields",
            "  user_id: {extract: id}",
            "  name: {extract: profile.name}",
            "main_source:",
            "  fields:",
            "    <<: *common_fields",
            "    age: {extract: profile.age}",
            "outputs: []",
        ]
    if "versioned-outputs" in cid or "versioned_outputs" in cid:
        return [
            "# 示例为提案语义示意（不保证可直接运行）",
            "workflow:",
            "  resources:",
            "    files:",
            "      detail:",
            "        kind: csv_file",
            "        path: ./out/report   # 现在是输出 root 目录（不是最终文件路径）",
            "        # write_lock: true   # 旧字段已移除（请删除）",
            "# 产物位置：<root>/versions/<run_id>/files/detail.csv",
            "# 稳定入口：<root>/manifest/latest.json",
        ]
    if "import_roots" in cid or "import-roots" in cid:
        return [
            "# 示例为提案语义示意（不保证可直接运行）",
            "yaml_dsl:",
            "  import_roots:",
            "    - root: ./demand_fragments",
            "      alias: frags",
            "    - root: ./src",
            "      alias: app",
            "  # 旧字段 import_aliases / import_allowed_roots 已移除",
            "  # 未显式指定 allowed_yaml_roots 时默认由 import_roots 推导",
            "  # 调用侧仍可用 allowed_yaml_roots 覆写/收紧",
        ]
    if "on-none" in cid or "on_none" in cid:
        return [
            "# 示例为提案语义示意（不保证可直接运行）",
            "sources:",
            "  orders:",
            '    loader: {call_by: "mypkg.load_orders"}',
            "    normalize: {kind: index_by_key, key_field: order_id, on_none: skip}",
            "fields:",
            "  order_score:",
            "    from: sources.orders",
            "    lookup_key: order_id",
            "    extract: score",
        ]
    if "books-resources" in cid or "io-books-resources" in cid:
        return [
            "# 示例为提案语义示意（不保证可直接运行）",
            "resources:",
            "  books:",
            "    report: {kind: xlsx_file, path: {$init_var: out_xlsx}}",
            "outputs_defaults:",
            "  to: {book: report}",
            "outputs:",
            "  - id: orders",
            "    to: {sheet: orders}",
            "    fields: [order_id, amount]",
        ]
    if "value-cast" in cid or "value_cast" in cid or ("decimal" in cid and "value" in cid):
        return [
            "# 示例为提案语义示意（不保证可直接运行）",
            "# 重点：`value_cast: decimal` + compute 里可用 `Decimal(...)`",
            "main_source:",
            "  fields:",
            "    amount: {extract: pay.amount, value_cast: decimal}",
            "    fee: {extract: pay.fee, value_cast: decimal}",
            "    total: {compute: 'amount - fee + Decimal(\"0.1\")'}",
            "outputs:",
            "  - id: settlement",
            "    fields: [amount, fee, total]",
        ]
    if priority == 1:
        return [
            "# 示例为提案语义示意（不保证可直接运行）",
            "sources:",
            "  users:",
            '    loader: {call_by: ".loaders:load_users"}',
            "    normalize: {kind: index_by_key, key_field: user_id}",
            "    fields:",
            "      name: {extract: profile.name}",
            "      age: {extract: profile.age}",
            "outputs:",
            "  - id: users_sheet",
        ]
    if priority == 2:
        return [
            "# 示例为提案语义示意（不保证可直接运行）",
            "main_source:",
            "  fields:",
            "    order_id: {extract: id}",
            "    sku: {extract: items[1].sku}",
            "    raw_key: {extract: '[\"a.b\"]'}",
            "sources:",
            "  ref:",
            '    loader: {call_by: "..loaders:load_ref"}',
            "    fields: {value: {extract: data.value}}",
        ]
    if priority == 3:
        if "template-vars" in cid or "template_vars" in cid:
            return [
                "# 示例为提案语义示意（不保证可直接运行）",
                "# 仅在调用方显式传入 template_vars 时启用预编译",
                "main_source:",
                '  loader: {call_by: ".loaders:main"}',
                "  params:",
                '    start_date: "{{ start_date }}"',
                '    end_date: "{{ end_date }}"',
                "outputs:",
                "  - id: report",
                '    name: "report_{{ biz }}"',
            ]
        if "output" in cid and ("init-var" in cid or "init-vars" in cid):
            return [
                "# 示例为提案语义示意（不保证可直接运行）",
                "main_source:",
                '  loader: {call_by: ".loaders:main"}',
                "  fields: {order_id: {extract: id}, amount: {extract: amt}}",
                "outputs:",
                "  - id: report",
                "    container:",
                "      path: {$init_var: out_dir}",
                "    fields: [order_id, amount]",
                "  # init_vars[out_dir] 由调用方在 run/compile 时传入",
            ]
        if "init-var" in cid or "init-vars" in cid or "runtime-vars" in cid:
            return [
                "# 示例为提案语义示意（不保证可直接运行）",
                "sources:",
                "  api:",
                '    loader: {call_by: ".loaders:fetch"}',
                "    params:",
                "      token: {$init_var: api_token}",
                "      query:",
                "        ids: {$keys: {as: list}}",
                "outputs:",
                "  - id: api_sheet",
            ]
        return [
            "# 示例为提案语义示意（不保证可直接运行）",
            "sources:",
            "  api:",
            '    loader: {call_by: ".loaders:fetch"}',
            "    params:",
            "      query:",
            "        ids: {$keys: {as: set}}",
            "      rows_ctx: {$rows: {cache_mode: batch}}",
            "outputs:",
            "  - id: api_sheet",
        ]
    if priority == 4:
        if "yaml-import" in cid or ("yaml" in cid and "imports" in cid):
            return [
                "# 示例为提案语义示意（不保证可直接运行）",
                "imports:",
                "  shared: ./_shared/sources.yaml",
                "  common: ../common/fragments.yaml",
                "  local: x/y.yaml",
                "# 解析基准：当前 YAML 文件所在目录",
                "# 仍拒绝：绝对路径 / 任意 URI scheme / 预留 alias 前缀",
                "main_source:",
                "  $import: shared.main_source",
                "outputs: []",
            ]
        return [
            "# 示例为提案语义示意（不保证可直接运行）",
            "sources:",
            "  orders:",
            '    loader: {call_by: ".loaders:load_orders"}',
            "  ref:",
            '    loader: {call_by: "..common.transforms:fixup"}',
            "main_source:",
            '  loader: {call_by: ".loaders:main"}',
            "outputs:",
            "  - id: orders_sheet",
        ]
    if priority == 5:
        return [
            "# 示例为提案语义示意（不保证可直接运行）",
            "outputs:",
            "  - id: summary",
            "    aggregate:",
            "      group_by: [shop_id]",
            "      fields:",
            "        order_cnt: {count: {}}",
            "        shop_rank:",
            "          dense_rank: {order_by: [{field: order_cnt, desc: true}]}",
            '      where: {eq: [status, "PAID"]}',
        ]
    if priority == 6:
        return [
            "# 示例为提案语义示意（不保证可直接运行）",
            "main_source:",
            "  fields:",
            "    quantity: &quantity {extract: qty}",
            "outputs:",
            "  - id: detail",
            "    fields:",
            "      - *quantity",
            "      - price",
            "      - amount",
            "  - id: summary",
        ]
    if priority == 7:
        return [
            "# 示例为提案语义示意（不保证可直接运行）",
            "# 仅展示注释/文档风格变化，不代表完整配置",
            "main_source:",
            "  # 这里描述该 source 的意图，而不是写在字段旁边",
            '  loader: {call_by: ".loaders:main"}',
            "  fields:",
            "    order_id: {extract: id}  # 只保留必要的行内注释",
            "outputs:",
            "  - id: sheet",
            "    fields: [order_id]",
        ]
    return None


def _extract_breaking_instructions(proposal_text: str, change_id: str) -> List[str]:
    all_lines = proposal_text.splitlines()

    def _tok_is_surface(tok: str) -> bool:
        t = tok.strip()
        lower = t.lower()
        # 兼容把 YAML 对写进反引号的写法：`call_by: "fn(x)"` / `fields.*.source: xxx`。
        # 只取 `key` 部分做“编写面 `token`”判定，避免因为包含 `value` 导致漏判。
        key_match = re.match(r"^([a-zA-Z0-9_.$\-\[\]*]+)\s*:", t)
        from_key_match = key_match is not None
        if from_key_match:
            t = key_match.group(1).strip()
            lower = t.lower()
        # 明确过滤掉“代码符号/签名”，避免把 `refactor` 里的内部函数名当成 YAML 编写面。
        if t.startswith("_"):
            return False
        if "->" in t or "(" in t or ")" in t:
            return False
        # `scalim.yaml` 的项目配置键路径（`yaml_dsl.*`）也是作者可感知的编写面。
        if "yaml_dsl." in lower:
            return True
        if _is_capability_token(t):
            return False
        # 过滤文件路径/源码文件/生成物路径等非 `YAML` 编写面 `token`。
        if "/" in t or "\\" in t:
            return False
        if re.search(r"\.(py|ts|md|json|yaml|yml)$", lower):
            return False
        # `RunOverrides.outputs_defaults` / `Decimal` 这类更像 `API`/类型名，不是 `YAML` 键路径。
        if t and t[0].isupper() and "[*]" not in t and "$" not in t:
            return False
        # `overrides.*` 是运行期 `Python` 入口的覆写，不是作者写在 `YAML` 里的主线编写面。
        if lower.startswith("overrides.") or lower.startswith("runoverrides"):
            return False
        if "[*]" in t or "$" in t:
            return True
        # 常见的 `YAML` 键（`snake_case`）也属于编写面 `token`。
        # - 仅在明确出现 `key:` 的反引号片段里才放行通用 `snake_case`（避免把 Python API 参数/变量名误判为 YAML）。
        # - 少量高频 `YAML` 键允许以“裸 `token`”出现（例如提案里写成 `write_lock`）。
        if t == "write_lock":
            return True
        if from_key_match and "_" in t and re.fullmatch(r"[a-z_][a-z0-9_]*", t):
            return True
        if any(
            k in lower
            for k in (
                "yaml-dsl",
                "write_to",
                "writes",
                "imports",
                "$import",
                "$ctx",
                "$runtime",
                "outputs",
                "fields",
                "resources",
                "aggregate",
                "group_by",
                "dedup_by",
                "value_cast",
                "value-cast",
                "observability",
                "guardrails",
                "retry",
                "template_vars",
                "template-vars",
                "yaml-dsl validate",
                "--",
            )
        ):
            return True
        if "." in t and any(k in lower for k in ("workflow", "demand", "outputs", "fields", "resources")):
            return True
        return False

    def _is_breaking_candidate(s: str) -> bool:
        text = s.strip()
        if not text:
            return False
        lower = text.lower()
        has_non_breaking_marker = re.search(r"\bnon[- ]breaking\b", lower) is not None
        tokens = re.findall(r"`([^`]+)`", text)
        workflow_authoring_hint = "workflow yaml" in lower or "workflow yml" in lower or "workflow 配置" in text
        demand_authoring_hint = "demand yaml" in lower or "demand yml" in lower
        has_surface_token = (
            any(_tok_is_surface(tok) for tok in tokens)
            or "workflow." in text
            or "yaml-dsl" in lower
            or workflow_authoring_hint
            or demand_authoring_hint
        )
        has_user_facing_hint = (
            "用户" in text and ("需要" in text or "应" in text or "改为" in text or "改成" in text or "迁移" in text)
        ) or ("旧写法" in text or "旧语法" in text or "旧字段" in text or "不再支持" in text or "不兼容" in text)

        # 明确不是 `breaking` 的常见表述：避免“为了避免 `breaking`”之类的句子误入。
        if ("避免" in text or "保持" in text) and ("breaking" in lower or "不兼容" in text):
            if "不再支持" not in text and "移除" not in text and "删除" not in text:
                return False

        # 明确 `BREAKING`：即便不包含 `YAML authoring surface token`，也应该进入升级提示（例如输出格式/指纹变化）。
        if (not has_non_breaking_marker) and re.search(r"\bbreaking\b", lower):
            return True
        if "破坏性" in text or "不兼容" in text or "不再支持" in text:
            return True

        # “输出约束：移除 ...” 这类描述是输出格式约束，不是 `upgrade` 点。
        if "输出约束" in text and ("移除" in text or "删除" in text):
            return False

        # 没有任何“用户可感知线索”的句子，通常不是“你要改什么”的 `upgrade` 点（避免 `refactor` 内部迁移误入）。
        if not (has_surface_token or has_user_facing_hint):
            return False

        # 触发词（严格依赖提案文本，不做代码推断）。
        if (not has_non_breaking_marker) and re.search(r"\bbreaking\b", lower):
            return True
        if "破坏性" in text or "不兼容" in text or "不再支持" in text:
            return True
        if "删除旧写法" in text:
            return True
        if ("移除" in text or "移出" in text or "迁出" in text or "删除" in text or "废弃" in text or "弃用" in text) and (
            has_surface_token
            or "旧写法" in text
            or "旧语法" in text
            or "旧字段" in text
            or "不再支持" in text
            or "不兼容" in text
            or "已移除" in text
            or "直接失败" in text
            or "fail-fast" in lower
            or "runtime" in lower
            or "write_to" in lower
        ):
            return True
        if "升级" in text or "迁移" in text or "migration" in lower or "migrate" in lower:
            return True
        if "schema" in lower and ("变更" in text or "更名" in text or "移除" in text or "删除" in text):
            return True
        if "authoring surface" in lower and (
            "变更" in text or "更名" in text or "移除" in text or "移出" in text or "迁出" in text or "删除" in text
        ):
            return True
        if "旧写法" in text and ("失败" in text or "fail-fast" in lower):
            return True
        if "直接失败" in text:
            return True
        # “旧写法不再自动解释/需要显式改写”也属于 `upgrade` 点（即使不出现“不再支持/迁移”等固定措辞）。
        if "不再" in text and ("自动" in text or "隐式" in text) and ("改写" in text or "改为" in text or "改成" in text or "显式" in text):
            return True
        if "用户应" in text and ("改写" in text or "改为" in text or "改成" in text):
            return True
        return False

    candidates: List[str] = []

    # 1) 顶层 `bullet blocks`（跨全文），适合抓“迁移/不兼容/删除旧写法”这类条目。
    for block in _parse_top_level_bullet_blocks(all_lines):
        blob = " ".join(block)
        if _is_breaking_candidate(blob):
            candidates.append(blob)

    # 2) 行级扫描：补齐段落里提到的迁移点（例如 `Why` 中的 “旧写法会直接失败”）。
    for raw in all_lines:
        stripped = raw.strip()
        if _is_breaking_candidate(stripped):
            candidates.append(stripped)

    instructions: List[str] = []
    for cand in candidates:
        cleaned = _clean_inline_markers(cand)
        if not cleaned:
            continue
        # 提案里明确标注 `BREAKING`（内部实现）的内容，通常不要求用户做迁移；避免挤占 `Breaking/Upgrade` 的版面。
        if "内部实现" in cleaned and ("BREAKING" in cleaned or "breaking" in cleaned.lower()):
            continue

        # === 高价值的“公共 API 收敛/重组”升级点（仍完全基于提案文本，不做代码推断） ===
        # 目标：把“`BREAKING` 但没有具体 `token`”的说明转成可执行的迁移指令，避免落到 `按提案升级` 兜底后被过滤掉。
        if ("RunOptions" in cleaned or "`RunOptions`" in cleaned) and ("扁平" in cleaned or "flat" in cleaned.lower()):
            instructions.append("把运行入口的 options-object 升级为分组结构；不要再依赖扁平 `RunOptions` 的公开字段集合。")
            continue
        if "options-object" in cleaned.lower() and ("拆分" in cleaned or "内聚" in cleaned or "收敛" in cleaned):
            instructions.append("把运行入口的 options-object 升级为分组结构（拆分并内聚 runtime knobs）。")
            continue
        if ("隐式" in cleaned or "implicit" in cleaned.lower()) and ("sink" in cleaned.lower() or "`sink`" in cleaned):
            if "tee" in cleaned.lower() or "镜像" in cleaned or "tee" in proposal_text.lower():
                instructions.append("不要再通过额外传 `sink` 触发隐式 tee；改用显式输出模式/捕获策略。")
                continue
        if "run_ir_fn" in cleaned or "compile_demand_yaml_fn" in cleaned:
            instructions.append("不要再用 `run_ir_fn` / `compile_demand_yaml_fn` 这类注入型参数（已移到 internal/test-only）。")
            continue
        if ("scalim.execution" in cleaned or "`scalim.execution`" in cleaned) and (
            "ExecutionRequest" in cleaned or "`ExecutionRequest`" in cleaned
        ):
            if "ScalimEngine" in proposal_text or "`ScalimEngine`" in proposal_text:
                instructions.append(
                    "执行层：把入口改为 `scalim.execution.run_ir` + `ExecutionRequest`/`ExecutionResult`；不要再把 `ScalimEngine` 当默认主入口。"
                )
            else:
                instructions.append("执行层：把入口改为 `scalim.execution.run_ir` + `ExecutionRequest`/`ExecutionResult`。")
            continue
        if ("scalim.sinks" in cleaned or "`scalim.sinks`" in cleaned) and (
            "pandas" in cleaned.lower() or "`scalim.sinks.pandas`" in cleaned
        ):
            instructions.append("把可选依赖 sinks 的导入改为从 `scalim.sinks.pandas` 等显式子模块进入（不要从 `scalim.sinks` 直接取）。")
            continue
        if "InMemoryRowDataSink" in cleaned or "`InMemoryRowDataSink`" in cleaned:
            if "get_data" in cleaned:
                instructions.append("把捕获 rows 的用法改为 `InMemoryRowDataSink.get_data() -> List[RowData]`。")
            else:
                instructions.append("把捕获 rows 的 sink 统一为 `scalim.sinks.memory.InMemoryRowDataSink`（返回 `List[RowData]`）。")
            continue
        if ("scalim.events" in cleaned or "`scalim.events`" in cleaned) and (
            "分组" in cleaned or "catalog" in cleaned.lower() or "namespace" in cleaned.lower()
        ):
            instructions.append("events：把事件常量的入口改为分组后的 catalog/namespace（不再依赖平铺常量名）。")
            continue
        if ("scalim.ob.Observability" in cleaned or "`scalim.ob.Observability`" in cleaned) and (
            "options" in cleaned.lower() or "强类型" in cleaned or "typed" in cleaned.lower()
        ):
            instructions.append("Observability：把策略字段迁移到强类型 options 对象（非法组合会 fail-fast）。")
            continue

        # === 工作流 `options` 迁出 `YAML`：合并成一条“你要改什么”的升级指令（避免刷屏） ===
        if ("workflow.options" in cleaned or "`workflow.options`" in cleaned) and (
            "不再允许" in cleaned or "不再支持" in cleaned or "fail-fast" in cleaned.lower() or "拒绝" in cleaned
        ):
            if "workflow_runtime_options" in proposal_text:
                instructions.append(
                    "把 workflow YAML 里的 `workflow.options.*` 从 YAML 迁移为运行入口 `workflow_runtime_options`（旧写法会 fail-fast）。"
                )
            else:
                instructions.append("把 workflow YAML 里的 `workflow.options.*` 删除（旧写法会 fail-fast）。")
            continue
        if "run_workflow" in cleaned and "workflow_runtime_options" in proposal_text:
            instructions.append("把 `run_workflow(...)` 的零散 workflow runtime 参数改为 `workflow_runtime_options`。")
            continue

        # === 高价值的“非 YAML 语法”升级点（仍完全基于提案文本，不做代码推断） ===
        # 1) `scalim-cli` 拆包：安装边界 + 导入路径会导致旧用法直接跑不起来。
        added_special = False
        if "`scalim-cli`" in cleaned and ("不再提供" in cleaned or "不再存在" in cleaned):
            instructions.append("把 `scalim-cli` 的安装从 `scalim` 改为安装 `scalim-cli`（Python >=3.10）。")
            added_special = True
        if "`scalim.cli`" in cleaned and ("不再存在" in cleaned or "不再提供" in cleaned):
            instructions.append("把 `scalim.cli` 的导入改为 `scalim_cli.*`（旧路径不再存在）。")
            added_special = True
        # 2) 可观测性输出从 `k=v` 切到 JSONL：旧解析器需要迁移。
        if ("`k=v`" in cleaned or "k=v" in cleaned) and ("JSONL" in cleaned or "jsonl" in cleaned.lower()):
            if "scalim-cli log" in proposal_text or "`scalim-cli log`" in proposal_text:
                instructions.append("把日志解析从 `k=v` 文本迁移到 JSONL；或直接用 `scalim-cli log` 渲染。")
            else:
                instructions.append("把日志解析从 `k=v` 文本迁移到 JSONL。")
            added_special = True

        if added_special:
            continue

        # `derived outputs meta fingerprint` 迁移：明确告诉用户“要改什么/要更新什么基线”，避免落到低信息量兜底项。
        fingerprint_hint = ("指纹" in cleaned) or ("fingerprint" in cleaned.lower())
        if fingerprint_hint and (
            ("40" in cleaned and "64" in cleaned) or ("sha1" in proposal_text.lower() and "sha256" in proposal_text.lower())
        ):
            if "sha1" in proposal_text.lower() and "sha256" in proposal_text.lower():
                instructions.append("更新依赖 meta 指纹的审计/对拍基线：算法已从 SHA-1 改为 SHA-256，指纹长度 40→64。")
            else:
                instructions.append("更新依赖 meta 指纹格式的审计/对拍基线（长度已变化）。")
            continue
        if fingerprint_hint and ("基线" in cleaned or "对拍" in cleaned or "snapshot" in cleaned.lower()):
            if "sha1" in proposal_text.lower() and "sha256" in proposal_text.lower():
                instructions.append("更新依赖 meta 指纹的审计/对拍基线：算法已从 SHA-1 改为 SHA-256，指纹长度 40→64。")
            else:
                instructions.append("更新依赖 meta 指纹格式的审计/对拍基线（长度已变化）。")
            continue

        # 版本化输出：最常见的升级点是“产物读取入口与路径语义变化”，这里直接抽成一条可执行指令。
        if (
            "最终产物路径" in cleaned
            and ("迁移" in cleaned or "改为" in cleaned or "改成" in cleaned)
            and ("latest" in cleaned.lower() or "manifest" in cleaned.lower() or "latest 指示" in cleaned)
        ):
            instructions.append("把产物读取入口改为 `manifest/latest.json`（或指定版本目录）；不要再依赖固定最终文件路径。")
            continue

        if ("输出 root" in cleaned or "root 目录" in cleaned) and ("path" in cleaned.lower() or "`path`" in cleaned):
            if ("books.*.path" in proposal_text or "resources.books" in proposal_text) and (
                "files.*.path" in proposal_text or "resources.files" in proposal_text
            ):
                instructions.append("把 `books.*.path` / `files.*.path`（以及 workflow 对应字段）改为输出 root 目录（不是最终文件路径）。")

        # `scalim.yaml` `imports` 单入口：优先输出一条“旧字段 -> 新字段”的升级指令，避免 `Breaking` 段刷屏。
        if (
            "yaml_dsl.import_roots" in proposal_text
            and ("yaml_dsl.import_aliases" in cleaned or "import_aliases" in cleaned)
            and ("yaml_dsl.import_allowed_roots" in cleaned or "import_allowed_roots" in cleaned)
            and ("移除" in cleaned or "删除" in cleaned or "弃用" in cleaned or "废弃" in cleaned)
        ):
            instructions.append("把 `yaml_dsl.import_aliases` / `yaml_dsl.import_allowed_roots` 迁移为 `yaml_dsl.import_roots`。")
            continue

        # `scalim.yaml yaml_dsl.runner` 移除：把“删除 YAML 配置 + CLI 不再执行”合并成一条升级指令。
        if "yaml_dsl.runner" in cleaned and ("移除" in cleaned or "删除" in cleaned or "已移除" in cleaned):
            if "scalim-cli yaml-dsl run" in proposal_text.lower() or "scalim-cli yaml-dsl workflow run" in proposal_text.lower():
                instructions.append(
                    "不要再用 `yaml_dsl.runner`；运行期策略改为 Python `RunOptions`，并且不再支持 `scalim-cli yaml-dsl run` / `scalim-cli yaml-dsl workflow run`。"
                )
            else:
                instructions.append("不要再用 `yaml_dsl.runner`；运行期策略改为 Python `RunOptions`。")
            continue

        # `CLI` 执行入口移除：提案常用反引号包含空格，无法按 `token` 规则抽取；这里补一条直白升级指令。
        if ("scalim-cli yaml-dsl run" in cleaned.lower() or "scalim-cli yaml-dsl workflow run" in cleaned.lower()) and (
            "yaml_dsl.runner" not in proposal_text
        ):
            instructions.append("不要再用 `scalim-cli yaml-dsl run` / `scalim-cli yaml-dsl workflow run`（已移除）。")
            continue

        # `demand` 运行期开关迁出 `YAML`：提案中明确了 `fail-fast` 与迁移方向，直接抽成一条高密度升级指令。
        if (
            "demand" in cleaned.lower()
            and "include_full_error_message" in cleaned
            and "validate_unique_field_names" in cleaned
            and ("不再允许" in cleaned or "fail-fast" in cleaned.lower() or "迁移" in cleaned)
        ):
            instructions.append(
                "`demand` YAML：删除顶层 `include_full_error_message` / `validate_unique_field_names`；改为通过 Python/CLI 运行入口参数 `demand_diagnostics` 配置（旧写法会 fail-fast）。"
            )
            continue

        # 工作流等待器默认超时策略：优先抽成可执行的升级指令（避免落到“按提案升级”的低信息量兜底）。
        if "max_wait_s" in cleaned and "`workflow.options.resources_wait`" in proposal_text:
            match = re.search(r"max_wait_s\s*=\s*(\d+)", cleaned)
            if match:
                secs = match.group(1)
                instructions.append(
                    "把 `workflow.options.resources_wait.max_wait_s` 配成你需要的值（默认 {}s，超时会 fail-fast）。".format(secs)
                )
            else:
                instructions.append("把 `workflow.options.resources_wait.max_wait_s` 配成你需要的值（超时会 fail-fast）。")
            continue

        # `xlsx_memory` + `align_by=header`（破坏性语义收紧）
        if "xlsx_memory" in cleaned and ("align_by=header" in cleaned or "align_by: header" in cleaned):
            instructions.append("不要再用 `xlsx_memory + align_by=header`；改为按 canonical field key 对齐（旧写法会 fail-fast）。")
            continue

        # `outputs_defaults` -> `outputs[*].to.book`（带迁移方向的一句）
        if "`outputs_defaults.to.book`" in cleaned and "`outputs[*].to.book`" in cleaned:
            reuse_hint = ""
            if "anchors" in proposal_text or "`$import`" in proposal_text or "$import" in proposal_text:
                reuse_hint = "（需要复用可用 YAML anchors / `$import`）"
            instructions.append("把 `outputs_defaults.to.book` 迁移为每个输出显式写 `outputs[*].to.book`{}。".format(reuse_hint))
            continue

        # `CSV` 容器 -> `resources.files` + `to.file` + `write`（旧写法会 `fail-fast`）
        if "`outputs[*].container`" in cleaned:
            instructions.append(
                "把 CSV 的 `outputs[*].container` 迁移为 `resources.files` + `outputs[*].to.file` + `outputs[*].write`（旧写法会 fail-fast）。"
            )
            continue

        # `observability.*` 迁出 `YAML`：直接给出迁移方向。
        if "`observability.*`" in cleaned and (
            "移出" in cleaned or "迁到" in cleaned or "迁出" in cleaned or "migration" in cleaned.lower()
        ):
            instructions.append("不要再用 `observability.*`；迁移到 Python / CLI 的运行入口配置。")
            continue

        if "write_to" in cleaned and "writes" in cleaned:
            if "`workflow.runs[*].write_to`" in cleaned and "`workflow.runs[*].writes`" in cleaned:
                instructions.append("把 `workflow.runs[*].write_to` 改为 `workflow.runs[*].writes`。")
                continue
            instructions.append("workflow YAML：把 `write_to` 改为 `writes`（旧写法会 fail-fast）。")
            continue

        # === “默认值变更/必填约束”这类高频 `upgrade` 点 ===
        # 1) “默认值从 `old -> new`”：用户要做的动作通常是“显式写回 `old`（若要保持旧行为）”。
        match = re.search(
            r"`([^`]+)`[^`]*默认值(?:从|由)\s*`([^`]+)`\s*(?:调整为|改为|变为|更新为|切换为)\s*`([^`]+)`",
            cleaned,
        )
        if match:
            key, old, new = match.group(1).strip(), match.group(2).strip(), match.group(3).strip()
            # 保守：只在看起来像 `authoring surface` 的键路径时输出迁移指令。
            if "." in key or _tok_is_surface(key):
                instructions.append("依赖旧默认 `{}` 的配置：显式写 `{}: {}`（新默认 `{}`）。".format(old, key, old, new))
                continue

        # 2) “改为必填/`required`”：直接告诉用户“必须显式填写”。
        match = re.search(r"`([^`]+)`[^`]*(?:改为|变为|调整为)[^\\n]*必填", cleaned)
        if match:
            key = match.group(1).strip()
            # 若文本里给了具体上下文（例如某个 `preset`），尽量带上，避免用户对不上号。
            if "WorkflowCachePoolPreloadForeverShared" in cleaned:
                instructions.append("bounded preset：为 `WorkflowCachePoolPreloadForeverShared` 显式填写 `max_entries`（默认值已移除）。")
            else:
                instructions.append("为 `{}` 显式填写配置值（现在必填；默认值已移除）。".format(key))
            continue

        # 重命名：`old` -> `new`
        match = re.search(r"`([^`]+)`\s*(?:指令节点)?(?:更名为|重命名为)\s*`([^`]+)`", cleaned)
        if match:
            old, new = match.group(1), match.group(2)
            if _tok_is_surface(old):
                instructions.append("把 `{}` 改为 `{}`。".format(old, new))
                continue

        match = re.search(r"将\s+.*?`([^`]+)`\s+.*?(?:更名为|重命名为)\s*`([^`]+)`", cleaned)
        if match:
            old, new = match.group(1), match.group(2)
            if _tok_is_surface(old):
                instructions.append("把 `{}` 改为 `{}`。".format(old, new))
                continue

        match = re.search(r"`([^`]+)`.*(?:升级为|改为|改成|替换为|改写为)\s*`([^`]+)`", cleaned)
        if match:
            old, new = match.group(1), match.group(2)
            if _tok_is_surface(old):
                instructions.append("把 `{}` 改为 `{}`。".format(old, new))
                continue

        match = re.search(r"(?:由|从)\s*`([^`]+)`\s*(?:更新为|改为|改成|替换为|改写为|迁移为|升级为)\s*`([^`]+)`", cleaned)
        if match:
            old, new = match.group(1), match.group(2)
            if _tok_is_surface(old):
                instructions.append("把 `{}` 改为 `{}`。".format(old, new))
                continue

        match = re.search(r"`([^`]+)`\s*(?:更新为|改为|改成|替换为|改写为|迁移为|升级为)\s*`([^`]+)`", cleaned)
        if match:
            old, new = match.group(1), match.group(2)
            if _tok_is_surface(old):
                instructions.append("把 `{}` 改为 `{}`。".format(old, new))
                continue

        if "--strict" in cleaned and "yaml-dsl validate" in cleaned:
            instructions.append("不要再用 `yaml-dsl validate --strict`；直接用 `yaml-dsl validate`（默认严格）。")
            continue

        if "value_cast" in cleaned and "None" in cleaned and '"None"' in cleaned:
            instructions.append('把下游依赖 `"None"` 字符串的逻辑改成处理 `None`（`value_cast: str/int` 不再把 None 变成 "None"）。')
            continue

        runtime_old = re.search(r"\$runtime\.([A-Za-z0-9_]+)", cleaned)
        runtime_new = re.search(r"\{\$runtime:\s*([A-Za-z0-9_]+)\}", cleaned)
        if runtime_old and runtime_new and runtime_old.group(1) == runtime_new.group(1):
            name = runtime_old.group(1)
            instructions.append("把 `$runtime.{}` 改成 `{{$runtime: {}}}`（旧写法会 fail-fast）。".format(name, name))
            continue
        if runtime_old and runtime_new:
            instructions.append("把 `$runtime.<name>` 字符串占位符迁移为 `{$runtime: <name>}` 指令节点（旧写法会 fail-fast）。")
            continue

        if (
            "fields.<field_id>.field" in cleaned
            or "`field` 从稳定 YAML authoring surface 中移除" in cleaned
            or "`field`" in cleaned
            and "移除" in cleaned
            and "`extract" in cleaned
        ):
            instructions.append("把 `fields.*.field` 迁移为 `extract`（`field` 会在校验阶段 fail-fast）。")
            continue

        if "bind/to_bind" in cleaned:
            instructions.append("把 `bind/to_bind` 写法迁移到 `params` 模板内联指令（旧写法会 fail-fast）。")
            continue

        if "aggregate.metrics" in cleaned and "aggregate.fields" in cleaned:
            instructions.append("把 `outputs[*].aggregate.metrics` 改为 `outputs[*].aggregate.fields`。")
            continue

        if "{op:" in cleaned and "函数当 key" in cleaned and "aggregate.fields" in cleaned:
            instructions.append(
                "把 `outputs[*].aggregate.fields.<field_id>` 从 `{op: ...}` 改成“函数当 key”的新写法（如 `order_cnt: {count: {}}`）。"
            )
            continue

        # 兜底：保持短句且直接。
        if cleaned.startswith("把 ") or cleaned.startswith("不要") or cleaned.startswith("将 ") or cleaned.startswith("按 "):
            instructions.append(cleaned.rstrip("。") + "。")
            continue
        if ("移除" in cleaned or "移出" in cleaned or "迁出" in cleaned or "删除" in cleaned) and "`" in cleaned:
            if "输出约束" in cleaned or ("输出" in cleaned and "effective" in cleaned.lower()):
                continue
            toks = re.findall(r"`([^`]+)`", cleaned)
            tok = next((t for t in toks if _tok_is_surface(t)), None)
            if tok:
                if (
                    "不兼容" in cleaned
                    or "不再支持" in cleaned
                    or "已移除" in cleaned
                    or "直接失败" in cleaned
                    or "fail-fast" in cleaned.lower()
                    or "runtime" in cleaned.lower()
                    or "旧写法" in cleaned
                    or "旧语法" in cleaned
                    or "旧字段" in cleaned
                    or "write_to" in tok.lower()
                ):
                    instructions.append("不要再用 `{}`（已移除/不兼容）。".format(tok))
                else:
                    instructions.append("不要再用 `{}`（已移除）。".format(tok))
                continue
        instructions.append("按提案升级：{}。".format(cleaned.rstrip("。")))

    # 去重：保持原顺序。
    seen: Set[str] = set()
    uniq: List[str] = []
    for ins in instructions:
        if ins in seen:
            continue
        seen.add(ins)
        uniq.append(ins)
    return uniq


def _score_change(change: _Change) -> int:
    score = 0
    cid = change.change_id.lower()
    # `Highlights` 只把“写法/语义”相关的 YAML 变更顶上来；纯 `refactor/docs` 不用靠 `is_yaml` 抢版面。
    if change.is_yaml and change.example_priority < 99:
        score += 120
    elif change.is_yaml:
        score += 20
    if "value-cast" in cid or "value_cast" in cid or ("decimal" in cid and "value" in cid):
        score += 60
    if "template-vars" in cid or "template_vars" in cid:
        score += 50
    if "normalize" in cid:
        score += 70
    if "extract" in cid and change.example_priority == 2:
        score += 70
    if "inline-dynamic-params" in cid or "params" in cid or "runtime-vars" in cid or "init-vars" in cid or "init-var" in cid:
        score += 50
    if "imports" in cid or "relative-import" in cid:
        score += 40
    # `output`/`outputs`/`aggregate` 都算“输出编写面”一类。
    if "outputs" in cid or "output" in cid or "aggregate" in cid or "derived-outputs" in cid:
        score += 30
    # 稳定 `public facade/shortcut`（面向用户的 `API` 入口）通常比内部拆分细节更值得进 `Highlights`。
    if change.keyword in ("resources-discovery", "public-api-surface-governance") or "output-discovery" in cid:
        score += 120
    if "workflow" in cid:
        score += 80
    if "qa" in cid or "hardening" in cid:
        score += 60
    if "lsp" in cid or "vscode" in cid or "editor" in cid:
        score += 90
    if "refactor" in cid or "core" in cid:
        score += 50
    # `Highlights` 里优先把破坏性升级点顶上来，否则容易被“编辑器/文档/卫生”类变更挤掉。
    if change.has_breaking:
        score += 250
    if "skill" in cid:
        score -= 30
    if "preproposal" in cid:
        score -= 50
    if "frontend" in cid:
        score += 30
    # 文档漂移/卫生在多数发布中不应盖过“写法/行为”变更：仅在缺少其它变化时才上榜。
    if "docs-consistency" in cid or "docs" in cid:
        score -= 80
    # `schema docs standardizer` / `dev-only` 插件通常不是“发布主线变化”，避免压过 `workflow`/核心重构。
    if "doc-standardizer" in cid or "doc_standardizer" in cid:
        score -= 250
    if change.keyword == "dev-optional-plugins":
        score -= 150
    if "marimo" in cid:
        score += 10
    if "demo" in cid or "example" in cid:
        score -= 20
    if "prompt-eval" in cid:
        score += 10
    return score


def _build_change(tag: str, change_id: str, *, root: Path) -> Optional[_Change]:
    proposal_relpath = "openspec/changes/archive/{}/proposal.md".format(change_id)
    proposal_text = _read_file_at_tag(tag, proposal_relpath, root=root)
    if proposal_text is None:
        # 兼容极端情况：`archive` 中没有 `proposal.md` 时再尝试 `design.md`（仍只读快照，不读 `patch`）。
        design_relpath = "openspec/changes/archive/{}/design.md".format(change_id)
        proposal_text = _read_file_at_tag(tag, design_relpath, root=root)
        if proposal_text is None:
            return None

    keyword = _extract_keyword(proposal_text, fallback_change_id=change_id)
    cap_names: List[str] = []
    for line in _extract_section_lines(proposal_text, "Capabilities"):
        match = re.search(r"-\s+`([^`]+)`\s*[:：]", line)
        if match:
            cap_names.append(match.group(1).strip())
    is_yaml = "yaml" in change_id.lower() or "yaml" in keyword.lower() or any("yaml" in name.lower() for name in cap_names)
    highlight = _choose_highlight_from_proposal(proposal_text, change_id)
    breaking = _extract_breaking_instructions(proposal_text, change_id)
    has_breaking = len(breaking) > 0 and any("按提案升级：" not in b for b in breaking)
    prio = _example_priority(change_id, proposal_text) if is_yaml else 99
    return _Change(
        change_id=change_id,
        proposal_text=proposal_text,
        keyword=keyword,
        is_yaml=is_yaml,
        highlight=highlight,
        has_breaking=has_breaking,
        breaking_instructions=tuple(breaking),
        example_priority=prio,
    )


def _git_log_oneline(prev_tag: str, tag: str, *, root: Path) -> List[str]:
    out = _run_git(["log", "--oneline", "{}..{}".format(prev_tag, tag)], cwd=root)
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    return lines


def _render_notes(
    tag: str,
    prev_tag: str,
    *,
    new_changes: List[_Change],
    commit_lines: List[str],
    include_example: bool,
    highlight_max: int,
    breaking_max: int,
) -> str:
    lines: List[str] = []

    lines.append("## Highlights")
    if not new_changes:
        lines.append("- 本版本没有新增 archived OpenSpec 提案，主要是实现/修整。")
    else:
        # 优先挑更关键的变更；若本版本有 YAML 变更，`Highlights` 至少保留 1 条 YAML。
        sorted_changes = sorted(new_changes, key=_score_change, reverse=True)
        chosen = sorted_changes[:highlight_max]
        yaml_authoring = [c for c in new_changes if c.is_yaml and c.example_priority < 99]
        if yaml_authoring and not any(c.is_yaml and c.example_priority < 99 for c in chosen):
            yaml_first = next((c for c in sorted_changes if c.is_yaml and c.example_priority < 99), None)
            if yaml_first is not None and chosen:
                chosen[-1] = yaml_first
            elif yaml_first is not None:
                chosen = [yaml_first]

        # `Highlights` 里尽量保留至少 1 条 `workflow` 相关变更（更贴近你给的优先级：`workflow` 语义/编排变化）。
        workflow_changes = [c for c in new_changes if "workflow" in c.change_id.lower()]
        if workflow_changes and not any("workflow" in c.change_id.lower() for c in chosen):
            workflow_first = next((c for c in sorted_changes if "workflow" in c.change_id.lower()), None)
            if workflow_first is not None and chosen:
                replace_idx = len(chosen) - 1
                # 若本版本存在 YAML `authoring` 变更，避免把唯一的 YAML `authoring` `highlight` 替换掉。
                if yaml_authoring:
                    yaml_idxs = [i for i, c in enumerate(chosen) if c.is_yaml and c.example_priority < 99]
                    if len(yaml_idxs) == 1 and replace_idx == yaml_idxs[0]:
                        alt = next((i for i in range(len(chosen) - 1, -1, -1) if i != yaml_idxs[0]), None)
                        if alt is not None:
                            replace_idx = alt
                chosen[replace_idx] = workflow_first
            elif workflow_first is not None:
                chosen = [workflow_first]

        for ch in chosen:
            highlight = ch.highlight.strip().rstrip("。").rstrip(".")
            lines.append("- {}（{}）".format(highlight + "。", ch.keyword))

    lines.append("## Breaking / Upgrade")
    breaking_items: List[str] = []
    for ch in new_changes:
        # 按你的约束：只放“旧写法跑不起来 / 需要改 YAML/配置”的点；完全基于提案文本抽取（不做代码推断）。
        breaking_items.extend(list(ch.breaking_instructions))
    # 丢弃“按提案升级：...”这类低信息量兜底项（不满足“你要改什么”的要求）。
    breaking_items = [b for b in breaking_items if not b.startswith("按提案升级：")]

    # 去重：保持顺序。
    seen: Set[str] = set()
    breaking_uniq: List[str] = []
    for item in breaking_items:
        if item in seen:
            continue
        seen.add(item)
        breaking_uniq.append(item)

    # 若同一迁移点同时出现“把 `old` 改为 `new`”与“不要再用 `old`”，保留前者即可。
    replaced_old_tokens: Set[str] = set()
    for item in breaking_uniq:
        match = re.search(r"^把 `([^`]+)` 改为 `([^`]+)`", item)
        if match:
            replaced_old_tokens.add(match.group(1))
    if replaced_old_tokens:
        filtered: List[str] = []
        for item in breaking_uniq:
            match = re.search(r"^不要再用 `([^`]+)`", item)
            if match and match.group(1) in replaced_old_tokens:
                continue
            filtered.append(item)
        breaking_uniq = filtered

    # 若已有 `workflow.options.*` 的汇总迁移指令，则移除各子字段的单项提示，避免刷屏。
    if any("`workflow.options.*`" in it for it in breaking_uniq):
        breaking_uniq = [it for it in breaking_uniq if ("`workflow.options.*`" in it) or ("`workflow.options." not in it)]

    # 若已有“组合升级指令”，则移除对应的单项移除提示，避免 `Breaking` 刷屏。
    if any("include_full_error_message" in it and "validate_unique_field_names" in it for it in breaking_uniq):
        breaking_uniq = [
            it
            for it in breaking_uniq
            if not (it.startswith("不要再用 `include_full_error_message`") or it.startswith("不要再用 `validate_unique_field_names`"))
        ]

    if not breaking_uniq:
        breaking_uniq = ["无（提案未提及不兼容/迁移点）。"]

    # 优先展示“你要改成什么”的迁移指令，其次再是“不要再用”的移除提示。
    if len(breaking_uniq) > 1:
        scored: List[Tuple[int, int, str]] = []
        for idx, item in enumerate(breaking_uniq):
            s = item.strip()
            score = 0
            if s.startswith("把 "):
                score += 100
            if any(k in s for k in ("改为", "改成", "替换为", "迁移为", "升级为")):
                score += 80
            if s.startswith("不要再用 "):
                score += 60
            if "`just " in s or s.startswith("不要再用 `just "):
                score -= 30
            if "fail-fast" in s.lower() or "直接失败" in s:
                score += 20
            if any(k in s for k in ("outputs", "workflow", "resources", "yaml", "write_lock", "latest.json", "manifest/latest.json")):
                score += 10
            scored.append((score, -idx, item))
        breaking_uniq = [it for _score, _neg_idx, it in sorted(scored, reverse=True)]

    for item in breaking_uniq[:breaking_max]:
        normalized = item.strip().rstrip("。").rstrip(".")
        lines.append("- {}".format(normalized + "。"))

    if include_example:
        yaml_candidates = [c for c in new_changes if c.is_yaml and c.example_priority < 99]
        # 同一优先级下优先选择带破坏性迁移点的变更，避免示例落到纯“编辑器能力”导致不贴题。
        yaml_candidates.sort(key=lambda c: (c.example_priority, not c.has_breaking, c.change_id))
        for chosen in yaml_candidates:
            snippet_lines = _render_example_snippet_for_change(chosen)
            if not snippet_lines:
                continue
            lines.append("## 新增/改动语法（示例）")
            lines.append("```yaml")
            lines.extend(snippet_lines)
            lines.append("```")
            break

    lines.append("## Commits（节选）")
    max_commit_lines = 8
    if len(commit_lines) <= max_commit_lines:
        shown = commit_lines
    else:
        # 仍保持 8 行：第 8 条 `commit` 行尾追加 “…略”。
        shown = commit_lines[:max_commit_lines]
        if shown:
            shown[-1] = shown[-1] + " …略"
    for ln in shown:
        lines.append("- {}".format(ln))

    # 强制 <= 30 行：优先裁 `Commits`，再裁 `Highlights/Breaking`（不删除各节标题）。
    while len(lines) > 30:
        # 优先裁 `Commits` 段内容。
        try:
            commits_idx = lines.index("## Commits（节选）")
        except ValueError:
            break
        if len(lines) > commits_idx + 2:
            # 从末尾移除 1 行提交记录（保留标题）。
            for k in range(len(lines) - 1, commits_idx, -1):
                if lines[k].startswith("- "):
                    del lines[k]
                    break
            continue
        break

    return "\n".join(lines).rstrip() + "\n"


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按 archived OpenSpec 提案+commit messages 批量 create/edit GitHub Releases。")
    parser.add_argument("--start-tag", default="v0.2.1", help="起始 tag（包含）。默认: v0.2.1")
    parser.add_argument("--prev-for-start", default="v0.1.0", help="start-tag 的 prev tag（用于 commits 区间）。默认: v0.1.0")
    parser.add_argument("--end-tag", default="", help="结束 tag（包含）。为空则使用仓库中最新 semver tag。")
    parser.add_argument("--notes-dir", default="", help="notes 输出目录。为空则写到 /tmp 下新目录。")
    parser.add_argument("--apply", action="store_true", help="执行 gh release create/edit。默认仅生成 notes。")
    parser.add_argument("--sleep-secs", type=int, default=5, help="每次 create/edit 后 sleep 秒数。默认: 5")
    parser.add_argument("--root", default=".", help="仓库根目录（默认: 当前目录）。")
    return parser.parse_args(list(argv or sys.argv[1:]))


def _ensure_gh_available() -> None:
    try:
        subprocess.run(["gh", "--version"], check=True, stdout=subprocess.DEVNULL)
    except Exception as exc:
        raise RuntimeError("未找到 gh CLI 或不可用: {}".format(exc))


def _gh_release_exists(tag: str) -> bool:
    proc = subprocess.run(["gh", "release", "view", tag], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc.returncode == 0


def _gh_release_create(tag: str, notes_path: Path) -> None:
    subprocess.run(["gh", "release", "create", tag, "--title", tag, "--notes-file", str(notes_path)], check=True)


def _gh_release_edit(tag: str, notes_path: Path) -> None:
    subprocess.run(["gh", "release", "edit", tag, "--title", tag, "--notes-file", str(notes_path)], check=True)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    root = Path(args.root).resolve()

    tags = _list_semver_tags(root)
    if not tags:
        print("未找到符合 `vX.Y.Z` 的版本标签（语义化版本）", file=sys.stderr)
        return 2

    start = args.start_tag.strip()
    if start not in tags:
        print("起始标签不存在（`--start-tag`）：{}".format(start), file=sys.stderr)
        return 2
    end = args.end_tag.strip() or tags[-1]
    if end not in tags:
        print("结束标签不存在（`--end-tag`）：{}".format(end), file=sys.stderr)
        return 2

    start_idx = tags.index(start)
    end_idx = tags.index(end)
    if end_idx < start_idx:
        print("结束标签早于起始标签：{} < {}".format(end, start), file=sys.stderr)
        return 2

    target_tags = tags[start_idx : end_idx + 1]
    prev_for_start = args.prev_for_start.strip()
    if prev_for_start not in tags:
        print("起始版本的前序标签不存在（`--prev-for-start`）：{}".format(prev_for_start), file=sys.stderr)
        return 2

    notes_dir = args.notes_dir.strip()
    if not notes_dir:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        notes_dir = os.path.join("/tmp", "scalim-gh-release-notes-{}".format(stamp))
    out_dir = Path(notes_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print("仓库根目录：", root)
    print("发布说明目录：", out_dir)
    print("标签序列：", ", ".join(target_tags))

    if args.apply:
        _ensure_gh_available()

    previous_tag = prev_for_start
    notes_paths: Dict[str, Path] = {}
    for tag in target_tags:
        dirs_t = _dirs_in_archive(tag, root=root)
        dirs_p = _dirs_in_archive(previous_tag, root=root)
        new_dirs = sorted(dirs_t - dirs_p)

        changes: List[_Change] = []
        for change_id in new_dirs:
            ch = _build_change(tag, change_id, root=root)
            if ch is None:
                continue
            changes.append(ch)

        has_yaml_authoring = any(c.is_yaml and c.example_priority < 99 for c in changes)
        include_example = has_yaml_authoring
        highlight_max = 3
        breaking_max = 3

        commits = _git_log_oneline(previous_tag, tag, root=root)
        notes = _render_notes(
            tag,
            previous_tag,
            new_changes=changes,
            commit_lines=commits,
            include_example=include_example,
            highlight_max=highlight_max,
            breaking_max=breaking_max,
        )

        path = out_dir / "{}.md".format(tag)
        path.write_text(notes, encoding="utf-8")
        notes_paths[tag] = path

        line_count = notes.count("\n")
        if line_count > 30:
            print("警告：{} 的发布说明行数超限：{}".format(tag, line_count), file=sys.stderr)
        else:
            print("{} 发布说明行数：{}".format(tag, line_count))

        previous_tag = tag

    if not args.apply:
        print("仅生成发布说明（`dry-run`）；加 `--apply` 才会创建/更新发布页。")
        return 0

    print("\n开始创建/更新发布页（每次操作后等待 {} 秒）...".format(args.sleep_secs))
    for tag in target_tags:
        notes_path = notes_paths[tag]
        exists = _gh_release_exists(tag)
        if exists:
            print("更新：", tag)
            _gh_release_edit(tag, notes_path)
        else:
            print("创建：", tag)
            _gh_release_create(tag, notes_path)
        time.sleep(max(0, int(args.sleep_secs)))

    print("\n完成。建议复核：")
    print("- `gh release list --limit 100`")
    print("- `gh release view v0.2.3`")
    print("- `gh release view v0.3.0`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
