## Why

`_REPORT.md` 指出 `BookConfig.path` / `FileConfig.path` 当前类型为 `Any`,导致下游路径操作普遍需要 `cast`/`isinstance` 进行缩窄,形成系统性的类型债务。

结合代码现状,这些 path 字段的真实语义是“字符串路径或 `{$init_var: <name>}` 指令节点”(并最终在编译/运行期解析为字符串路径)。但由于缺少一个统一的显式类型,目前的实现表现为:
- 多处重复的 `isinstance(raw, dict)`/`parse_init_var_mapping_node(...)`
- 大量 `cast(...)` 与 `# pragma: allow-cast` 分散在关键路径
- 很难在 review 中确认“哪些路径是关键路径、哪些地方应该只看到 str”

你希望选一条主线把关键路径类型收紧,并在调研中声明关键路径。这个 change 将把“path-or-init-var”收敛为 SSOT 类型,并逐步消减 cast/pragma。

## What Changes

- 新增并推广一个 SSOT 类型表示“路径节点”:
  - `str` 静态路径
  - `InitVarRef`(或等价对象)表示 `{$init_var: <name>}`
- 将 `BookConfig.path` / `FileConfig.path` 及相关结构从 `Any` 收紧为明确类型(含 Optional/Required 约束不变)。
- 收敛解析与解析后路径归一化逻辑:
  - YAML 解析层: 仅负责把 YAML mapping node 转成 `InitVarRef`
  - 运行/编译层: 负责把 `InitVarRef` 在 `init_vars` 上解析为最终字符串
- 在 design 中给出“关键路径清单”(schema → parse → compile → runtime resolve → output publish),作为后续治理 cast/pragma 的地图。

## Capabilities

### New Capabilities

- （无）

### Modified Capabilities

- `dsl-runtime-structure`: 增补 runtime adapter 的类型契约,要求路径节点使用显式 SSOT 类型而不是 `Any` + scattered cast。

## Impact

- 受影响代码(预计):
  - `src/scalim/dsl/yaml_dsl/schema_dsl/models/resources.py` (BookConfig/FileConfig)
  - `src/scalim/dsl/yaml_dsl/runtime/compiler.py` (path parsing helpers)
  - `src/scalim/dsl/yaml_dsl/workflow_config/_parse.py`
  - `src/scalim/dsl/yaml_dsl/runtime/output_path_resolve.py`
  - `src/scalim/dsl/yaml_dsl/runtime/output_composition_yaml.py`
  - `src/scalim/dsl/yaml_dsl/workflow_compile.py`
- 预期收益:
  - 下游路径操作不再依赖 `Any` + cast,review 更可控
  - 为后续减少 `cast()` pragma 与进一步模块化重构打基础
