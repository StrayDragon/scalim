## 1. Validator 与 conversion 对齐

- [x] 1.1 更新 YAML validator `src/scalim/dsl/by_yaml/_internal/config_parsing/validators/sources.py` 的 `index_by_key` 规则: `normalize.key_field` 允许缺失/空字符串并默认推导为 `sources.<id>.key`,同时保留显式 `key_field` 与 `key` 的强一致性校验与 composite key 拒绝策略。
- [x] 1.2 更新 YAML→IR conversion `src/scalim/dsl/by_yaml/runtime/_internal/conversion_sources.py` 的 `index_by_key` 转换: 计算 effective `key_field` 并填充到 IR,确保与 validator 缺省逻辑一致（避免 validate 通过但 runtime 编译失败）。

## 2. 测试与样例回归

- [x] 2.1 更新/补充 `tests/yaml_dsl/test_yaml_source_normalize.py`: 覆盖 `key_field` 省略默认取 `key`、显式一致、显式不一致 fail-fast、composite key fail-fast 四条路径。
- [x] 2.2 在实现通过后升级仓库内示例 YAML,移除 `index_by_key` 下冗余 `key_field`（不改语义,仅瘦身）:
  - `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/workflow_demo_big_data_report_detail_demand.yaml`
  - `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/ecommerce_report.yaml`

## 3. 文档/Schema 与验收门禁

- [x] 3.1 更新 YAML JSON Schema / editor hover 文案,显式强调 “`index_by_key` 下 `key_field` 可省略且默认取 `sources.<id>.key`”；如涉及 docs site 生成物,仅修改手工 SSOT 并运行 `just gen-docs` 刷新生成物,禁止手工编辑任何 `.gen.` 文件或 `BEGIN/END AUTOGEN` 注入区块。
- [x] 3.2 运行 `just openspec-check` 校验本 change 工件,并执行与本变更相关的 targeted tests（例如 `pytest -k normalize` 或相邻用例）。
- [x] 3.3 在合并/发布前运行 `just qa`（或等价 CI 门禁）确保无 drift 与回归。
