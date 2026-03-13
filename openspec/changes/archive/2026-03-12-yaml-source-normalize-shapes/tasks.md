## 1. Schema / Authoring Surface

- [x] 1.1 扩展 `normalize.kind` 枚举与 schema(新增 `take_first`/`map_values`/`project_fields`),并补齐 markdownDescription/examples
- [x] 1.2 为 `take_first`/`project_fields`/`map_values` 增加结构化配置 schema(含 `on_empty`/`on_missing`/`steps`/`fields.path` 等约束)
- [x] 1.3 运行生成入口刷新 YAML schema 生成物,并通过 drift gate(避免手改 `.gen.*` 或 injected blocks)
- [x] 1.4 重新生成并提交 editor schema: `just gen-yaml-dsl-editor-schema`(同步 `frontend/scalim-yaml-dsl-editor/**/schema/demand.gen.json`)

## 2. Runtime / IR 实现

- [x] 2.1 扩展 `SourceNormalizeIr` 与 normalize 执行逻辑,实现 `take_first`/`project_fields`/`map_values` 的运行时语义与错误信息
- [x] 2.2 `project_fields`: 实现基于 YAML 序列的 path 解析(支持 `int` key)与 `from_key` 注入
- [x] 2.3 `take_first`: 实现 `mapping[key -> list]` 取首条 + `on_empty` 策略;补齐 `list[row]` 场景的约束与失败提示

## 3. YAML 解析与语义校验

- [x] 3.1 更新 `config_parsing` validators: 按 kind 校验必填/互斥字段,并校验 `steps`/`fields`/`path` 类型边界
- [x] 3.2 更新 YAML -> IR conversion: 支持新 kind 与 `map_values.steps` 的编译,并确保错误路径可定位到 `sources.<id>.normalize`

## 4. 受控扩展点 `normalize.call_by`

- [x] 4.1 在 runtime 引用解析中复用 allowlist 逻辑解析 `normalize.call_by`,支持相对引用归一化
- [x] 4.2 强制 `Mapping -> Mapping` contract,对非 Mapping 输入/输出 fail-fast,并补齐错误信息(含 source_id 与配置路径)

## 5. Tests / Acceptance

- [x] 5.1 增加单测覆盖: `take_first`(on_empty=miss|null|error)、`map_values` pipeline、`project_fields`(含 int key path 与 from_key)
- [x] 5.2 增加单测覆盖: `normalize.call_by` allowlist/contract(返回非 Mapping 被拒绝)
- [x] 5.3 扩展/新增 acceptance demo YAML,覆盖 “nested dict flatten(含 int key)” 与 “mapping[key -> list] take_first” 的可运行样例
- [x] 5.4 更新 canonical demo: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml` 覆盖至少一种新 normalize 写法

## 6. Docs / QA

- [x] 6.1 更新与 `yaml-source-normalize` 相关的文档/说明(作者视角: 何时用 `take_first`/`project_fields`/`map_values`/`call_by`)
- [x] 6.2 盘点下游适配与同步修改: 读取 `.tmp/known-outer-paths-using-this-package.txt` 并列出需要同步的下游目录(输出/文档中不得引用文件内容)
- [x] 6.3 新增升级指南: `docs/doc/yaml-dsl/upgrades/2026-03-13-yaml-source-normalize-shapes.md`,并运行 `just gen` 注入升级索引
- [x] 6.4 通过: `just gen`
- [x] 6.5 通过: `just qa`
- [x] 6.6 通过: `just openspec-check`
- [x] 6.7 归档到: `openspec/changes/archive/YYYY-MM-DD-yaml-source-normalize-shapes/`
