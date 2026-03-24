## Context

by_yaml 的 aggregate 输出相关逻辑当前在多个层次重复维护 producer key 枚举常量（parser/runtime/introspection/schema/editor）。这类重复常量很容易在扩展 aggregate 能力时产生“改一处漏两处”的漂移，最终表现为校验/装配/自省/结构校验/编辑器提示不一致。

约束：

- `src/scalim/` 运行时需保持 Python 3.6 兼容
- by_yaml 目录内倾向相对导入，避免跨层循环依赖
- `*.gen.json` 属于生成物，不手工编辑；需要通过生成命令同步到仓库与 editor bundle
- 本变更目标是“SSOT 收敛 + 护栏”，不改变 aggregate 语义

## Goals / Non-Goals

**Goals:**
- 为 aggregate producer keys 建立单一事实来源（SSOT），并让 parser/runtime/introspection/schema/editor 统一引用
- 增加最小回归护栏，确保未来新增/调整 key 时不会跨层漂移（含 schema/editor）

**Non-Goals:**
- 不新增/删除任何 aggregate producer key
- 不改变 aggregate 的执行语义、字段选择策略或输出默认行为（除非当前已存在不一致且被认定为 bug）
- 不在本变更内拆分/重构 outputs 解析的大函数（那是独立的 c1 refactor 议题）

## Decisions

1) **SSOT 位置选择**

- 选项 A：放在 `src/scalim/dsl/by_yaml/schema_dsl/constants.py`
  - 优点：`schema_dsl` 已是多处 parser 的 SSOT；依赖层级低
  - 缺点：`constants.py` 已较大，继续扩展会变得更臃肿
- 选项 B（推荐）：新增轻量模块 `src/scalim/dsl/by_yaml/schema_dsl/output_enums.py`
  - 优点：聚合/输出相关枚举独立收敛，避免进一步污染 `constants.py`
  - 优点：依赖方向清晰（parser/runtime/introspection 都可安全向下依赖）
  - 缺点：多一个文件

**决策**：采用选项 B，新建 `schema_dsl/output_enums.py` 作为输出/聚合枚举的 SSOT。

2) **常量粒度**

我们不只提供一个“大而全”的 tuple，而是按语义拆分，降低误用风险：

- `AGG_METRIC_PRODUCER_KEYS`
- `AGG_RANK_PRODUCER_KEYS`
- `AGG_POST_PRODUCER_KEYS`

并允许工具层（introspection）基于 SSOT 组合出自己的默认行为（例如默认字段选择是否包含 `compute` 属于工具语义，而不是“枚举是否存在”的问题）。

3) **纳入 schema/editor（避免“schema 允许但运行时不支持”或反之）**

producer keys 同时存在于：

- parser/runtime/introspection（运行时行为与工具行为）
- JSON schema（结构校验 + editor 补全/hover 的基础）

为避免新增/调整 key 时出现 “schema 支持但 runtime 不支持” 或 “runtime 支持但 schema/editor 不提示”，本变更把 schema/editor 纳入 SSOT 收敛范围：

- `src/scalim/dsl/by_yaml/schema_dsl/models/outputs.py` MUST 基于 SSOT 组装 aggregate producer keys 的 schema 列表（anyOf/required）
- schema 生成阶段 MUST 对齐 SSOT（缺 key 或多 key 都应失败或被测试捕获）
  - 实现建议：schema 侧本质是 `oneOf` 分支列表（每个分支通过 `required: ["<producer_key>"]` 锚定 key）。可以从该 `oneOf` 中抽取所有 `required` key 集合，与 SSOT 的全集做集合一致性断言（避免“schema 多支持/少支持”）。
- 使用既有生成命令同步 canonical schema 与 editor bundle（`just gen-yaml-dsl-editor-schema`）

4) **对齐默认行为（修复已存在漂移）**

当前存在一个可复现的不一致：

- runtime 默认 aggregate 输出列包含 `compute`
- introspection 的 `load_output_config()` 默认 `output_fields` 不包含 `compute`

这会导致 “工具默认预览字段” 与 “实际 `run()` 输出列” 不一致，属于跨层漂移风险的真实表现。

**决策**：采用方案 A，将 introspection 的默认 `output_fields` 对齐到 runtime 的默认输出列（包含 `compute`），并用测试固化该一致性。

5) **护栏策略**

- 添加单元测试护栏：
  - 行为回归：覆盖 aggregate + `compute` + 未显式 `outputs.*.fields` 的场景，确保 `load_output_config()` 的默认 `output_fields` 与 runtime 输出列一致
  - 防漂移：断言 parser/runtime/introspection 均引用 SSOT（建议断言导入同一对象；至少断言集合一致）
  - schema/editor drift：通过生成命令同步 `demand.gen.json` 与 editor bundle，并在 CI 中阻止未同步（`just schema-drift-check`）
- 若发现当前三处枚举实际不一致：
  - 先在测试中显式捕获差异并解释其是否为“有意差异”
  - 若为 bug，则在同一变更中修复并写入 spec/测试，避免继续漂移

## Risks / Trade-offs

- [隐藏的不一致被暴露] → 在迁移时可能发现 introspection 默认策略与 parser/runtime 不一致；本变更选择直接对齐并写测试固化，避免再次漂移
- [schema 生成物大范围变更] → 将触发 `*.gen.json` 更新；必须通过生成命令更新并提交，避免手工修改与遗漏
- [循环依赖风险] → SSOT 放在 `schema_dsl` 下的独立模块，并保持无运行时依赖，避免 runtime → parser 的反向依赖
