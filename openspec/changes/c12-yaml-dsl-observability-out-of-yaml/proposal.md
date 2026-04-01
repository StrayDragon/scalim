## Why

`observability.*` 是当前最明确的 control-plane 候选之一:

- 量大、组合复杂、布尔开关多
- 与 Python 入口的 `components` / `viz_config` 已有明显重叠
- 用户还可能接入自定义 hook / observer / 组织内部观测工具

这类能力天然更像运行入口集成面,而不是可复用的 authoring DSL。

## What Changes

- 将 YAML 中的 `observability.*` 从主线 authoring surface 中移出
- 统一收口到 Python / CLI 的 typed runtime entrypoints
- 为旧 YAML 使用方式提供明确 migration hint

## Scope

包括:
- `observability.*` 在 YAML 主线中的去留边界
- Python/CLI 侧承载面的预期职责
- 文档与示例口径调整

不包括:
- 重设计 observability runtime/observer 体系本身
- 处理其它 runtime policy (`guardrails` / `retry`) 的最终策略

## Expected Outcome

- YAML 主线更聚焦业务建模
- 用户在运行入口侧集成自定义 hook/observer 的路径更清晰
- schema/imports/LSP 不再被一大块观测配置面拖复杂
