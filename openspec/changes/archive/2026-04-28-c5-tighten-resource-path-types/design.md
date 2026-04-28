## Context

### 关键路径清单(调研结果)

路径节点的“输入形状”来自 YAML schema,其语义贯穿多个阶段:

1. Schema 层(作者表面)
- demand:
  - `resources.books.*.xlsx_file.path`
  - `resources.files.*.csv_file.path`
  - `resources.books.*.xlsx_memory.export_xlsx.path`
- workflow:
  - `workflow.resources.books.*.xlsx_file.path`
  - `workflow.resources.files.*.csv_file.path`
  - `workflow.resources.books.*.xlsx_memory.export_xlsx.path`
- 这些字段允许的形状: `str` 或 `{$init_var: <name>}` mapping node。

2. YAML parse/compile 层(把 YAML 形状收敛为内部结构)
- demand runtime compiler:
  - `src/scalim/dsl/yaml_dsl/runtime/compiler.py`:
    - `_parse_non_empty_path_or_init_var`
    - `_parse_optional_path_or_init_var`
- workflow config parse:
  - `src/scalim/dsl/yaml_dsl/workflow_config/_parse.py`:
    - `_parse_path_or_init_var`
- 当前这些函数都返回 `Any`(str 或 dict),导致下游必须 cast。

3. runtime resolve 层(把 init_var 解析为最终字符串)
- `src/scalim/dsl/yaml_dsl/runtime/output_path_resolve.py`:
  - `resolve_output_container_path`
  - `resolve_yaml_relative_output_path`
- 当前通过 `isinstance(raw, dict)` + `parse_init_var_mapping_node(...)` 实现。

4. 使用侧(真正消费路径的关键路径)
- workflow compile/runtime:
  - `src/scalim/dsl/yaml_dsl/workflow_compile.py` (通过 `resolve_yaml_relative_output_path`)
  - `src/scalim/dsl/yaml_dsl/workflow_entrypoints.py` (把资源路径传给 workflow/execution)
- output composition:
  - `src/scalim/dsl/yaml_dsl/runtime/output_composition_yaml.py` (资源路径/输出路径检查与拼装)

### 问题

- `BookConfig.path` / `FileConfig.path` 在 schema_dsl 模型中为 `Any`。
- 下游模块大量依赖 `cast` 与 `allow-cast` pragma,难以判断哪些 cast 是“必要边界”,哪些只是“类型系统没建模”。

## Goals / Non-Goals

Goals:
- 用显式 SSOT 类型替代 `Any`:
  - `InitVarRef` 表示 `{$init_var: <name>}`
  - `PathNode = Union[str, InitVarRef]`
- 让关键路径只在“边界函数”里做一次形状判定/窄化,其它地方只看到明确类型。
- 在不改变行为的前提下减少 cast/pragma,并让剩余 cast 更集中更可审计。

Non-Goals:
- 不改变 YAML schema 的作者表面(仍支持 `str` 或 `{$init_var: ...}`)。
- 不在本 change 内把所有路径都统一解析为绝对路径(仍由既有 resolve 层控制)。

## Decisions

1. 引入 `InitVarRef` 作为内部表示
- YAML mapping node 在 parse 阶段被转换为 `InitVarRef(name=...)`。
- 下游不再使用 `dict` 作为内部形状,避免重复 `parse_init_var_mapping_node`。

2. 统一路径节点类型别名
- 在 YAML DSL runtime 的某个稳定位置定义:
  - `PathNode` / `OutputRootPathNode` / `OptionalPathNode` 等别名
- `BookConfig.path` / `FileConfig.path` 及相关字段使用该别名替代 `Any`。

3. resolve 层只接受明确类型
- `resolve_output_container_path` 等函数改为接受 `PathNode` (或 `object` 但尽快 narrow),并将 dict 分支迁移为 `InitVarRef` 分支。

## Risks / Trade-offs

- [风险] 这是类型与内部表示的重构,会波及多个模块。
  - 缓解: 按关键路径清单分层推进(先定义类型与 parse/resolve 边界,再迁移使用侧)。

- [风险] 可能影响少量外部用户对 config dataclass 的直接检查(如果他们依赖 dict 形状)。
  - 缓解: 本仓库策略允许 breaking;但仍应在 release note/变更说明中点明。

## Migration Plan

- 代码内分阶段迁移:
  1. 新增 `InitVarRef` 与类型别名
  2. parse 阶段改为产出 `InitVarRef`
  3. resolve 阶段与使用侧改为消费 `InitVarRef`
  4. 移除残留 dict 分支与相关 cast/pragma

## Open Questions

- `InitVarRef` 是否需要同时携带 `path`(用于更好的错误信息)? 当前倾向由调用方传 `path=`。
> 需要携带 这样可以方便更好的错误信息