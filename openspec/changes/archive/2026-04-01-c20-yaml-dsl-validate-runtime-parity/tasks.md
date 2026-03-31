## 1. Review Gate (Maintainer)

- [x] 1.1 维护者确认本 change 的目标是“fail-late -> fail-fast”,且不要求兼容放行
- [x] 1.2 维护者确认本 change 覆盖的具体 fail-late 清单(见 proposal 的 What Changes),并确认拆分边界(不包含 path 表达格式统一)

## 2. Schema SSOT: sources/retry/outputs 约束下沉

- [x] 2.1 更新 schema_dsl SSOT: 为 `main_source.source_id` 与 `sources` keys 增加 identifier pattern(SSOT=`src/scalim/dsl/by_yaml/schema_dsl/models/**`; `sources` 的 propertyNames 需同时允许 `$import`)
- [x] 2.2 更新 schema_dsl SSOT: `main_source.loader` / `sources.*.loader` 增加非空约束,`sources.*.key` 拒绝空字符串
- [x] 2.3 更新 schema_dsl SSOT: `retry.should_retry` 显式提供时必须为非空字符串(不在 schema 中强制 `enabled=true -> should_retry`,以保留 driver injection 场景)
- [x] 2.4 更新 schema_dsl SSOT: `outputs.*.container.streaming` 限制为 const true(缺省允许;显式提供时必须为 true)
- [x] 2.5 更新 schema_dsl SSOT: detail outputs 增加 `fields`/`from` 结构性约束(建议通过 `OutputTargetConfig.SCHEMA_ALL_OF` 表达;需显式允许 `$import`-only output_target 通过 schema)
- [x] 2.6 生成并校验 schema 生成物漂移: SSOT=`src/scalim/dsl/by_yaml/schema_dsl/**`; 生成入口=`just gen-yaml-dsl-schema`; 验收=`just schema-drift-check`

## 3. Semantic Validate Parity (ConfigValidator)

- [x] 3.1 更新内部语义 validator: 对 sources keys 做 identifier pattern 校验并产出可定位 issue
- [x] 3.2 更新内部语义 validator: `loader/key` 空值 fail-fast,并给出稳定 path(注意: 当前实现对“字段存在但为空字符串/空白”会放行,需补齐)
- [x] 3.3 更新内部语义 validator: outputs 语义不变量在 validate 阶段可定位失败(与 parser/runtime 文案对齐)
- [x] 3.4 CLI validate: 对 `retry.enabled=true` 且缺失/为空 `should_retry` fail-fast(提示可由 driver injection 提供);该规则**仅在 CLI 层实现**,不得下沉到共享 `ConfigValidator`/schema(避免破坏 runtime compile 的 driver injection 用例)
- [x] 3.5 CLI schema validate: 补充同样的 retry 完整性检查(因为该约束不下沉到 schema,避免破坏 driver injection)

## 4. Tests

- [x] 4.1 新增/更新 fixtures: 覆盖 sources key 非法/空 loader/空 key/retry 缺 should_retry/streaming=false/detail 缺 fields
- [x] 4.2 更新/新增 CLI 回归测试: `yaml-dsl validate` 与 `schema validate` 对上述形态一致失败且路径稳定

## 5. Quality Gates

- [x] 5.1 运行 `just openspec-check` 确保 OpenSpec 工件一致性
- [x] 5.2 运行 `just qa` 通过 lint/tests + drift checks
