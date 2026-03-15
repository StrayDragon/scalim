**状态: TODO**

## 8. Custom Aggregates (outputs.*.aggregate)

- [ ] 8.1 更新 YAML schema/models 以允许 aggregate `kind/ref` + `options/config`(保持内置 group_by 兼容):
  - `src/scalim/dsl/by_yaml/schema_dsl/models/outputs.py`:
    - 扩展 `OutputAggregateConfig` 以表达:
      - 内置 `group_by` 形态(现状)
      - 自定义 kind: `aggregate.kind` + `aggregate.options`
      - 自定义 ref: `aggregate.ref` + `aggregate.config`
    - 确保 schema-only 校验可通过(见本 change 的 yaml-dsl-schema spec)
- [ ] 8.2 定义并实现 custom aggregate factory 的返回契约并编译:
  - 建议在 `src/scalim/dsl/by_yaml/runtime/` 新增轻量编译帮助(例如 `compile_custom_aggregate(...)`):
    - 输入: kind/ref + options/config + `ExtensionHost`/resolver + yaml_path
    - 输出: `{derived: IDerivedAggregationSpec, output_field_ids: Tuple[str, ...]}`(或等价 dataclass)
  - kind 路径: 从 `ExtensionHost.aggregate_kind_factories` 查找并调用
  - ref 路径: 通过 `SecurePythonReferenceResolver` 解析并调用
  - 任意失败必须包含可行动上下文(至少 yaml_path + kind_id/ref)
- [ ] 8.2.1 required_fields 注入必须发生在字段裁剪前:
  - 在 YAML outputs 解析阶段(产生 required_field_ids 的位置)编译 custom aggregate 并调用 `derived.required_fields()`
  - 将其结果并入 required_field_ids,确保 fields parse/IR 构造阶段不会因字段裁剪缺失依赖
  - 预计落点: `src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py`(需要 extensions-aware 的上下文/registry)
- [ ] 8.3 并发边界校验(fail-fast):
  - 在装配阶段调用 `IDerivedAggregationSpec.validate_parallel_mode(parallel_mode)`
  - `parallel_mode` 来源为 `ExecutionRequest.parallel_mode`/RunOptions
  - 建议落点: 构造 `OutputCompositionSpec` 时或 `build_request(...)` 时(避免 run 中途才报错)
- [ ] 8.4 回归测试(端到端):
  - `tests/fixtures/extensions_aggregates_mod.py` 提供可 allowlist 引用的 custom aggregate kind/ref:
    - 返回 `IDerivedAggregationSpec`(可复用现有 `DerivedGroupBySpec`/或实现最小自定义 spec)
    - 同时提供 `output_field_ids`
    - 可选: 对某个 `parallel_mode` 明确抛错以测试 fail-fast
  - `tests/test_yaml_dsl_extensions_custom_aggregates.py` 覆盖:
    - kind/ref 形态可被编译并产生派生输出
    - `required_fields()` 注入生效(不会因字段裁剪缺字段)
    - `parallel_mode` 不支持时在装配阶段 fail-fast 且错误包含 kind/ref

## Gates

- [ ] `just qa`
- [ ] `just openspec-check`
