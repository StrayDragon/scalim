## 1. YAML DSL 行为与 schema

- [x] 1.1 调整 `books.kind=xlsx_memory` 的 `budget` 约束为可选(更新 schema SSOT: `src/scalim/dsl/yaml_dsl/schema_dsl/models/resources.py`)
- [x] 1.2 调整 `write_defaults.mode` 默认值为 `sheet`(更新 SSOT: `src/scalim/dsl/yaml_dsl/schema_dsl/output_enums.py`)
- [x] 1.3 更新 YAML 解析/编译期语义校验: 允许 `xlsx_memory` 缺省 `budget`(相关: `src/scalim/dsl/yaml_dsl/workflow_config/_parse.py`, `src/scalim/dsl/yaml_dsl/workflow_compile.py`)

## 2. 运行时预算护栏语义

- [x] 2.1 将 `xlsx_memory` 的“缺省预算”解释为 unlimited(运行时对 `budget_max_sheets/max_total_cells <= 0` 跳过检查;相关: `src/scalim/workflow/resources_sheetbook.py`)
- [x] 2.2 确保当用户显式设置预算时仍严格执行并给出可行动诊断(错误 diff 中包含预算值)

## 3. 文档与生成物

- [x] 3.1 更新用户文档示例: 移除“用极大值模拟无限制”的写法,并说明 `budget` 可选与默认 mode 行为(SSOT: `docs/doc/yaml-dsl/workflow.md`)
- [x] 3.2 生成 schema 产物(生成入口: `just gen-yaml-dsl-schema`; 生成物: `src/scalim/dsl/yaml_dsl/schema/*.gen.*`)
- [x] 3.3 生成 docs 受控产物/注入区块(生成入口: `just gen-docs`; 生成物: `docs/doc/**/*.gen.md`)

## 4. 测试与门禁

- [x] 4.1 更新/新增 tests 覆盖: `xlsx_memory` 缺省 budget 可通过校验且写入不触发预算失败(相关: `tests/workflow/**`, `tests/yaml_dsl/**`)
- [x] 4.2 更新/新增 tests 覆盖: `write_defaults.mode` 缺省时 effective 为 `sheet`
- [x] 4.3 运行质量门禁: `just openspec-check` + (至少) `just schema-drift-check` + 相关 tests(建议最终 `just qa`)
