## 1. Runtime overrides v2(输出覆盖)

- [ ] 1.1 在 `src/scalim/dsl/by_yaml/runtime/contracts.py` 中重设计 `RunOverrides` 以支持 `overrides.outputs`(YAML-shaped list/mapping;仅承诺 `name/container/fields`)
- [ ] 1.2 在 `src/scalim/dsl/by_yaml/runtime/entrypoints.py` 的 `run/compile` 中接入 `overrides.outputs` 并明确优先级: `overrides.outputs` > YAML `outputs` > 默认(无文件写出)
- [ ] 1.3 在 `src/scalim/dsl/by_yaml/runtime/compiler.py` 中复用现有 `outputs` 编译链路将 `overrides.outputs` 编译为 execution 层输出编排对象(避免维护两套语义)
- [ ] 1.4 破坏性移除 `overrides.output.*` 契约(从 `RunOverrides`/入口签名中删除,让旧调用在构造期 `TypeError` fail-fast)
- [ ] 1.5 破坏性移除 `output_composition` 运行期注入扩展点(从 `RunOptions`/`run/compile`/`unsafe_*`/`workflow_entrypoints` 等路径中删除)
- [ ] 1.6 为 `overrides.outputs` 的非法输入提供可诊断错误(至少包含逻辑路径,例如 `overrides.outputs[0].container.type`);并对不支持的 keys(`where/from/aggregate`)给出明确报错

## 2. 字段展示名唯一性预检查(默认启用)

- [ ] 2.1 在 `src/scalim/dsl/by_yaml/schema_dsl/models/**` 增加顶层 `validate_unique_field_names`(boolean) 并定义 hover 文案(SSOT;说明仅在 `header_fields_output_by: name` 时触发)
- [ ] 2.2 将 `outputs[*].container.header_fields_output_by` 默认值改为 `name`(SSOT: `DEFAULT_OUTPUT_HEADER_BY`),并同步更新 schema examples/hover
- [ ] 2.3 运行 `just gen-yaml-dsl-schema` 生成 `src/scalim/dsl/by_yaml/schema/demand.gen.json` 并通过 `tests/test_yaml_schema_generation.py` 漂移门禁
- [ ] 2.4 在 `src/scalim/dsl/by_yaml/config_parsing/validator.py` 实现“有效展示名”唯一性校验(默认启用;仅当 YAML `outputs` 使用 `header_fields_output_by: name` 时触发;开关为 false 时跳过)
- [ ] 2.5 在 `src/scalim/dsl/by_yaml/runtime/compiler.py` 中实现同一校验,但触发条件基于 effective outputs(含 `overrides.outputs`),以保证运行期动态输出也能 fail-fast
- [ ] 2.6 为该校验补齐单测(冲突报错/关闭开关可通过),并确保错误信息包含冲突展示名与相关字段定位信息

## 3. 公共表面收敛与文档迁移

- [ ] 3.1 将 docs/examples 的标准写法统一升级为“demand YAML 默认不声明 `outputs` + 调用侧 `overrides.outputs` 指定单输出 Excel 单 sheet”(避免模板 workaround 作为主路径)
- [ ] 3.2 统一移除 docs/examples 中任何 Python-only `output_composition` 注入路径,并确保对外叙事仅保留 YAML `outputs` 与 `overrides.outputs`
- [ ] 3.3 若涉及 docs-site 生成页或注入区块,修改对应 SSOT 并运行 `just gen-docs`(禁止手改 `.gen.*` 与 `BEGIN/END AUTOGEN:*` 区块内部)

## 4. 验收与回归门禁

- [ ] 4.1 补齐 `overrides.outputs` 的最小回归用例(至少覆盖: 单 workbook/单 sheet/字段顺序/表头策略)
- [ ] 4.2 运行 `just qa` 确认 lint/tests 与 drift checks 通过
- [ ] 4.3 运行 `just openspec-check` 确认 OpenSpec artifacts sanitize + validate 通过
