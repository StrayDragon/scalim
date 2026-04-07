## Why

用户反馈 YAML DSL LSP 的 go-to-definition 在部分合法 loader 引用上无法跳转到“真正可调用对象”的定义位置，导致排障与迭代效率显著下降。
典型场景是 `module.path:obj.method`：当前实现会跳到 `obj = Klass()` 的赋值语句，而不是 `class Klass: def method(...)`。

## What Changes

- 扩展 editor semantics core 的静态 definition 解析能力：对 `module.path:obj.method` 形态引入“轻量静态推断”，在不执行用户代码的前提下，尽可能定位到 `Klass.method` 的 AST 定义位置。
- go-to-definition 返回 **多个** locations：
  - 优先返回推断到的 `Klass.method`（或更深链路的最终 symbol）定义位置；
  - 同时保留当前的降级行为：将 `obj` 的定义/赋值位置作为后续备选 location（便于用户追溯引用来源）。
- 引入覆盖更全面的 fixtures + pytest 回归集合，覆盖常见对象引用/导入/别名/注解等模式，确保行为稳定且失败可诊断（warnings）。

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `yaml-dsl-editor-semantics-core`: Python 引用的静态 definition 解析新增 `obj.method` 场景的轻量推断，并允许返回多 locations（有序）。
- `yaml-dsl-lsp-server`: go-to-definition 将透传并返回多 locations；对 `loader/call_by/...` 的引用解析覆盖面扩大且保持静态无副作用约束。

## Impact

- 影响代码路径：
  - `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/core.py`（definition 解析与 AST 索引/推断）
  - `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/server.py`（LSP definition handler 的返回值策略与 diagnostics）
- 影响测试：
  - 新增/扩展 `tests/yaml_dsl/*` 单测与 `tests/fixtures/*` 夹具模块，用于覆盖多种 Python 引用形态与 go-to-definition 返回顺序。

