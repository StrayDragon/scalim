## 1. Source Field Authoring Surface (`extract` only)

- [x] 1.1 在 `schema_dsl` / parser / validator 中新增 `extract`,并从稳定 YAML surface 中移除 `fields.*.field`(出现即 fail-fast,并给迁移提示: “请改用 extract”)
- [x] 1.2 默认规则: 未声明 `extract` 时,行为等价于 `extract: <field_id>`(顶层同名 key)
- [x] 1.3 `output.fields` 选择器语义保持不变: 如需显式选择使用 `extract` 的字段,优先用 `field_id` / alias(不扩展 `{field: ...}` 去匹配 extract)

## 2. `extract` Path Expression Compiler (dot + bracket)

- [x] 2.1 在编译阶段将 `extract` 解析为 canonical segments(typed),并保留原始表达用于诊断;运行时不得再对字符串做 ad-hoc split
- [x] 2.2 语法支持:
  - `a.b.c`(string segments)
  - `[1]`(int key segment)
  - `["a.b"]` / `['a.b']`(string key segment,用于字面量含点号/特殊字符的 key)
- [x] 2.3 约束: 不做 `"1" ↔ 1` 隐式 cast;不支持数组下标语义(`[1]` 永远表示 key=1,不是 list index)
- [x] 2.4 bracket string segment 支持最小转义(`\\`/`\"`/`\'`)并在编译期 fail-fast 拒绝非法转义
- [x] 2.5 非法表达式在编译/校验阶段 fail-fast(空 segment/连续点/首尾点/非法括号/未闭合引号等),错误包含配置 path 与修复建议

## 3. Runtime Field Access (segment-wise traversal)

- [x] 3.1 扩展字段读取 helper: 按 segments 逐段执行 mapping key / obj attr / `__getitem__` 读取,任一段失败返回 `None`
- [x] 3.2 明确 int segment 行为: `[1]` 仅表示“key=1”,不得对 list/tuple 做索引(即使 `__getitem__` 支持也必须拒绝)
- [x] 3.3 确保主加载与 ref-load 两条执行路径都消费同一套 segments traversal,并共享同一份编译产物

## 4. Schema, Editor, Docs, Skill

- [x] 4.1 更新 YAML schema 元数据: 仅暴露 `extract`,并在 `description` / `markdownDescription` 中写入 current-row-relative 解释、bracket 语法示例与迁移提示
- [x] 4.2 重新生成 `src/scalim/dsl/by_yaml/schema/demand.gen.json`,并同步更新前端 schema 镜像(`frontend/scalim-yaml-dsl-editor/**/schema/demand.gen.json`)
- [x] 4.3 更新 `docs/doc/` 下 YAML DSL 文档与示例,补充 `extract` 语法(含 `[1]` / `["a.b"]`)、反例与迁移说明
- [x] 4.4 更新 `artifacts/skills/scalim-yaml-dsl/**`,以 `extract` 作为唯一字段取值写法,覆盖 int-key nested dict 场景

## 5. Repo-wide Upgrade (breaking)

- [x] 5.1 一次性升级仓库内所有 YAML 示例/fixtures/notebooks/skill/前端 examples: 将 `fields.*.field` 全部改为 `fields.*.extract`
- [x] 5.2 增加回归/守卫: 校验器对 `fields.*.field` 给出明确迁移错误,防止旧写法回流
- [x] 5.3 升级 canonical example `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`: 将所有 `fields.*.field` 改为 `extract` 并确保相关测试/导出产物可验证

## 6. Tests And Verification

- [x] 6.1 新增单元测试: 语法解析(bracket/int/string)、dotted literal key、无隐式 cast、非法表达式 fail-fast
- [x] 6.2 补充边界测试: `[-1]` / `[ 1 ]` 被拒绝、最小转义可用且非法转义被拒绝、dot identifier 非法字符必须用 bracket 表达
- [x] 6.3 新增集成测试: YAML 编译/执行端到端提取 nested mapping/对象属性/`__getitem__`,以及主加载与 ref-load 一致性
- [x] 6.4 验证: 运行 `openspec validate --all --strict --no-interactive` 与相关 YAML/schema/editor drift 测试,确认工件和生成物一致
- [x] 6.5 下游适配盘点: 读取 `.tmp/known-outer-paths-using-this-package.txt` 并对其中关联代码做同步升级(不得在输出中引用其内容)
