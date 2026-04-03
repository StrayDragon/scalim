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
    needle = "## {}".format(heading)
    for i, line in enumerate(lines):
        if line.strip() == needle:
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
    out = re.sub(r"^\*\*NON-BREAKING\*\*:\s*", "", out, flags=re.I)
    out = re.sub(r"^BREAKING:\s*", "", out, flags=re.I)
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
    # OpenSpec capabilities 多为 kebab-case；避免把它们当成 “YAML authoring surface token”。
    if lower.startswith(("yaml-dsl-", "yaml-source-", "openspec-", "docs-", "output-", "lsp-", "frontend-", "cli-", "qa-")):
        return True
    return False


def _score_highlight(text: str) -> int:
    s = text
    lower = s.lower()
    score = 0
    if "non-goals" in lower or "non goals" in lower or "non-goal" in lower or "非目标" in s or "不做" in s or "明确不做" in s:
        score -= 50
    if "新增" in s or "引入" in s or "扩展" in s or "增加" in s or "new" in lower:
        score += 3
    if "支持" in s:
        score += 1
    # `Highlights` 优先保留用户会“立刻感知”的破坏性变更；否则容易被“同步文档/示例”等条目抢走。
    if "BREAKING" in s or "breaking" in lower or "破坏性" in s:
        score += 6
    # 更偏向“作者/用户可感知”的说明，而不是内部实现口径。
    if "yaml" in lower or "YAML" in s:
        score += 1
    if "runtime" in lower or "编译" in s or "compile" in lower:
        score -= 1
    if "dataclass" in lower or "dataclasses" in lower or "数据类" in s:
        score += 2
    if "导入路径" in s or "_internal" in s or "modulenotfounderror" in lower or "内部实现" in s:
        score -= 3
    if "runoverrides" in lower or "overrides." in lower or "by_yaml runtime" in lower:
        score -= 2
    if "重构" in s or "refactor" in lower:
        score += 2
    if "工作流" in s or "workflow" in lower or "质量" in s or "qa" in lower:
        score += 2
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
        if head.endswith(":") or head.endswith("："):
            score -= 4
        # 同分时偏向更靠前的条目。
        return score, -blocks.index(block)

    best = max(blocks, key=_score_block)
    head = _clean_inline_markers(best[0])
    if (head.endswith(":") or head.endswith("：")) and len(best) > 1:
        head = head.rstrip(":：").rstrip()
        tail = _clean_inline_markers(best[1])
        tail = re.sub(r"^-\s+", "", tail)
        if tail:
            return "{}（例如：{}）".format(head, tail.rstrip("。"))
    return head


def _extract_keyword(proposal_text: str, *, fallback_change_id: str) -> str:
    cap_lines = _extract_section_lines(proposal_text, "Capabilities")
    for line in cap_lines:
        match = re.search(r"-\s+`([^`]+)`\s*:", line)
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


def _example_priority(change_id: str) -> int:
    cid = change_id.lower()
    if "normalize" in cid:
        return 1
    # `resources.books` / `workflow IO` 收敛：属于 `outputs/IO` 编写面的核心变化。
    if "books-resources" in cid or "io-books-resources" in cid:
        return 5
    # 字段级：`extract` / `value_cast` / 显式 `decimal` 等都归为同一档（`field-level authoring surface`）。
    if "value-cast" in cid or "value_cast" in cid or ("decimal" in cid and "value" in cid):
        return 2
    if "extract" in cid:
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
    if "imports" in cid or "relative-import" in cid:
        return 4
    if "outputs" in cid or "aggregate" in cid or "derived-outputs" in cid:
        return 5
    if "output-fields-alias" in cid or "fields-alias" in cid:
        return 6
    if "comment-style" in cid:
        return 7
    return 99


def _render_example_snippet(change_id: str, priority: int) -> Optional[List[str]]:
    cid = change_id.lower()
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
        # 常见 YAML key（snake_case）也属于 authoring surface。
        if "_" in t and re.fullmatch(r"[a-z_][a-z0-9_]*", t):
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
        if "." in t and any(k in lower for k in ("workflow", "demand", "outputs", "fields")):
            return True
        return False

    def _is_breaking_candidate(s: str) -> bool:
        text = s.strip()
        if not text:
            return False
        lower = text.lower()
        tokens = re.findall(r"`([^`]+)`", text)
        has_surface_token = (
            any(_tok_is_surface(tok) for tok in tokens) or "workflow." in text or "workflow " in lower or "yaml-dsl" in lower
        )

        # 明确不是 `breaking` 的常见表述：避免“为了避免 `breaking`”之类的句子误入。
        if ("避免" in text or "保持" in text) and ("breaking" in lower or "不兼容" in text):
            if "不再支持" not in text and "移除" not in text and "删除" not in text:
                return False

        # 没有任何 `authoring surface token` 的句子，通常不是“你要改 `YAML`”的点。
        if not has_surface_token:
            return False

        # “输出约束：移除 ...” 这类描述是输出格式约束，不是 `upgrade` 点。
        if "输出约束" in text and ("移除" in text or "删除" in text):
            return False

        # 触发词（严格依赖提案文本，不做代码推断）。
        if re.search(r"\bbreaking\b", lower):
            return True
        if "破坏性" in text or "不兼容" in text or "不再支持" in text:
            return True
        if "删除旧写法" in text:
            return True
        if ("移除" in text or "移出" in text or "迁出" in text or "删除" in text or "废弃" in text or "弃用" in text) and (
            "旧写法" in text
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

        # demand runtime flags 迁出 YAML：提案中明确了 fail-fast 与迁移方向，直接抽成一条高密度升级指令。
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

        # 重命名：`old` -> `new`
        match = re.search(r"`([^`]+)`\s*(?:指令节点)?(?:更名为|重命名为)\s*`([^`]+)`", cleaned)
        if match:
            old, new = match.group(1), match.group(2)
            instructions.append("把 `{}` 改为 `{}`。".format(old, new))
            continue

        match = re.search(r"将\s+.*?`([^`]+)`\s+.*?(?:更名为|重命名为)\s*`([^`]+)`", cleaned)
        if match:
            old, new = match.group(1), match.group(2)
            instructions.append("把 `{}` 改为 `{}`。".format(old, new))
            continue

        match = re.search(r"`([^`]+)`.*(?:升级为|改为|改成|替换为)\s*`([^`]+)`", cleaned)
        if match:
            old, new = match.group(1), match.group(2)
            instructions.append("把 `{}` 改为 `{}`。".format(old, new))
            continue

        match = re.search(r"(?:由|从)\s*`([^`]+)`\s*(?:更新为|改为|改成|替换为|迁移为|升级为)\s*`([^`]+)`", cleaned)
        if match:
            old, new = match.group(1), match.group(2)
            instructions.append("把 `{}` 改为 `{}`。".format(old, new))
            continue

        match = re.search(r"`([^`]+)`\s*(?:更新为|改为|改成|替换为|迁移为|升级为)\s*`([^`]+)`", cleaned)
        if match:
            old, new = match.group(1), match.group(2)
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
    if change.is_yaml:
        score += 100
    if "value-cast" in cid or "value_cast" in cid or ("decimal" in cid and "value" in cid):
        score += 60
    if "template-vars" in cid or "template_vars" in cid:
        score += 50
    if "normalize" in cid:
        score += 70
    if "extract" in cid:
        score += 70
    if "inline-dynamic-params" in cid or "params" in cid or "runtime-vars" in cid or "init-vars" in cid or "init-var" in cid:
        score += 50
    if "imports" in cid or "relative-import" in cid:
        score += 40
    # `output`/`outputs`/`aggregate` 都算“输出编写面”一类。
    if "outputs" in cid or "output" in cid or "aggregate" in cid or "derived-outputs" in cid:
        score += 30
    if "workflow" in cid:
        score += 80
    if "qa" in cid or "hardening" in cid:
        score += 60
    if "lsp" in cid or "vscode" in cid or "editor" in cid:
        score += 90
    if "refactor" in cid or "core" in cid:
        score += 50
    if "breaking" in change.proposal_text.lower() or change.has_breaking:
        score += 40
    if "skill" in cid:
        score -= 30
    if "preproposal" in cid:
        score -= 50
    if "frontend" in cid:
        score += 30
    # 文档漂移/卫生在多数发布中不应盖过“写法/行为”变更：仅在缺少其它变化时才上榜。
    if "docs-consistency" in cid or "docs" in cid:
        score -= 80
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
        match = re.search(r"-\s+`([^`]+)`\s*:", line)
        if match:
            cap_names.append(match.group(1).strip())
    is_yaml = "yaml" in change_id.lower() or "yaml" in keyword.lower() or any("yaml" in name.lower() for name in cap_names)
    highlight = _choose_highlight(_extract_section_lines(proposal_text, "What Changes"))
    breaking = _extract_breaking_instructions(proposal_text, change_id)
    has_breaking = len(breaking) > 0 and any("按提案升级：" not in b for b in breaking)
    prio = _example_priority(change_id) if is_yaml else 99
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
        if any(c.is_yaml for c in new_changes) and not any(c.is_yaml for c in chosen):
            yaml_first = next((c for c in sorted_changes if c.is_yaml), None)
            if yaml_first is not None and chosen:
                chosen[-1] = yaml_first
            elif yaml_first is not None:
                chosen = [yaml_first]

        for ch in chosen:
            highlight = ch.highlight.strip().rstrip("。").rstrip(".")
            lines.append("- {}（{}）".format(highlight + "。", ch.keyword))

    lines.append("## Breaking / Upgrade")
    breaking_items: List[str] = []
    for ch in new_changes:
        # 按你的约束：只放“需要改 `YAML`/旧写法跑不起来”的点；因此仅从 `YAML` 相关 `archived changes` 抽取。
        if ch.is_yaml:
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

    # 若已有“组合升级指令”，则移除对应的单项移除提示，避免 Breaking 刷屏。
    if any("include_full_error_message" in it and "validate_unique_field_names" in it for it in breaking_uniq):
        breaking_uniq = [
            it
            for it in breaking_uniq
            if not (it.startswith("不要再用 `include_full_error_message`") or it.startswith("不要再用 `validate_unique_field_names`"))
        ]

    if not breaking_uniq:
        if new_changes:
            breaking_uniq = ["无（本版本 archived 提案未声明不兼容/迁移点）。"]
        else:
            breaking_uniq = ["无（该 tag 未包含 archived OpenSpec 提案，无法从提案文本抽取迁移点）。"]

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
            if "fail-fast" in s.lower() or "直接失败" in s:
                score += 20
            if any(k in s for k in ("outputs", "workflow", "resources", "yaml")):
                score += 10
            scored.append((score, -idx, item))
        breaking_uniq = [it for _score, _neg_idx, it in sorted(scored, reverse=True)]

    for item in breaking_uniq[:breaking_max]:
        normalized = item.strip().rstrip("。").rstrip(".")
        lines.append("- {}".format(normalized + "。"))

    if include_example:
        yaml_candidates = [c for c in new_changes if c.is_yaml and c.example_priority < 99]
        yaml_candidates.sort(key=lambda c: (c.example_priority, c.change_id))
        if yaml_candidates:
            chosen = yaml_candidates[0]
            snippet_lines = _render_example_snippet(chosen.change_id, chosen.example_priority)
            if snippet_lines:
                lines.append("## 新增/改动语法（示例）")
                lines.append("```yaml")
                lines.extend(snippet_lines)
                lines.append("```")

    lines.append("## Commits（节选）")
    max_commit_lines = 8
    if len(commit_lines) <= max_commit_lines:
        shown = commit_lines
    else:
        # 把 “...略” 也算进 8 行预算里：7 条 `commit` + 1 行省略。
        shown = commit_lines[: max_commit_lines - 1] + ["...略"]
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

        has_yaml = any(c.is_yaml for c in changes)
        include_example = has_yaml and any(c.example_priority < 99 for c in changes)
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
