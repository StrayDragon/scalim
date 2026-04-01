## Why

当前 YAML DSL 的“可写配置面”明显偏宽：同一能力同时存在于 JSON Schema、YAML authoring、Python `RunOptions/RunOverrides`、以及 CLI/runtime 隐式默认中，导致：
- 维护成本高（schema/validator/runtime/docs 的漂移点多，尤其是 `$import`、runtime policy、observability）。
- 用户心智负担大（大量布尔开关/阈值/枚举/万能桶对象；且存在多入口与隐式 fallback）。
- 破坏性改动难做（历史包袱与双入口让“收敛”变成长期拖尾工程）。

本 change 以 **C0-（允许破坏性）** 为前提，提出一次性收敛方案，并把后续 YAML DSL 演进的 **SSOT 与组织原则** 固化下来，避免继续扩张。

## What Changes

- 定义并落地 “YAML authoring 核心面 vs runtime control plane” 的边界：
  - YAML 仅承载 **核心业务建模**（sources/fields/relations/outputs 等）与少量可移植的 IO 声明。
  - 运行时策略类配置（retry/guardrails/observability/diagnostics 等）迁移到 **Python API / CLI / profile**，避免 YAML 变成控制面。
- **BREAKING**：收敛/隐藏一批历史债务与低频高复杂度配置面（以保持 YAML 可读、可维护为优先），并提供迁移路径：
  - 收敛大量布尔开关为更少的稳定语义入口（prefer enum / presence / profile）。
  - 数值阈值从“细粒度裸露”转向“分层默认 + 少量可调旋钮”。
- 统一 demand/workflow 的重复建模：
  - 资源 IO（books/files）的结构与覆盖语义对齐：明确哪一层是声明、哪一层是 overlay。
  - 输出写入策略（write / write_defaults / meta/audit）合并与去重，减少“同一语义多处可配”。
- 修复并建立 drift gate：schema/runtime/docs 不一致视为 P0 缺陷（典型：workflow schema 暴露 `$import` 但 runtime parser 不支持）。
- 设定 YAML DSL 未来组织风格 SSOT：
  - **KV-first**：凡是需要稳定 ID/引用/复用的结构优先 mapping；仅当顺序语义不可替代时使用 list（例如 runs、relation steps、outputs）。
  - 统一 overlay/import 规则：避免 “YAML `$import` + YAML anchor + Python overrides + runtime fallback” 多套叠加语义同时存在且互相可替代。

## Capabilities

### New Capabilities
- `yaml-dsl-vnext-surface`: 定义 vNext YAML authoring 核心面、组织原则（KV-first vs list-first 的裁决）、以及“哪些配置不再属于 YAML”的边界与迁移要求。

### Modified Capabilities
- `yaml-dsl-schema`: schema 作为编辑器提示与结构校验的 SSOT 需要随 vNext 收敛（并新增 drift gate，避免 schema/runtime 漂移）。
- `yaml-dsl-workflow`: workflow YAML 的 schema/runtime/validator 对齐；明确 workflow 层允许/禁止的配置面（尤其是 imports/$import 与 resources）。
- `yaml-dsl-imports`: imports/$import 的可用范围、支持矩阵与安全/治理边界需要与 vNext 重新收敛。
- `yaml-dsl-output-overrides`: YAML outputs 与 typed `RunOverrides.outputs` 的分层与优先级在 vNext 下需要明确，避免重复建模与文档歧义。

## Impact

- 影响面：`src/scalim/dsl/by_yaml/schema_dsl/**`、`src/scalim/dsl/by_yaml/schema/*.gen.json`（生成物）、demand/workflow loader/validator、`scalim-cli yaml-dsl *`、docs/examples/notebooks 的推荐用法与迁移提示。
- 迁移风险：破坏性收敛将改变 YAML authoring 的可写面（尤其 runtime policy/observability/diagnostics 类）；需要提供 `upgrade`/lint/compat 层与明确 deprecation 时间线。
- 附录：完整 schema 配置清单已生成（基于当前 `*.gen.json`）：`appendices/schema-inventory-demand.tsv`、`appendices/schema-inventory-workflow.tsv`。

