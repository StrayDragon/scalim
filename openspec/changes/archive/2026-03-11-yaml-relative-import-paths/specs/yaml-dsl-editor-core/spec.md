## ADDED Requirements

### Requirement: 编辑器对相对模块引用提供一致提示
系统 MUST 在编辑器中对 `main_source.loader` / `sources.*.loader` / `fields.*.call_by` / `*.retry.should_retry` 等引用字段提供与 canonical schema 一致的 hover/补全提示,并确保相对模块引用语法 `.` / `..` 不会被前端链路误判为非法格式。

#### Scenario: 编辑器 hover 可见相对引用示例
- **WHEN** 用户在编辑器 hover 查看 `main_source.loader`
- **THEN** hover 文案 MUST 展示相对引用示例(例如 `.loaders:load_orders`)
