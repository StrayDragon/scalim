## 1. Schema / Authoring Surface

- [ ] 1.1 扩展 `normalize.kind` 枚举与 schema(新增 `take_first`/`map_values`/`project_fields`),并补齐 markdownDescription/examples
- [ ] 1.2 为 `take_first`/`project_fields`/`map_values` 增加结构化配置 schema(含 `on_empty`/`on_missing`/`steps`/`fields.path` 等约束)
- [ ] 1.3 运行生成入口刷新 YAML schema 生成物,并通过 drift gate(避免手改 `.gen.*` 或 injected blocks)

## 2. Runtime / IR 实现

- [ ] 2.1 扩展 `SourceNormalizeIr` 与 normalize 执行逻辑,实现 `take_first`/`project_fields`/`map_values` 的运行时语义与错误信息
- [ ] 2.2 `project_fields`: 实现基于 YAML 序列的 path 解析(支持 `int` key)与 `from_key` 注入
- [ ] 2.3 `take_first`: 实现 `mapping[key -> list]` 取首条 + `on_empty` 策略;补齐 `list[row]` 场景的约束与失败提示

## 3. YAML 解析与语义校验

- [ ] 3.1 更新 `config_parsing` validators: 按 kind 校验必填/互斥字段,并校验 `steps`/`fields`/`path` 类型边界
- [ ] 3.2 更新 YAML -> IR conversion: 支持新 kind 与 `map_values.steps` 的编译,并确保错误路径可定位到 `sources.<id>.normalize`

## 4. 受控扩展点 `normalize.call_by`

- [ ] 4.1 在 runtime 引用解析中复用 allowlist 逻辑解析 `normalize.call_by`,支持相对引用归一化
- [ ] 4.2 强制 `Mapping -> Mapping` contract,对非 Mapping 输入/输出 fail-fast,并补齐错误信息(含 source_id 与配置路径)

## 5. Tests / Acceptance

- [ ] 5.1 增加单测覆盖: `take_first`(on_empty=miss|null|error)、`map_values` pipeline、`project_fields`(含 int key path 与 from_key)
- [ ] 5.2 增加单测覆盖: `normalize.call_by` allowlist/contract(返回非 Mapping 被拒绝)
- [ ] 5.3 扩展/新增 acceptance demo YAML,覆盖 “nested dict flatten(含 int key)” 与 “mapping[key -> list] take_first” 的可运行样例

## 6. Docs / QA

- [ ] 6.1 更新与 `yaml-source-normalize` 相关的文档/说明(作者视角: 何时用 `take_first`/`project_fields`/`map_values`/`call_by`)
- [ ] 6.2 跑 `just openspec-check` 与 `just qa` 确认工件校验、schema 漂移与核心测试通过

