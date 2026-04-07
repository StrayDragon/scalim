## Context

本变更是一个“后置提案”：在 YAML DSL 的 runtime knobs 已经通过 `RunOptions` 收敛后，我们希望进一步把 **用户高频使用的 Python public API 命名体系**（模块路径、关键类型、关键参数名）做一次激进一致化。

当前主要问题：

- `scalim.dsl.by_yaml` 的模块名偏实现细节，且与 OpenSpec 能力命名(`yaml-dsl-*`)不一致。
- workflow per-run patch 的真实语义是：在 `run_workflow(..., options=RunOptions(...))` 的 base options 上应用 per-run patch，但命名(`WorkflowRunPatch`、`run_patches_by_id`)不显式表达它是 “RunOptions patch”。
- 命名漂移会放大维护成本：spec/docs/skills/examples/tests 必须持续同步；一旦把内部实现路径误写成公开入口，会被 gate 固化为事实 API。

约束：

- 运行时需兼容 Python 3.6（尤其是 import-time 兼容性 smoke gate）。
- 本变更不考虑兼容层/弃用期：允许破坏性全局重命名。
- 必须避免循环导入：新的 facade/转发层应保持单向依赖，不得把 workflow/framework 反向拉入 runtime。
- 文档治理规则不变：任何 `*.gen.*` 与 injected blocks 禁止手工编辑；需通过 SSOT + `just gen-docs` 更新。

## Goals / Non-Goals

**Goals:**

- 以 `scalim.dsl.yaml_dsl` 作为 YAML DSL 的 canonical public facade（取代 `scalim.dsl.by_yaml`）。
- 用命名直接表达关键关系：workflow per-run patch 是对 `RunOptions` 的 patch。
- 保持用户心智：`run/compile` 默认指 demand；workflow 入口仍为 `run_workflow`。
- 降低长期 drift 风险：spec/docs/gates 只承认一套 canonical 名称体系。

**Non-Goals:**

- 不改 YAML authoring surface（例如不把 `workflow.runs` 改为 `workflow.nodes`；不引入新的 YAML 字段）。
- 不在本变更中新增新的 runtime knobs 或新的扩展点（例如 per-run sink_factory）。
- 不要求一次性物理重命名所有内部实现文件/目录；本变更聚焦 public API 的命名一致性（内部实现可用转发/alias 逐步收敛）。

## Decisions

### Decision 1: canonical public facade 为 `scalim.dsl.yaml_dsl`

对用户侧的推荐导入与示例一律收敛到：

- `scalim.dsl.yaml_dsl`
- `scalim.dsl.yaml_dsl.workflow`
- `scalim.dsl.yaml_dsl.workflow_types`
- `scalim.dsl.yaml_dsl.workflow_paths`
- `scalim.dsl.yaml_dsl.tools`

实现策略允许两阶段：

1. **先引入新 facade（推荐）**：新增 `src/scalim/dsl/yaml_dsl/` 作为薄转发层，内部仍复用既有 `by_yaml` 实现；并将所有用户材料/gates/suite 切换到新路径。
2. **再收敛内部实现（可选）**：视重构成本决定是否将 `src/scalim/dsl/by_yaml/` 物理改名/迁移为 `yaml_dsl`（或保留其为 internal impl 包并最终移除旧路径）。

理由：把 “public naming” 与 “内部目录结构” 解耦可以显著降低循环导入风险与重构顺序依赖；同时保证用户侧认知一口径。

### Decision 2: 保持短动词 `run/compile`，并允许可选别名

- `run/compile` 继续作为 facade 的主入口动词（在 `yaml_dsl.*` 的语境下已足够明确）。
- 可选增加别名（不阻塞主变更）：
  - `run_demand = run`
  - `compile_demand = compile`

理由：既满足“默认心智 run/compile = demand”，也给 wrapper/集成代码提供更明确的可选导入形态。

### Decision 3: workflow per-run patch 命名显式化为 RunOptions patch

将以下高频名字收敛为自解释关系：

- `WorkflowRunPatch` → `WorkflowRunOptionsPatch`
- `run_patches_by_id` → `run_options_patches_by_run_id`

并在 spec 与 docstring 中明确语义：

`effective_run_options = apply_patch(base_options, per_run_options_patch)`

### Decision 4: 通过 AST-aware/IDE 重构实现全局替换（而非纯文本替换）

实现阶段推荐以语义化工具完成重命名（如 ast-grep、JetBrains rename、Python LSP rename），避免：

- import string 的误替换（docstring/Markdown/注释 vs 真实导入）
- symbol shadowing 导致的误命中
- 路径字符串（例如错误信息）被错误替换

### Decision 5: 文档与生成物治理边界明确

- OpenSpec 的 delta specs 为 SSOT（本 change 目录内的 `proposal/design/specs/tasks` 手工维护）。
- `docs/doc/**/*.gen.*` 与 injected blocks 为生成物：不得手改；必须通过 SSOT 修改并运行 `just gen-docs` 刷新。

## Risks / Trade-offs

- [大规模重命名] → 通过“先 facade 再内部实现”的分层策略降低一次性变更面；同时依赖治理门禁(`just qa`)兜底。
- [循环导入/导入成本] → 新 facade 采用与现有 `by_yaml.__init__` 类似的“受控 re-export +（必要时）延迟 import”策略；保持依赖方向单向。
- [spec/docs drift] → 在 tasks 中显式列出需要更新的 spec/用户材料/门禁脚本，并以 `just openspec-check` + `just qa` 作为验收口径。

## Migration Plan

1. 引入 `scalim.dsl.yaml_dsl` 以及其 curated 子模块（薄转发层）。
2. 全局迁移用户材料与 public API suite 到新导入路径（docs/skills/notebooks/tests）。
3. 重命名 workflow patch surface（类型名 + 参数名），并更新对应 spec 场景与示例。
4. 更新 public surface governance（manifest + import smoke + user-material boundaries）。
5. 运行门禁：
   - `just openspec-check`
   - `just qa`

## Open Questions

- `WorkflowRunOptionsPatch` 的字段命名是否需要进一步与 `RunOptions` 对齐（例如 `demand_failure_policy` 是否应更名为 `failure_policy`，或保持现状以避免与 workflow failure_policy 混淆）？
- `by_yaml` 路径是否完全移除，还是保留为 internal-only alias（不写入任何用户材料与 spec），用于降低内部目录迁移成本？
