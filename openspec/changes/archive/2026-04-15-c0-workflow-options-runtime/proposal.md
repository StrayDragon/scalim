## Why

当前 workflow YAML 会把一组明显“环境敏感”的运行期策略（例如 `max_concurrency`、`failure_policy`、`ctx` 护栏、`cache_pool` 预算/回收策略）写死在 `workflow.options` 里。实际使用中这些参数往往需要随开发/CI/生产环境切换，导致调用方不得不通过 override/复制 YAML 等方式覆盖，破坏 SSOT 并显著增加维护与反馈成本。

我们已经有“runtime policy boundary”的先例（demand 的多项 runtime knobs、workflow 的 `resources_wait` / `output_staging` 已迁出 YAML）。现在需要把 workflow 剩余的环境敏感 knobs 也迁出 YAML 主线，收敛到 Python/CLI runtime entrypoints 的 typed surface。

## What Changes

- **BREAKING**：workflow YAML 不再允许声明 `workflow.options`（该段落整体迁出为 runtime policy）。

同时，为了迁移提示更明确，系统 MUST fail-fast 拒绝以下旧字段（并指向 runtime entrypoints）：
  - `workflow.options.max_concurrency`
  - `workflow.options.failure_policy`
  - `workflow.options.ctx`（含其所有子字段）
  - `workflow.options.cache_pool`（含其所有子字段）
- 系统 MUST 在 workflow YAML parse/validate 阶段 fail-fast 拒绝上述字段，并给出迁移指导（指向 Python/CLI runtime entrypoints）。
- `workflow.options.ctx` 将被移除，且 workflow ctx store 的“单值/总量”护栏逻辑将整体移除：框架不再对 ctx payload 做 size-limit 报错，内存与 payload 规模由调用方自行治理。
- 系统新增/扩展 workflow runtime entrypoints 的 typed 参数 `workflow_runtime_options=...`，使调用方可在 Python/CLI 侧配置 workflow-level runtime policy（核心编排 knobs 为 `max_concurrency` / `failure_policy`）；未显式提供时使用稳定默认值（与历史行为等价）。
- `workflow.options.resources_wait` / `workflow.options.output_staging` 已迁出 YAML；本变更将进一步把它们收敛到 `workflow_runtime_options`（不再散落为多个独立的运行入口参数），以保持外部接口受限且正交。
- **BREAKING**：`run_workflow(...)` 将移除/替换零散的 workflow-level runtime kwargs（例如 `workflow_resources_wait` / `workflow_output_staging`），统一由 `workflow_runtime_options` 承载。
- `cache_pool` 将保留为 workflow 能力，但 **配置面收口为 runtime-only preset**（避免外部接口过度开放）：
  - workflow YAML 中不再允许声明 `workflow.options.cache_pool`（fail-fast）。
  - runtime entrypoints 仅暴露极小 knobs（例如 `max_entries`：按 signature 计数的“最多缓存 entry 数量”，默认 `16`），其余策略固定为稳定默认（例如 `conflict_policy=error`、`release_policy=dag_refcount`、`over_budget_policy=fail_fast`）。
- workflow YAML 仍保留结构化编排信息（`workflow.runs`、`depends_on`、`resources`，以及现有允许留在 YAML 的结构性字段；详见 design）。

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `yaml-dsl-runtime-policy-boundary`: 将 workflow 的 `max_concurrency` / `failure_policy` / `cache_pool` 重新归类为 runtime policy，并迁出 YAML 主线；`ctx` 护栏不再作为可配置项；更新迁移提示与边界约束。
- `yaml-dsl-workflow`: 更新 workflow YAML 的可 authoring 字段集合与 schema-only 校验口径（移除上述字段）；并更新示例与用户侧入口指引（核心 workflow options 通过 runtime entrypoints 提供）。
- `workflow-cache-pool-safety`: `cache_pool` 的配置来源从 YAML 迁移为 runtime entrypoints（语义不变、仅改变 authoring surface）。
- `agent-skill-export`: 受控生成的 workflow 语法索引/CLI reference 不再把迁出的字段视为 YAML 主线语法（改为 runtime entrypoint 指引）。

## Impact

- **YAML 作者体验**：现有 workflow YAML 需要删除 `workflow.options`（含其子字段）；并在运行入口以 typed 参数提供等价配置。
- **Python API**：`scalim.dsl.yaml_dsl.run_workflow(...)`（及其稳定 facade）将新增 `workflow_runtime_options=...` 参数用于承载 workflow-level runtime policy；并收敛/替换现有零散的 workflow-level runtime kwargs（例如 `workflow_resources_wait` / `workflow_output_staging`）。下游集成需要更新调用方式。
- **CLI（如适用）**：如仓库内存在 workflow 运行 CLI，则需要提供对应 flags / 环境选择入口以注入 runtime policy。
- **生成物与漂移门禁**：
  - `src/scalim/dsl/yaml_dsl/schema/workflow.gen.json` 为生成物，schema 变更必须通过 SSOT + `just gen-yaml-dsl-schema` 生成。
  - agent skill references 为生成物，更新需通过 `just gen-agent-skill`，并由 `just qa` / drift-check gates 兜底。
