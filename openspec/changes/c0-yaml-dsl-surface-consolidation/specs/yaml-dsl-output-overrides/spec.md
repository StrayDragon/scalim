# yaml-dsl-output-overrides Delta Specification (c0-yaml-dsl-surface-consolidation)

## ADDED Requirements

### Requirement: typed overrides MUST cover vNext runtime-only output extras

当 vNext demand YAML 不再暴露 `meta/audit` 等“输出附加 sheet/审计信息”控制面时，系统 MUST 提供稳定的 typed overrides 入口，以保持 YAML-only 与 Python-driver 两种使用方式都可表达。

系统 MUST 在 `RunOverrides`（稳定从 `scalim.dsl.by_yaml` 导入）中提供一个结构化字段（名称不限，但 MUST 为 typed dataclass），用于启用/配置：
- `meta` extra sheet
- `audit` extra sheet

#### Scenario: overrides enables meta sheet without editing YAML
- **GIVEN** vNext demand YAML 未声明 `meta`
- **WHEN** 调用方通过 `RunOverrides` 启用 meta extra sheet
- **THEN** 本次运行 MUST 产生包含 meta sheet 的输出

#### Scenario: overrides enables audit sheet without editing YAML
- **GIVEN** vNext demand YAML 未声明 `audit`
- **WHEN** 调用方通过 `RunOverrides` 启用 audit extra sheet
- **THEN** 本次运行 MUST 产生包含 audit sheet 的输出

