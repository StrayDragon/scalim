## Context

by_yaml 的 aggregate 输出相关逻辑当前在多个层次重复维护 producer key 枚举常量（parser/runtime/introspection）。这类重复常量很容易在扩展 aggregate 能力时产生“改一处漏两处”的漂移，最终表现为校验/装配/自省三者不一致。

约束：

- `src/scalim/` 运行时需保持 Python 3.6 兼容
- by_yaml 目录内倾向相对导入，避免跨层循环依赖
- 本变更目标是“SSOT 收敛 + 护栏”，不改变 aggregate 语义

## Goals / Non-Goals

**Goals:**
- 为 aggregate producer keys 建立单一事实来源（SSOT），并让 parser/runtime/introspection 统一引用
- 增加最小回归护栏，确保未来新增/调整 key 时不会跨层漂移

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

3) **护栏策略**

- 添加一个单元测试，断言三处模块均引用 SSOT（至少断言集合一致；更强可断言导入同一对象名）
- 若发现当前三处枚举实际不一致：
  - 先在测试中显式捕获差异并解释其是否为“有意差异”
  - 若为 bug，则在同一变更中修复并写入 spec/测试，避免继续漂移

## Risks / Trade-offs

- [隐藏的不一致被暴露] → 在迁移时可能发现 introspection 默认策略与 parser/runtime 不一致；通过“显式拆分常量 + 测试解释差异”的方式把不确定性变成可讨论的决策点
- [循环依赖风险] → SSOT 放在 `schema_dsl` 下的独立模块，并保持无运行时依赖，避免 runtime → parser 的反向依赖
