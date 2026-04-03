## 1. YAML DSL schema (SSOT + 生成物)

- [ ] 1.1 在 `src/scalim/dsl/by_yaml/schema_dsl/models/source.py` 扩展 `NormalizeConfig`: 新增 `on_none: raise|skip`(默认 `raise`,仅对 `index_by_key` 有意义)
- [ ] 1.2 在 schema SSOT 中表达约束: 仅当 `normalize.kind=index_by_key` 时允许 `normalize.on_none`(其它 kind MUST 被拒绝,不得静默忽略)
- [ ] 1.3 运行 `just gen-yaml-dsl-schema` 重新生成 `src/scalim/dsl/by_yaml/schema/*.gen.json` 等生成物(禁止手工编辑 `*.gen.*`)
- [ ] 1.4 验收: 运行 `just schema-drift-check` 确认生成物无 drift

## 2. YAML 配置校验与转换

- [ ] 2.1 更新 `src/scalim/dsl/by_yaml/_internal/config_parsing/validators/sources.py`: 当 `normalize.kind!=index_by_key` 且出现 `on_none` 时 fail-fast,错误信息包含字段路径与修复建议
- [ ] 2.2 更新 `src/scalim/dsl/by_yaml/runtime/_internal/conversion_sources.py`: 将 `normalize.on_none` 传递到 IR/runtime(保持默认 `raise`)

## 3. IR normalize runtime

- [ ] 3.1 更新 `src/scalim/spec/ir/_sources.py` 的 `index_by_key` 归一化逻辑: 遇到 `key_field is None` 时按 `on_none` 执行 `raise|skip`
- [ ] 3.2 确认边界不变: `key_field` 缺失仍 fail-fast; `key_value` 非 hashable 仍 fail-fast; duplicate key 仍按 `on_conflict` 处理
- [ ] 3.3 统一 fail-fast 错误信息: 包含 `source_id` + 配置路径(例如 `sources.<id>.normalize.key_field`) + row index;当 `key_field is None` 且 `on_none=raise` 时明确提示可用 `sources.<id>.normalize.on_none: skip`
- [ ] 3.4 增加 `on_none=skip` 可观测性: 统计 `skipped_none_rows` 并将其暴露到 `loader_call` 事件 payload 的可选字段(避免仅依赖 `Event.meta`,以便 typed observers/scalim-viz 可读取)

## 4. Tests

- [ ] 4.1 为默认行为补充测试: `index_by_key` 遇到 `None` key 时仍 fail-fast(未设置 `on_none` 或 `on_none=raise`)
- [ ] 4.2 新增测试: `on_none=skip` 时跳过 `key_field is None` 的 row 且输出 mapping 不包含该 key
- [ ] 4.3 新增测试: validator 拒绝非 `index_by_key` 下的 `normalize.on_none`
- [ ] 4.4 新增测试: `on_none=skip` 时 `loader_call` 事件 payload 包含 `skipped_none_rows`(或等价字段)且数值正确

## 5. Quality gates

- [ ] 5.1 运行 `just qa`(含 lint/tests + drift checks + OpenSpec checks)
- [ ] 5.2 若仅需校验 OpenSpec 工件: 运行 `just openspec-check`
