## Context

- `src/scalim/dsl/yaml_dsl/runtime/compiler.py` 与 `src/scalim/dsl/yaml_dsl/workflow_compile.py` 同时承担了:
  - outputs overrides 解析与校验
  - resources/books/files 的 IO-only overlay
  - output_extras 的 overlay
  - outputs_defaults.to.book 的默认绑定
- 两者在多个 helper 上存在重复实现(函数名与逻辑高度相似)。
- 异常类型不一致:
  - workflow 侧倾向抛 `ScalimWorkflowConfigError(message, path=...)`
  - runtime compiler 侧大量抛 `ValueError/TypeError`，缺少稳定 `path=`

## Goals / Non-Goals

Goals:
- 提取 override 解析/校验 SSOT 模块,让 demand 与 workflow 复用同一份实现。
- 统一对外异常: DSL 配置/override 相关错误一律抛 `ScalimWorkflowConfigError` 且携带稳定 `path=`。
- 把这一步做成后续大拆分(拆 workflow_compile.py)的“前置降耦”。

Non-Goals:
- 本 change 不拆分 `workflow_compile.py` 的其它职责(DAG 构建/运行时选项等)。
- 不改变 outputs/resources override 的语义(除错误类型/错误路径的外观一致性)。

## Decisions

1. 新增 `_internal` SSOT 模块
- 新模块候选: `src/scalim/dsl/yaml_dsl/_internal/resource_override.py` (名称与 `_REPORT.md` 建议对齐)。
- 模块职责:
  - 解析/校验 `RunOverrides.outputs/resources/outputs_defaults/output_extras`
  - 复用既有 SSOT 校验函数(例如 `validate_output_name`, `validate_excel_sheet_name` 等)
  - 仅依赖 runtime/contracts 与 schema_dsl models(避免依赖 workflow_compile)

2. 异常统一策略
- SSOT 模块内,遇到任何配置形状/类型/值错误,直接抛 `ScalimWorkflowConfigError(..., path=...)`。
- runtime/compiler.py 中:
  - 将原先的 `TypeError/ValueError` 改为直接抛 `ScalimWorkflowConfigError`
  - 对跨边界捕获的异常,保持 `raise ... from exc` 以保留 cause 链(符合 `execution-error-taxonomy` 规范)

3. 渐进式落地顺序(减少一次性大改风险)
- 第一步: 提取最明确的复制粘贴 helpers(例如 outputs_defaults/to.book、output_extras)
- 第二步: 提取 outputs override 的 parser/validator
- 第三步: 提取 resources override overlay

## Risks / Trade-offs

- [风险] BREAKING: 下游若捕获 `ValueError/TypeError` 判断 DSL 错误将需要迁移。
  - 缓解: 统一到一个 canonical 错误类型更易迁移(只改一次捕获点)。

- [风险] 大范围移动函数可能引入 import cycle。
  - 缓解: 新模块放在 `dsl/yaml_dsl/_internal` 且只依赖更底层的 runtime/contracts 与 schema_dsl models。

## Migration Plan

- 下游迁移建议:
  - 捕获 `ScalimWorkflowConfigError`
  - 使用 `.path` 或 message 中的 `(path=...)` 做定位

## Open Questions

- 是否需要为 runtime compiler 提供一个更稳定的“公共错误包装边界”(例如统一在 entrypoint 处 catch 并 wrap),以进一步减少内部 helper 的 `path` 传递成本?
> yes