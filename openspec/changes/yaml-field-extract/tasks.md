## 1. Source Field Authoring Surface

- [ ] 1.1 在 `schema_dsl` / parser / validator 中为 source field 增加 `extract` 字段,并实现 `field` 与 `extract` 互斥校验
- [ ] 1.2 在字段编译链路中实现 effective selector 优先级(`extract > field > field_id`),并保持现有 YAML 兼容
- [ ] 1.3 明确并保持 `output.fields` 现有选择器语义不变: `extract` 字段的显式输出选择继续优先使用 `field_id` / alias

## 2. Runtime Field Access

- [ ] 2.1 扩展字段读取 helper,支持对 `extract` dotted path 逐段执行 mapping / attr / `__getitem__` 读取
- [ ] 2.2 保持 `field` 的 raw flat 语义: dotted `field` 仍按字面量顶层键处理,不得被当作路径拆分
- [ ] 2.3 确保主加载与 ref-load 两条执行路径都基于同一套 dotted traversal 语义读取字段值

## 3. Schema, Editor, Docs, Skill

- [ ] 3.1 更新 YAML schema 元数据: 为 `extract` 写入 current-row-relative 的 `description` / `markdownDescription`,并明确 `field` 与 `extract` 的边界
- [ ] 3.2 重新生成 `src/scalim/dsl/by_yaml/schema/demand.gen.json`,并同步更新 `frontend/scalim-yaml-dsl-editor/src/schema/demand.gen.json`
- [ ] 3.3 更新 `docs/doc/` 下 YAML DSL 文档与示例,补充 `extract` 的语义、反例和迁移说明
- [ ] 3.4 更新 `artifacts/skills/scalim-yaml-dsl/**`,明确“嵌套 row value 优先用字段级 `extract`”的指导

## 4. Tests And Verification

- [ ] 4.1 新增测试覆盖: nested mapping、对象属性路径、缺失中间段返回 `None`、`field`/`extract` 互斥、默认回退到 `field_id`
- [ ] 4.2 新增测试覆盖: `field` 中的 dotted literal key 仍按 raw flat selector 读取,以及 `output.fields` 继续通过 `field_id` / alias 选择 `extract` 字段
- [ ] 4.3 运行 `openspec validate --all --strict --no-interactive` 与相关 YAML/schema/editor drift 测试,确认工件和生成物一致
