## 1. SSOT 枚举模块

- [ ] 1.1 新增 `src/scalim/dsl/by_yaml/schema_dsl/output_enums.py`（Python 3.6 兼容）并定义 `AGG_METRIC_PRODUCER_KEYS/AGG_RANK_PRODUCER_KEYS/AGG_POST_PRODUCER_KEYS`
- [ ] 1.2 为 SSOT 常量补齐最小文档字符串与导出列表（避免被误当作内部变量）

## 2. 迁移重复常量

- [ ] 2.1 `src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py` 删除本地 `_AGG_FUNC_KEYS/_RANK_FUNC_KEYS/_POST_FUNC_KEYS` 等重复枚举，改为从 SSOT 导入
- [ ] 2.2 `src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py` 删除本地 `_AGG_FUNC_KEYS/_RANK_FUNC_KEYS`，改为从 SSOT 导入
- [ ] 2.3 `src/scalim/dsl/by_yaml/runtime/introspection.py` 删除本地 `_AGG_FUNC_KEYS/_RANK_FUNC_KEYS`，改为从 SSOT 导入（工具层默认策略若需要子集，必须基于 SSOT 组合）

## 3. 防漂移护栏（回归测试）

- [ ] 3.1 新增单元测试：断言 parser/runtime/introspection 使用同一份枚举集合（至少集合一致；可选更强：引用同一对象）
- [ ] 3.2 若发现当前三处行为存在“有意差异”，在测试中写清差异的理由并固定（避免再次漂移）

## 4. 验收

- [ ] 4.1 运行 `just qa`（或最小子集）确保无 lint/test 回归
- [ ] 4.2 运行 `just openspec-check` 确保 OpenSpec 工件通过校验
