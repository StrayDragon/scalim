## ADDED Requirements

### Requirement: validate and schema validate MUST catch known fail-late cases consistently
系统 MUST 确保 `scalim-cli yaml-dsl validate` 与 `scalim-cli yaml-dsl schema validate` 对下列形态给出一致的失败结果(非零退出码),且错误信息可定位到对应路径:

- `sources` 出现非法 mapping key(空 key 或不匹配 identifier pattern)
- `main_source.loader` / `sources.*.loader` 为空字符串
- `sources.*.key` 为空字符串(或列表包含空字符串)
- `retry.enabled=true` 且缺失/为空 `should_retry`(在 CLI 校验上下文中;提示可由 driver injection 提供)
- `outputs.*.container.streaming=false`
- detail output(未声明 aggregate)缺失 `fields` 且缺失 `from`

#### Scenario: validate fails early instead of compile-time failure
- **GIVEN** 某 demand YAML 含上述任一错误形态
- **WHEN** 用户执行 `scalim-cli yaml-dsl validate <file.yaml>`
- **THEN** 命令 MUST 失败
- **AND** 错误 MUST 指向对应逻辑路径(例如 `sources.orders.key`, `outputs.0.container.streaming`)
