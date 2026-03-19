## Why

by_yaml 的 `init_vars`/`$init_var` 机制主要解决“结构化节点的编译期注入”(loader params 与部分路径),但无法把 demand/workflow YAML 当作可复用的“参数化配置模板”在更大范围内复用(例如任意字段的路径、sheet 名、资源 id、注释块中的 SQL/表达式片段等).

我们已引入 `src/scalim/vendor/litejinja2/`(轻量 Jinja2 子集). 现在需要把它作为 YAML 读取前的预编译步骤,让调用方通过 `template_vars` 一次性注入 `{{ x }}` 值,从而减少重复 YAML 与外部 glue code.

## What Changes

- by_yaml `run/compile` 与 workflow `run_workflow` 增加可选参数 `template_vars: Mapping[str, object]`,用于模板预编译注入.
- 当且仅当调用方显式提供 `template_vars` 时,系统在读取 YAML 文本后、YAML parse 之前执行 LiteJinja2 预渲染:
  - demand YAML(含其 import fragments)
  - workflow YAML
- 模板缺失变量在编译期 fail-fast: `{{ missing }}` 若无法从 `template_vars` 解析,必须抛出可诊断错误(包含入口/文件上下文).
- 提供“预编译缓存”以避免重复解析同一模板字符串(基于 `litejinja2.Environment` 的缓存能力或等价机制).
- 与现有 `$init_var` 互补:
  - `{{ ... }}` 负责“文本层参数化”(覆盖面更大,但最终必须生成合法 YAML)
  - `{$init_var: ...}` 保持为“结构化节点注入”(类型保真、一次性编译期解析、避免字符串拼装歧义)

## Capabilities

### New Capabilities
- `yaml-template-vars-precompile`: 允许 demand/workflow YAML 在文本层使用 LiteJinja2(`{{ ... }}`/`{% ... %}`)预编译,并通过 `template_vars` 注入变量;缺失变量 fail-fast;支持缓存.

### Modified Capabilities
- `dsl-runtime-structure`: by_yaml runtime 的 `run/compile` / workflow runtime 的 `run_workflow` 对外入口新增 `template_vars` 注入参数,并定义其触发/错误语义.

## Impact

- 受影响代码(示例,非详尽):
  - by_yaml 入口与 contracts: `src/scalim/dsl/by_yaml/runtime/entrypoints.py`, `src/scalim/dsl/by_yaml/runtime/contracts.py`
  - demand YAML loader/imports: `src/scalim/dsl/by_yaml/config_parsing/loader.py`, `src/scalim/dsl/by_yaml/config_parsing/imports.py`
  - workflow YAML loader: `src/scalim/dsl/by_yaml/workflow.py`, `src/scalim/dsl/by_yaml/runtime/workflow_entrypoints.py`
  - LiteJinja2: `src/scalim/vendor/litejinja2/`(需要补齐 strict-undefined/fail-fast 能力)
- Public API: 新增可选参数,保持现有调用不受影响(未传 `template_vars` 时不启用模板预编译).
- 安全与治理: 模板表达式会执行 LiteJinja2 的表达式解析(含属性/方法访问能力). 该能力仅建议在“受信 YAML + 受信 template_vars”场景启用;不对不可信 YAML 开启.

