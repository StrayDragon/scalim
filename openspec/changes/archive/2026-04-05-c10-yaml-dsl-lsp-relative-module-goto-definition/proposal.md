## Why

YAML DSL 允许在 `loader` / `call_by` 等 Python 引用字段里使用**相对模块引用**（例如 `.loaders:load_orders`、`..loaders:load_orders`），
以便把配置与实现放在同一包内并减少重复的绝对模块前缀。

但当前 `scalim-yaml-dsl-lsp` 的 editor semantics core/LSP server 在 go-to-definition/hover/completion 上会对相对模块引用降级为 warning
（例如 `相对模块路径引用暂不支持 go-to-definition: .registry`），导致 notebooks/demo/真实工程里常见写法无法跳转，影响开发体验与可回归性。

## What Changes

- 支持对相对模块引用进行静态解析：
  - 基于 `yaml_path` + project discovery 的 `python_roots` 推导 `base_module_path`
  - 将 `.mod` / `..mod` 等相对模块规范化为绝对模块路径后再进行文件系统 + AST 的 definition/hover/completion 解析
- 对无法解析的情况提供更可诊断的降级：
  - YAML 文件不在任何 `python_roots` 下（无法推导 base）时给出明确 warning（提示补充 `yaml_dsl.editor.python_roots` 或改用绝对引用）
  - 相对引用向上越界（超过根包）时给出明确 warning
- 不引入运行时副作用：不得执行用户代码，且不得改写进程级 `sys.path`

## Capabilities

### New Capabilities
- （无）

### Modified Capabilities
- `yaml-dsl-editor-semantics-core`: Python reference resolution MUST 支持相对模块引用（在具备 `yaml_path + python_roots` 上下文时）。
- `yaml-dsl-lsp-server`: go-to-definition/hover/completion MUST 复用 core 对相对模块引用的解析能力，并在失败时返回空结果 + warnings（不得 crash）。

## Impact

- 受影响代码：
  - `packages/scalim-yaml-dsl-lsp/`: core Python 引用解析 + server feature handler 的入参/调用方式
- 测试/回归：
  - 新增/扩展 editor semantics core 的单测，覆盖 `.mod` / `..mod` 的定位与失败降级形态
