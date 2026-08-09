---
name: scalim-yaml-dsl
description: "编写、重构、升级、校验和排错 Scalim YAML DSL(demand/workflow)配置,并为旧报表脚本规划渐进迁移。覆盖 resources.books identity(唯一分支 xlsx,可选 path)、outputs→book 绑定、Python ResourcesPolicy/BookWritePolicy(write_defaults 已迁出 YAML；book budget/BookBudgetPolicy 已移除)、Python IR 侧 DedupBy/TwoStageGroupBy 已移除、RunOverrides IO overlay(含保留的 xlsx_file_single_sheet 工厂)、path/init_var 输出 root、以及 scalim-cli yaml-dsl validate/schema。适用于修复 validate 报错、迁移 write_defaults/删除残留 budget/已硬删的 xlsx_file|xlsx_memory、迁移已删 Dedup/TwoStage IR、判断逻辑应留在 Python 还是下沉 YAML 的场景。"
---

# Scalim YAML DSL

先识别任务类型,只读取最少的 reference:

- 新写或改写 YAML: 读 [references/task-authoring.md](references/task-authoring.md)
- **YAML vs Python 边界**（开放盘点；动态 knobs 目标收口 Python）: 读 [references/yaml-runtime-policy-boundary.md](references/yaml-runtime-policy-boundary.md)（`llmanspec/changes/c40-yaml-runtime-policy-boundary/evidence-notes.md`）
- 新写或改写 workflow YAML(编排多 demand / `workflow.resources.books` / outputs→book 绑定 / `resources_policy`): 读 [references/task-workflow-authoring.md](references/task-workflow-authoring.md)
- 旧写法直接升级到当前结构: 读 [references/task-upgrade-legacy.md](references/task-upgrade-legacy.md)
- 校验、订正、排错: 读 [references/task-validate-debug.md](references/task-validate-debug.md)
- 运行时故障处理(服务端/工作目录/PYTHONPATH 导致的相对引用问题): 读 [references/task-runtime-troubleshooting.md](references/task-runtime-troubleshooting.md)
- 校验、订正、排错 workflow YAML: 读 [references/task-workflow-validate-debug.md](references/task-workflow-validate-debug.md)
- 服务端并发输出/版本化输出(D-2)/outputs facade 定位写法: 读 [references/task-workflow-versioned-outputs.md](references/task-workflow-versioned-outputs.md)
- 旧报表脚本渐进迁移方案: 读 [references/task-report-migration-playbook.md](references/task-report-migration-playbook.md)
- 宽表 Excel 峰值 / `StreamingColumnExcelSink` / `ExcelColumnResidency` 选型: 读 [references/streaming-column-excel-guidance.md](references/streaming-column-excel-guidance.md)（人类文档: `docs/doc/getting-started/excel-column-residency.md`）
- **0.10.0 版本亮点**（默认 write-precompute / row-wise fusion；opt-in lookup chunk 并行；YAML 无强制迁移）: 读 [references/0.10-release-highlights.md](references/0.10-release-highlights.md)（人类总览: `docs/doc/releases/0.10.0/index.md`）
- **0.10.1**（相对 0.10.0；YAML 无强制迁移；Python typed handlers 收 `Event`）: [references/0.10.1-release-highlights.md](references/0.10.1-release-highlights.md) + `docs/doc/releases/0.10.1/`；Observer/Hook 迁移走 `scalim-public-api`
- 下游适配盘点与同步: 读 [references/task-downstream-adaptation.md](references/task-downstream-adaptation.md)
- **低漂移自我观测**（run_stats / profiles / write 归因；非 YAML authoring）: 改读 `agentdev/skills/scalim-run-stats/SKILL.md` + `docs/doc/viz/run-stats.md`
- 需要按批次快速定位 breaking/migration: 读 [references/generated/yaml-dsl-upgrades.gen.md](references/generated/yaml-dsl-upgrades.gen.md)
- 需要阅读完整升级指南(SSOT): 读 `references/upgrades/*.md`(book write: `2026-07-12-book-write-policy-python-ssot.md`；book budget 移除: `2026-07-28-remove-book-budget-policy.md`；Dedup/TwoStage IR 移除: `2026-07-28-remove-dedup-and-two-stage-derived.md`)
- 需要全量语法/API: 读 [references/syntax-catalog.gen.md](references/syntax-catalog.gen.md) 和 [references/generated/cli-lsp-reference.gen.md](references/generated/cli-lsp-reference.gen.md)
- 需要完整 canonical example: 读 [references/generated/example-full/ecommerce_report.gen.yaml](references/generated/example-full/ecommerce_report.gen.yaml)

先给出最小可执行命令,再开始分析或改 YAML:

<!-- BEGIN AUTOGEN:yaml-dsl-skill-cli-min-commands -->
- demand YAML 仓库内完整校验: `uv run scalim-cli yaml-dsl validate <demand.yaml>`
- demand YAML workflow 上下文校验: `uv run scalim-cli yaml-dsl validate --workflow <workflow.yaml> <demand.yaml>`
- demand YAML 仓库内 schema 校验: `uv run scalim-cli yaml-dsl schema validate <demand.yaml>`
- demand YAML workflow 上下文 schema 校验: `uv run scalim-cli yaml-dsl schema validate --workflow <workflow.yaml> <demand.yaml>`
- workflow YAML 仓库内完整校验(静态/编译期;递归校验引用的 demands;不执行 workflow): `uv run scalim-cli yaml-dsl validate --type workflow <workflow.yaml>`
- workflow YAML 仓库内 schema 校验(结构/unknown-fields; 必须显式 schema 路径): `uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/yaml_dsl/schema/workflow.gen.json <workflow.yaml>`
- 仓库外完整校验: `uvx scalim-cli yaml-dsl validate <file.yaml>`
- 仓库外 schema 校验: `uvx scalim-cli yaml-dsl schema validate <file.yaml>`
- 仓库内查询 schema 绝对路径: `uv run scalim-cli yaml-dsl schema path`
- 仓库外查询 schema 绝对路径: `uvx scalim-cli yaml-dsl schema path`

完整 canonical example 故意不带头部(也就是 schema modeline)。本地编辑时,我们一般用下面这套“团队通用”的做法(直接批量写入头部,不依赖内置 schema server):

- 批量插入/更新头部(默认同时写 Red Hat + JetBrains 两种 modeline; 用 `--comment-style` 控制): `uv run scalim-cli yaml-dsl upsert-lsp-comment --type demand --comment-style all <paths...>`
- workflow YAML 同理: `uv run scalim-cli yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`

运行入口已迁出 CLI,统一使用 Python API(需 allowlist):

```python
from scalim.dsl.yaml_dsl import (
    DemandRunOptions,
    DemandRunSecurityOptions,
    WorkflowRunOptions,
    run,
    run_workflow,
)

demand = DemandRunOptions(
    security=DemandRunSecurityOptions(
        allowed_modules=frozenset(["myapp.loaders"]),
    ),
)

run(
    "path/to/demand.yaml",
    options=demand,
)

run_workflow(
    "path/to/workflow.yaml",
    options=WorkflowRunOptions(demand=demand),
)
```

```yaml
# yaml-language-server: $schema=.../demand.gen.json
# $schema: .../demand.gen.json
```
<!-- END AUTOGEN:yaml-dsl-skill-cli-min-commands -->

工作时遵守这些硬规则:

- 顶层 `fields` 只放派生字段,必须使用 `compute` 或 `call_by`
- `main_source.fields` / `sources.<id>.fields` 只放源字段,不要把派生逻辑塞进去
- `relations.*.steps.from/to` 写 YAML 的字段 ID(不要写 loader 的 `data_key`)
- 不要硬记/猜语法: 以 schema / 生成文档为准(需要时看 `references/syntax-catalog.gen.md`、`references/generated/cli-lsp-reference.gen.md`、`references/generated/example-full/ecommerce_report.gen.yaml`)
- 迁移/升级优先看自动索引的 upgrades(从 `references/task-upgrade-legacy.md` 进入,或读取生成的 upgrades 摘要)
- 未明确要求兼容时,旧 DSL 写法直接升级到当前结构,不要保留兼容层
- YAML `resources.books` 只声明 identity（唯一分支 `xlsx`：有 `path`=落盘，无 `path`=内存总线；`xlsx_file`/`xlsx_memory` 已硬删）;`write_defaults` 已迁出 → 用 `WorkflowRunOptions`/`DemandRunOptions.resources_policy`(`BookWritePolicy`,StrEnum 严格 in)；`budget` / `BookBudgetPolicy` **已移除**（YAML/`RunOverrides` 残留仍 fail-fast，删字段；内存交宿主限制）；Python IR `DedupBy*` / `TwoStageGroupBy*` **已移除**（loader 去重 / workflow 两段 demand）；详见 `references/upgrades/2026-07-12-book-write-policy-python-ssot.md`、`references/upgrades/2026-07-28-remove-book-budget-policy.md`、`references/upgrades/2026-07-28-remove-dedup-and-two-stage-derived.md`、`references/upgrades/2026-07-13-unified-xlsx-book-kind.md`、`references/upgrades/2026-07-13-normalize-xlsx-book-ir-path-presence.md`、`references/upgrades/2026-07-20-remove-deprecated-xlsx-file-memory-kinds.md`
- **MUST NOT** 为降低 Excel 峰值在 YAML 发明 `write.streaming` / books streaming knobs;YAML Excel 组合层已是行 sink。列式 HOLD→WINDOW 用 Python `ExcelColumnResidency`(见 `references/streaming-column-excel-guidance.md` 与站点 `docs/doc/getting-started/excel-column-residency.md`)
- `path` 是输出 root 目录:相对路径相对 **声明该路径的 YAML 文件目录**(不是进程 cwd);环境相关 root 用绝对路径、`{$init_var: ...}` 或 `BookResourceOverride`(IO-only overlay,不再含 write/budget)。唯一写法 `resources.books.*.xlsx.path`（旧 `export_xlsx.path` / `xlsx_file` 已硬删）。
- workflow YAML 校验优先用 `yaml-dsl validate --type workflow`(递归校验引用的 demands,并检查 outputs→book 绑定等跨文件一致性);需要更快时再用 `schema validate --schema .../workflow.gen.json`
- 交付时必须说明: 跑了哪些校验,缺了哪些依赖,哪些内容仍未在真实环境验证
- 若 Python 侧使用 `overrides.outputs` 把 workbook outputs 整体替换为非 workbook 输出,未显式 `path` 的 `meta/audit`
  会被运行时跳过;仍需保留时请显式配置 `meta.path` / `audit.path`

只在需要时再读大 reference,不要默认把全量 catalog 和 playbook 一起塞进上下文。
