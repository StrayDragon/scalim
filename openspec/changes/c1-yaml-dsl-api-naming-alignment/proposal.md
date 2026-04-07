## Why

当前 YAML DSL 的 Python public API 在“模块路径 / 名词 / 动词”层面存在整体一致性问题：

- 模块名 `by_yaml` 更像实现细节(“按 YAML 实现”)，不如领域名 `yaml_dsl` 直觉；这会让用户在阅读/搜索时不断做心智翻译。
- workflow 的 per-run patch 实际是“对 base `RunOptions` 做局部覆写”，但命名(`WorkflowRunPatch`、`run_patches_by_id`)没有表达 patch 与 `RunOptions` 的关系，导致 API 读起来像两套系统。
- `run`/`compile` 作为动词本身很通用；若模块路径不够语义化，就更难通过代码搜索/示例复用建立稳定心智模型。

我们希望在不考虑破坏性成本的前提下，一次性把这些“用户高频触达的名字”收敛到更一致、更可维护、也更不容易 drift 的命名体系中。

## What Changes

- **BREAKING**：将 YAML DSL 的 canonical public module 从 `scalim.dsl.by_yaml` 收敛为 `scalim.dsl.yaml_dsl`，并同步迁移所有 curated stable modules：
  - `scalim.dsl.yaml_dsl`
  - `scalim.dsl.yaml_dsl.workflow`
  - `scalim.dsl.yaml_dsl.workflow_types`
  - `scalim.dsl.yaml_dsl.workflow_paths`
  - `scalim.dsl.yaml_dsl.tools`
- **BREAKING**：将 workflow per-run patch 命名显式化为 “RunOptions patch”，使其读起来直接对应：
  - `WorkflowRunPatch` → `WorkflowRunOptionsPatch`
  - `run_patches_by_id` → `run_options_patches_by_run_id`（或等价更短但语义不丢失的命名）
- 保留 `run/compile` 作为“执行/编译 demand YAML”的默认动词（符合当前用户心智：run/compile = demand）。
  - 可选：在新 facade 中增加别名 `run_demand = run`、`compile_demand = compile` 作为“更啰嗦但更明确”的可选导入形态（不强制决定主名）。
- 同步更新 specs/docs/notebooks/skills/tests 与治理门禁，使官方材料与 gate 统一使用新的 canonical 名称体系（不做兼容层/弃用期）。

## Options

### Option 1: 仅修补 patch 命名（不改 module root）

- 保持 `scalim.dsl.by_yaml` 不变，只把 patch 表面收敛：
  - `WorkflowRunPatch` → `WorkflowRunOptionsPatch`
  - `run_patches_by_id` → `run_options_patches_by_run_id`
- **优点**：变更面最小。
- **缺点**：`by_yaml` 的“实现味”仍然存在；`run/compile` 的通用性问题仍然依赖读者记住上下文。

### Option 2 (Recommended): canonical facade 改为 `scalim.dsl.yaml_dsl`，动词保持短

- 以 `scalim.dsl.yaml_dsl` 作为唯一推荐入口；`run/compile` 保持短动词：
  - `yaml_dsl.run(...)` / `yaml_dsl.compile(...)` / `yaml_dsl.run_workflow(...)`
- patch 命名同时收敛为 `RunOptions patch`（解决 patch vs options 的关系不可见问题）。
- **优点**：整体认知最自然(模块名表达领域、动词保持简洁)；后续新增 knobs 不会继续扩大函数签名或引入新的命名漂移。
- **缺点**：需要一次性迁移大量 import 路径（但本提案明确不计破坏性成本）。

### Option 3: canonical facade 改为 `scalim.dsl.yaml_dsl`，并把动词也语义化

- 在 Option 2 基础上，把动词也变得更明确：
  - `run` → `run_demand`
  - `compile` → `compile_demand`
- **优点**：即使脱离模块上下文（例如 `from ... import run_demand`）也清晰。
- **缺点**：API 更啰嗦；且会引入“是否也要暴露 `compile_workflow`”等连锁讨论。

本变更建议先落地 Option 2；Option 3 作为后续可选增量(通过 alias 或主名切换)。

## High-Frequency Naming Inventory (Proposal)

以下清单聚焦“用户高频使用/看到”的入口与类型（curated stable surface），并在同一表格中表达问题与 Option 2 的推荐命名。

### Module Paths

| Current | Problem | Option 2 (Recommended) |
| --- | --- | --- |
| `scalim.dsl.by_yaml` | `by_yaml` 更像实现细节而非领域名 | `scalim.dsl.yaml_dsl` |
| `scalim.dsl.by_yaml.workflow` | 同上 | `scalim.dsl.yaml_dsl.workflow` |
| `scalim.dsl.by_yaml.workflow_types` | 同上 | `scalim.dsl.yaml_dsl.workflow_types` |
| `scalim.dsl.by_yaml.workflow_paths` | 同上 | `scalim.dsl.yaml_dsl.workflow_paths` |
| `scalim.dsl.by_yaml.tools` | 同上 | `scalim.dsl.yaml_dsl.tools` |
| `scalim.dsl.by_yaml.workflow_entrypoints` | 内部实现路径容易被误当作“官方入口” | `scalim.dsl.yaml_dsl.workflow_entrypoints`（仅作为实现模块；官方示例优先用 facade） |

### Symbols / Types (Facade)

| Current | Problem | Option 2 (Recommended) |
| --- | --- | --- |
| `run` / `compile` | 动词通用，但在 `yaml_dsl.*` 语境下可接受 | 保持：`yaml_dsl.run` / `yaml_dsl.compile` |
| `run_workflow` | 已足够具体 | 保持：`yaml_dsl.run_workflow` |
| `RunOptions` / `RunOverrides` / `RunResult` | 名字通用，但与模块语境绑定即可 | 保持不变（从 `scalim.dsl.yaml_dsl` 导入） |

### Workflow Per-run Patches

| Current | Problem | Option 2 (Recommended) |
| --- | --- | --- |
| `WorkflowRunPatch` | 看不出这是对 `RunOptions` 的 patch | `WorkflowRunOptionsPatch` |
| `run_patches_by_id` | `id` 语义不清晰；且看不出 patch 作用对象 | `run_options_patches_by_run_id` |
| `ComponentsInherit/Replace/Extend` | 看起来像“真组件类型”，不像 patch 策略 | 保留现名或重命名为 `ComponentsPatchInherit/Replace/Extend`（备选；待 review） |

### Optional Aliases (Non-blocking)

| Alias | Reason |
| --- | --- |
| `run_demand = run` | 允许在脱离模块上下文时保持可读性（例如 wrapper 代码 `from scalim.dsl.yaml_dsl import run_demand`） |
| `compile_demand = compile` | 同上 |

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `dsl-runtime-structure`: YAML DSL 的 canonical facade 从 `IMPL_ROOT.dsl.by_yaml` 收敛为 `IMPL_ROOT.dsl.yaml_dsl`。
- `public-api-surface-governance`: curated public surface 目录与门禁随 canonical facade 更新。
- `yaml-dsl-workflow`: workflow 相关的 curated stable entrypoints 更新为 `scalim.dsl.yaml_dsl.*`。
- `yaml-dsl-cli-runner`: spec 中对 Python 入口的引用更新为 `scalim.dsl.yaml_dsl.*`（CLI tooling-only 定位不变）。
- `yaml-dsl-public-tools`: tools 稳定入口从 `scalim.dsl.by_yaml.tools` 迁移为 `scalim.dsl.yaml_dsl.tools`。
- `workflow-run-patches`: per-run patch 的命名显式化为 `RunOptions patch`，并更新参数名。
- `yaml-dsl-output-overrides`: `RunOverrides` 的稳定导入路径更新为 `scalim.dsl.yaml_dsl`。

## Impact

- 受影响代码：
  - `src/scalim/dsl/by_yaml/**` 的 public facade/curated modules（迁移到 `src/scalim/dsl/yaml_dsl/**`，或通过新 facade 转发并最终移除旧路径）
  - `src/scalim/cli/yaml_dsl.py` 与所有 wrapper/示例导入
  - 治理脚本：public surface manifest + examples gate + user-material import boundary gate
- 受影响 specs/docs/notebooks/skills：
  - OpenSpec: 多个 spec 中写死的 `scalim.dsl.by_yaml.*` 文案与场景需要迁移到 `scalim.dsl.yaml_dsl.*`
  - Docs/skills/notebooks 需要全局替换导入路径（建议用 AST-aware 工具/IDE 重构）
- 生成物治理（SSOT）：
  - 任何 `*.gen.*` 文件与 `BEGIN/END AUTOGEN:*` 区块禁止手工编辑；若改动触发文档注入或生成页变更，必须修改 SSOT 并运行 `just gen-docs`。
  - OpenSpec 工件必须通过 `just openspec-check`。
