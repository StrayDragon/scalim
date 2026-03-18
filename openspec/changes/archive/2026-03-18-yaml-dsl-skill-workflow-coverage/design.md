## Context

近期 workflow YAML 的 authoring surface 已显著扩展（DAG `depends_on`、跨节点小体量 ctx、共享 resources / `write_to`、sheetbook 等），而现有 docs 与 `scalim-yaml-dsl` skill 仍以 demand YAML 为主，形成明显漂移。

本变更的核心是 **对齐与治理**：

- 对齐：把已实现的 workflow authoring surface 写进 docs 与 skill references，让用户/Agent 能“按 schema 写、按命令验”。
- 治理：把易漂移内容放入受控生成层，并通过现有门禁（`just gen-docs` / `just validate-agent-skill` / `just openspec-check`）确保可重复生成。

关键约束（SSOT 与治理）：

- docs 中任何 `.gen.` 为生成物（禁止手改）；任何 `BEGIN/END AUTOGEN:<id>` 块为受控注入（禁止手改块内）。
- skill 的受控生成物集合与校验和由 `artifacts/skills/scalim-yaml-dsl.build-manifest.json` 记录；`just validate-agent-skill` 负责漂移检测。

## Goals / Non-Goals

**Goals:**

- `docs/doc/yaml-dsl/workflow.md` 覆盖 workflow schema 的核心字段与最小可用范式：`runs[*].depends_on/init_vars/write_to`、`options.ctx/cache_pool`、`resources.*`、并发契约与校验入口。
- `artifacts/skills/scalim-yaml-dsl/` 作为统一 skill 入口，新增 workflow 任务路由 + 最小命令（schema validate、schema-serve、upsert-modeline `--type workflow`）。
- skill 生成器纳入 workflow schema 的语法目录/索引，并把 workflow 相关 OpenSpec specs 纳入 requirement map/coverage index（作为“覆盖面基线”）。
- 增加一条 upgrades 文档，把近期 workflow DAG/ctx/resources/sheetbook 的 breaking/migration 信息收敛成可检索入口，并由 `just gen-docs` 生成对应 docs 页面。
- 消除 `workflow-sheetbook-resources` spec 的元信息 TBD（补齐 Purpose/状态），提升 OpenSpec index 的覆盖观感。

**Non-Goals:**

- 不改 workflow/demand 的运行时行为、不新增 workflow runner CLI（仍以 Python 入口为主）。
- 不引入旧写法兼容层；只在 upgrades 中提供迁移提示（不做双写/兼容模式）。
- 不重写 docs 站点结构（除非 workflow 页面因新增内容显著过长才拆分）。

## Decisions

1) **扩展现有 skill，而不是新建 workflow skill**

- 选择：把 workflow authoring/validate/debug 纳入 `scalim-yaml-dsl`，保持“一套入口覆盖 demand + workflow”。
- 原因：用户侧/Agent 侧更少选择成本，且生成器与门禁已围绕该 skill 成熟。

2) **workflow 语法目录与 CLI reference 进入受控生成层**

- 选择：在 `packages/scalim-misc/src/scalim_misc/agent_skill_gen.py` 中引入 `workflow.gen.json`，扩展 `syntax-catalog.gen.md` 与 `cli-lsp-reference.gen.md`。
- 原因：workflow schema 演进快，手工维护易漂移；生成器可对齐 schema/CLI 的“唯一真相”。

3) **docs 只手写用户视角，复杂细节链接到 specs**

- 选择：`docs/doc/yaml-dsl/workflow.md` 保持“最小可用 + 常见坑 + 命令入口”，深层约束（确定性写入/冲突策略/可观测性）链接到 OpenSpec spec。
- 原因：避免 docs 过载与重复维护；spec 作为行为真相已存在。

## Risks / Trade-offs

- [Risk] 生成器扩展后会引入较大 diff（新增 workflow 输入、更新 manifest、生成引用文件变化）→ [Mitigation] 在同一提交中跑 `just gen-agent-skill` + `just validate-agent-skill`，并让 CI 漂移门禁兜底。
- [Risk] docs workflow 页面内容膨胀影响可读性 → [Mitigation] 先在单页补齐“最小可用”，如超过可维护阈值再拆分到 `workflow-resources.md`（并在 index 中补链接）。
- [Trade-off] 新增 capability spec（`yaml-dsl-agent-skill`）会带来额外维护 → [Benefit] 为 skill 的“覆盖要求/分层/门禁”提供长期 SSOT，后续 schema 扩展可被要求显式同步。

