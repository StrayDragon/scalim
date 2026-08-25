# language: zh-CN
# capability: yaml-dsl-lsp-semantics-core
# purpose: 定义 LSP 编辑器语义核心：project discovery、静态无副作用 diagnostics、Python 引用定位、光标位置抽取（call_by kwargs / compute 表达式 token），均不执行用户代码。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: yaml-dsl-lsp-semantics-core

  @req:r119 @human
  场景: Editor semantics core MUST expose project discovery
    - 系统 MUST 提供 project discovery 能力，用于为 editor/LSP 侧推导： - `project_root` - `scalim_yaml_path`（可为空） - `allowed_yaml_roots` - `python_roots`

  @req:r361 @human
  场景: Editor semantics core MUST expose diagnostics without invoking CLI
    - 系统 MUST 提供 diagnostics API，且 MUST 直接复用 library 语义（schema/validator/unknown-fields），不得通过 shell-out 调用 CLI。

  @req:r482 @human
  场景: Editor semantics core MUST be static and side-effect free
    - 系统 MUST 保证 editor 语义为静态解析： - MUST NOT 执行用户代码（仅允许文件系统读取与 AST 解析） - MUST NOT 修改进程级全局状态（例如 `sys.path`、`sys.meta_path`）

  @req:r563 @human
  场景: Python reference resolution MUST be filesystem + AST based
    - 系统 MUST 支持对 Python 引用进行静态解析并定位定义位置： - 引用格式 MUST 支持 `module:attr` 与 `module.attr` - 引用格式 MUST 支持相对模块引用（前导 `.`），例如 `.loaders:func` / `..loaders:func` - 当引用为相对模块时，系统 MUST 基于 `yaml_path`（文档路径）与 project discovery 的 `python_roots` 推导 `base_module_path`，并将其规范化为绝对模块路径后再进行解析 - 定位 MUST 基于 `python_roots` + 文件系统模块解析 + AST 符号索引 - 对 class-style 的多段属性路径（例如 `module.path:obj.method`），系统 MUST 在不执行用户代码的前提下尝试静态推断 `obj` 的候选类（例如来自 `obj = Klass()` / `obj: Klass = ...` / 简单 import/alias），并在可推断时优先定位到真实实现（例如 `Klass.method`） - 当 `obj.method` 可推断时，definition MUST 返回 **多个** locations，且顺序 MUST 稳定：第一个为推断到的真实实现，其后为 `obj` 的定义/赋值等备选位置（用于回溯引用来源）

  @req:r626 @human
  场景: Editor semantics core MUST support extracting Python references by cursor positi
    - 系统 MUST 提供一个基于 `yaml_text + position` 的抽取能力，用于把编辑器光标映射到 YAML DSL 内的 Python 引用字段。 抽取结果 MUST 至少包含： - 命中的 YAML 字段路径（canonical dot path） - 命中的 Python 引用字符串（raw value 或经 `call_by` 头部解析后的 reference） - 命中范围 `range`（以 1-based 表示，供 server 转换为 LSP range） - 失败时的可诊断 warnings（不得抛出未捕获异常） 支持字段集合 v1 MUST 至少覆盖： - `loader` - `call_by` - `retry.should_retry`（包含常见嵌套路径下的该字段） 当上述字段的 scalar 为 YAML block scalar（`|`/`>` 及其变体）且跨多行时： - 抽取 MUST 仍然可用 - 返回的 `range` MUST 精确覆盖“光标所在行内”的命中 token（不得要求用一个跨行 range 覆盖整个 block）

  @req:r673 @human
  场景: Editor semantics core MUST extract field-id tokens from `call_by` kwargs value p
    - 系统 MUST 扩展光标抽取能力，使其能在 `call_by` 的参数段（`(...)`）内识别 kwargs 的 `=` **右侧** field-id token，并用于 editor/LSP 语义能力。 覆盖 callsite 至少包括： - `fields.*.call_by` - `outputs[*].aggregate.fields.*.call_by` - builtin callable：`call_by: "^<id>(...)"`（head 为 builtin id） 抽取必须满足： - 抽取 MUST 仅对 `=` 右侧生效；`=` 左侧 kwargs 名称 MUST NOT 被当作 field-id - token 抽取 MUST 返回精确 range（仅覆盖 token 本身） - 当值为空（例如 `x=` 或 `x= `）且用户触发 completion 时，抽取结果 MUST 能提供稳定的 value_range（用于 completion） - 解析失败 MUST 降级为空结果 + warnings（不得抛出未捕获异常） - 参数段解析 MUST 支持换行符与 Python 风格 `#` 注释（不在 string literal 内），以便 multiline `call_by`（含 YAML block scalar）仍可提供 token 抽取

  @req:r713 @human
  场景: expression identifier tokens MUST be resolvable to field definitions
    - 在 `compute`/`where` 等安全表达式字符串内,当光标位于某个 identifier token 上时,semantics core MUST 能静态解析该 token 并用于 editor 语义能力: - semantics core MUST 能抽取该 token 的精确 range（仅覆盖 token）。 - semantics core MUST 能将 token 解析为字段引用（在当前上下文作用域内），用于 hover/definition/completion。
  @req:r119 @human
  场景: nearest-wins-scalim-yaml-yields-discovery-payload
    - 必须成立：假如 某 `YAML` 文件位于项目子目录，且父目录链上存在 `scalim.yaml`；当 editor 调用 project discovery；那么 返回的 `project_root` MUST 为最近的 `scalim.yaml` 所在目录
    假如 某 `YAML` 文件位于项目子目录，且父目录链上存在 `scalim.yaml`
    当 editor 调用 project discovery
    那么 返回的 `project_root` MUST 为最近的 `scalim.yaml` 所在目录
  @req:r361 @human
  场景: diagnostics-are-computed-without-spawning-a-subprocess
    - 必须成立：当 editor 请求某 YAML 的 diagnostics；那么 系统 MUST 返回结构化 diagnostics（errors/warnings + path + range）
    当 editor 请求某 YAML 的 diagnostics
    那么 系统 MUST 返回结构化 diagnostics（errors/warnings + path + range）
  @req:r482 @human
  场景: resolving-definitions-does-not-mutate-process-globals
    - 必须成立：假如 editor 触发 go-to-definition；当 core 解析某 Python 引用；那么 解析过程 MUST NOT 改写进程级全局搜索路径
    假如 editor 触发 go-to-definition
    当 core 解析某 Python 引用
    那么 解析过程 MUST NOT 改写进程级全局搜索路径
  @req:r563 @human
  场景: definition-resolution-locates-a-python-function
    - 必须成立：假如 YAML 中某字段引用 `pkg.mod:func`；当 用户触发 go-to-definition；那么 系统 MUST 返回 `func` 定义所在文件与范围
    假如 YAML 中某字段引用 `pkg.mod:func`
    当 用户触发 go-to-definition
    那么 系统 MUST 返回 `func` 定义所在文件与范围

  @req:r563 @human
  场景: relative-module-definition-resolution-locates-a-python-funct
    - 必须成立：假如 YAML 文件位于某个 `python_roots` 之下；当 用户触发 go-to-definition 且 core 收到 `yaml_path + python_roots`；那么 系统 MUST 将 `.loaders` 规范化为绝对模块路径
    假如 YAML 文件位于某个 `python_roots` 之下
    当 用户触发 go-to-definition 且 core 收到 `yaml_path + python_roots`
    那么 系统 MUST 将 `.loaders` 规范化为绝对模块路径

  @req:r563 @human
  场景: relative-module-resolution-degrades-when-base-cannot-be-deri
    - 必须成立：假如 YAML 文件不在任何 `python_roots` 条目下；当 用户触发 go-to-definition；那么 系统 MUST 返回空 locations
    假如 YAML 文件不在任何 `python_roots` 条目下
    当 用户触发 go-to-definition
    那么 系统 MUST 返回空 locations

  @req:r563 @human
  场景: object-method-resolution-locates-class-method-and-returns-fa
    - 必须成立：假如 Python 模块 `pkg.mod` 内存在 `class Klass` 且其定义 `def a_method(self)`（可调用实现）；当 YAML 中某字段引用 `pkg.mod:some_ref.a_method`；那么 definition MUST 返回至少 2 个 locations
    假如 Python 模块 `pkg.mod` 内存在 `class Klass` 且其定义 `def a_method(self)`（可调用实现）
    当 YAML 中某字段引用 `pkg.mod:some_ref.a_method`
    那么 definition MUST 返回至少 2 个 locations

  @req:r563 @human
  场景: object-method-resolution-follows-simple-imports
    - 必须成立：假如 Python 模块 `pkg.mod` 内存在 `from pkg.other import Klass`；当 YAML 中某字段引用 `pkg.mod:some_ref.a_method`；那么 第一个 location MUST 指向 `pkg.other.Klass.a_method` 的定义位置
    假如 Python 模块 `pkg.mod` 内存在 `from pkg.other import Klass`
    当 YAML 中某字段引用 `pkg.mod:some_ref.a_method`
    那么 第一个 location MUST 指向 `pkg.other.Klass.a_method` 的定义位置

  @req:r563 @human
  场景: object-method-resolution-follows-imported-object-single-hop
    - 必须成立：假如 Python 模块 `pkg.mod` 内存在 `from pkg.other import some_ref`；当 YAML 中某字段引用 `pkg.mod:some_ref.a_method`；那么 definition MUST 返回至少 3 个 locations
    假如 Python 模块 `pkg.mod` 内存在 `from pkg.other import some_ref`
    当 YAML 中某字段引用 `pkg.mod:some_ref.a_method`
    那么 definition MUST 返回至少 3 个 locations

  @req:r563 @human
  场景: object-method-resolution-degrades-when-class-cannot-be-infer
    - 必须成立：假如 Python 模块 `pkg.mod` 内存在 `some_ref = factory()`（返回类型未知）；当 YAML 中某字段引用 `pkg.mod:some_ref.a_method`；那么 definition MUST NOT crash
    假如 Python 模块 `pkg.mod` 内存在 `some_ref = factory()`（返回类型未知）
    当 YAML 中某字段引用 `pkg.mod:some_ref.a_method`
    那么 definition MUST NOT crash
  @req:r626 @human
  场景: cursor-inside-a-scalar-string-yields-extracted-reference-ran
    - 必须成立：假如 某 demand YAML 包含 `loader: "pkg.mod:func"` 且光标位于该字符串值内部；当 editor semantics core 执行光标抽取；那么 MUST 返回 `yaml_path` 指向该字段
    假如 某 demand YAML 包含 `loader: "pkg.mod:func"` 且光标位于该字符串值内部
    当 editor semantics core 执行光标抽取
    那么 MUST 返回 `yaml_path` 指向该字段

  @req:r626 @human
  场景: cursor-inside-a-block-scalar-yields-extracted-reference-rang
    - 必须成立：假如 某 demand YAML 包含： `call_by: |` ` pkg.mod:fn(a=1)`；当 光标位于 `pkg.mod:fn` 区间并触发抽取；那么 MUST 返回 `reference` 等于 `pkg.mod:fn`
    假如 某 demand YAML 包含： `call_by: |` ` pkg.mod:fn(a=1)`
    当 光标位于 `pkg.mod:fn` 区间并触发抽取
    那么 MUST 返回 `reference` 等于 `pkg.mod:fn`

  @req:r626 @human
  场景: call-by-reference-with-args-yields-head-reference
    - 必须成立：假如 某 demand YAML 包含 `call_by: "pkg.mod:fn(a=1)"` 且光标位于 `pkg.mod:fn` 区间；当 editor semantics core 执行光标抽取；那么 MUST 返回 `reference` 等于 `pkg.mod:fn`
    假如 某 demand YAML 包含 `call_by: "pkg.mod:fn(a=1)"` 且光标位于 `pkg.mod:fn` 区间
    当 editor semantics core 执行光标抽取
    那么 MUST 返回 `reference` 等于 `pkg.mod:fn`

  @req:r626 @human
  场景: parse-failure-degrades-to-empty-result-with-warnings
    - 必须成立：假如 某 YAML 语法不完整或无法被解析；当 editor semantics core 执行光标抽取；那么 MUST 返回空结果
    假如 某 YAML 语法不完整或无法被解析
    当 editor semantics core 执行光标抽取
    那么 MUST 返回空结果
  @req:r673 @human
  场景: cursor-on-kwargs-value-token-yields-extracted-field-referenc
    - 必须成立：假如 YAML 包含 `call_by: "pkg.mod:fn(x=a)"`；当 光标位于 `a` 上并触发 hover/definition；那么 抽取结果 MUST 将 token `a` 解析为字段引用
    假如 YAML 包含 `call_by: "pkg.mod:fn(x=a)"`
    当 光标位于 `a` 上并触发 hover/definition
    那么 抽取结果 MUST 将 token `a` 解析为字段引用

  @req:r673 @human
  场景: cursor-on-kwargs-value-token-in-multiline-call-by-yields-ext
    - 必须成立：假如 YAML 包含： `call_by: |` ` pkg.mod:fn(` ` x=a, # comment` ` )`；当 光标位于 `a` 上并触发 hover/definition；那么 抽取结果 MUST 将 token `a` 解析为字段引用
    假如 YAML 包含： `call_by: |` ` pkg.mod:fn(` ` x=a, # comment` ` )`
    当 光标位于 `a` 上并触发 hover/definition
    那么 抽取结果 MUST 将 token `a` 解析为字段引用

  @req:r673 @human
  场景: cursor-on-kwargs-name-yields-empty-field-extraction
    - 必须成立：假如 YAML 包含 `call_by: "pkg.mod:fn(x=a)"`；当 光标位于 `x` 上并触发 hover/definition；那么 系统 MUST NOT 将 `x` 解析为字段引用
    假如 YAML 包含 `call_by: "pkg.mod:fn(x=a)"`
    当 光标位于 `x` 上并触发 hover/definition
    那么 系统 MUST NOT 将 `x` 解析为字段引用
  @req:r713 @human
  场景: compute-expression-token-resolves-to-field-definition
    - 必须成立：假如 YAML 声明 `fields.a: ...` 且存在 `fields.sum.compute: \"a + 1\"`；当 光标位于表达式中的 token `a` 上并触发 definition/hover；那么 token MUST 解析为对 `fields.a` 的引用
    假如 YAML 声明 `fields.a: ...` 且存在 `fields.sum.compute: \"a + 1\"`
    当 光标位于表达式中的 token `a` 上并触发 definition/hover
    那么 token MUST 解析为对 `fields.a` 的引用
