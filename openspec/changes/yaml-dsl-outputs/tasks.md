## 1. Schema 与模型(SSOT)

- [ ] 1.1 在 `src/scalim/dsl/by_yaml/schema_dsl/models/` 中新增 `outputs` 相关配置模型(输出目标、容器、where、aggregate、meta/audit、failure_policy 等)并更新 `DemandConfig`
- [ ] 1.2 更新 `schema_dsl` builder/常量键映射,生成 `outputs` 对应的 JSONSchema(并移除旧 `output` 顶层字段,不保留兼容层)
- [ ] 1.3 通过既有生成入口刷新 `src/scalim/dsl/by_yaml/schema/demand.gen.json` 与相关文档生成物(禁止手改生成文件)
- [ ] 1.4 重新生成并提交 editor schema: `just gen-yaml-dsl-editor-schema`(同步 `frontend/scalim-yaml-dsl-editor/**/schema/demand.gen.json`)

## 2. 解析与语义校验(config_parsing)

- [ ] 2.1 在 `YamlDemandLoader` 中解析 `outputs` 并落入 `DemandConfig` 新字段(包含 order 保序)
- [ ] 2.2 实现 `outputs.*.from` 继承解析: 继承字段集合与容器配置,并支持覆盖 where/sheet/aggregate 等
- [ ] 2.3 对 `where` 接入 `SecureComputeEngine` 校验与编译,静态提取依赖字段并为每个 output 记录 `requires`
- [ ] 2.4 编译期 fail-fast 校验:
  - 重名 output / 非法 name
  - `from` 指向不存在或循环引用
  - composed outputs 必填 `path`,共享 workbook 必填 `sheet`
  - composed outputs 仅允许 `streaming=true`
  - `aggregate` 结构完整性(必填 group_by/metrics 等)与与 `fields` 的互斥/约束
  - `where` 依赖字段无法解析时给出可操作的错误提示
- [ ] 2.5 当检测到旧写法 `output:` 顶层字段时 fail-fast,提示升级到 `outputs:` 并给出最小迁移片段

## 3. Runtime 装配(outputs → OutputCompositionSpec)

- [ ] 3.1 在 `src/scalim/dsl/by_yaml/runtime/` 中实现从 `DemandConfig.outputs` 装配 `OutputCompositionSpec`,并写入 `ExecutionRequest.output_composition`
- [ ] 3.2 明细 outputs → `OutputTargetSpec`:
  - 生成 `ExportLayout`(字段顺序/表头策略)
  - 生成 `OutputSpec`(format/path/sheet/allow_formulas/write_lock/include_header 等)
  - where predicate 使用受限表达式执行,并注入 `requires`
- [ ] 3.3 派生 outputs(aggregate) → `DerivedOutputTargetSpec`:
  - 生成 `DerivedGroupBySpec`(group_by/metrics/max_groups/可选 rank/top_k)
  - 生成派生输出 layout(默认: group_by + metric 输出字段 [+ rank 字段])
  - 注入 `requires`(包含 where/aggregate 依赖)
- [ ] 3.4 装配 meta/audit sheet 与 `failure_policy`/`include_full_error_message`,并明确 primary 输出选择策略(顺序或显式标记)
  - MVP: primary 按 `outputs` 列表顺序(默认第一个明细/派生 output)

## 4. 测试与验收用例

- [ ] 4.1 增加单元测试: `where` 依赖字段提取与 required fields 注入;依赖缺失时 fail-fast
- [ ] 4.2 增加编译级测试: 给定一份 YAML(脱敏 fixtures),断言编译结果生成等价的 `OutputCompositionSpec` + derived 配置
- [ ] 4.3 将 `acceptance/mvp_demo` 的需求表达沉淀为回归用例(脱敏),覆盖:
  - 多 sheet where 分发确定性
  - 派生汇总写入 workbook
  - meta/audit/fingerprint 开关与输出统计

## 5. Demo / 文档迁移

- [ ] 5.1 升级 `acceptance/mvp_demo` 以使用 YAML `outputs`(去掉“最薄 Python sink” glue),保持可运行
- [ ] 5.2 升级 canonical demo: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml` 覆盖新语义
- [ ] 5.3 如涉及 docs 生成物/注入区块,运行 `just gen-docs` 刷新,并在提交前跑 `just qa`/`just openspec-check`

## 6. 全仓迁移(一步到位;不做兼容层)

- [ ] 6.1 将仓内所有 YAML DSL 从顶层 `output:` 升级为 `outputs:`(单输出时为单元素列表),并统一迁移到 `container` + `fields: [field_id, ...]` 的 MVP 语法
- [ ] 6.2 更新 docs/README/skill references 中的 YAML 示例以匹配新语法(注意: `.gen.` 文件与 `BEGIN/END AUTOGEN:*` 区块遵循文档治理,通过 SSOT + `just gen-docs` 刷新)
- [ ] 6.3 更新前端 YAML DSL editor 的示例与模板(`frontend/scalim-yaml-dsl-editor/**`),并确保其使用的 schema/示例与新语义一致
- [ ] 6.4 更新测试用例与 fixtures(`tests/**`)以匹配新语法,确保覆盖:
  - 单输出(单元素 outputs)与多输出(多 sheet + aggregate)
  - `where` 依赖注入(required fields)与依赖缺失时的诊断
  - `failure_policy: primary_only` 下 primary/非 primary 失败行为
- [ ] 6.5 运行 `just qa` 验证迁移后的 repo 质量门禁通过

## 7. Breaking 升级指南 / 下游适配 / 门禁 / 归档

- [ ] 7.1 盘点下游适配与同步修改: 读取 `.tmp/known-outer-paths-using-this-package.txt` 并列出需要同步的下游目录(输出/文档中不得引用文件内容)
- [ ] 7.2 新增升级指南: `docs/doc/yaml-dsl/upgrades/YYYY-MM-DD-yaml-dsl-outputs.md`,并运行 `just gen` 注入升级索引
- [ ] 7.3 通过: `just gen`
- [ ] 7.4 通过: `just qa`
- [ ] 7.5 通过: `just openspec-check`
- [ ] 7.6 归档到: `openspec/changes/archive/YYYY-MM-DD-yaml-dsl-outputs/`
