## ADDED Requirements

### Requirement: YAML output root paths MUST use an explicit SSOT path-node type (no Any)

系统 MUST 允许 YAML DSL 的输出 root 路径字段采用两种作者形状:
- 静态字符串路径
- `{$init_var: <name>}` 指令节点

系统 MUST 在 runtime adapter 内使用一个显式的 SSOT 类型表示该“路径节点”(例如 `PathNode = Union[str, InitVarRef]`),并禁止在核心模型中继续使用 `Any` 承载该语义。

系统 MUST 将“形状判定/解析”集中在少量边界函数中(例如 parse 与 resolve),其余使用侧不得重复 `isinstance(raw, dict)` + cast 的散落模式。

#### Scenario: maintainers can identify the path-node boundary
- **WHEN** 维护者审阅 resources/files/books 的 path 解析与解析后使用路径
- **THEN** 必须能找到一个明确的 SSOT 类型与集中化的 parse/resolve 边界函数
- **AND** 核心模型字段不得继续以 `Any` 表达该语义
