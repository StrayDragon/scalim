## Context

当前 by_yaml 体系内已有两类“动态注入”能力:

- **结构化编译期注入**: `init_vars` + `{$init_var: <name>}` 指令节点,用于在编译期把初始化对象注入到 loader params 模板与少量路径节点中(不做字符串子串插值).
- **workflow 编排期注入**: `workflow.runs[*].init_vars` 支持 `$ctx` 指令读取上游 node 的 JSON-like ctx,并合并到 node 级 `init_vars`.

这两类能力的共同特征是:

- 只覆盖“有限的字段位置/结构”,不把 YAML 当作可复用的“参数化文本模板”.
- 注入过程发生在 YAML parse 之后(结构化节点),并尽量保持类型保真与可诊断路径.

同时,仓库已引入 `src/scalim/vendor/litejinja2/` 作为轻量 Jinja2 子集,具备 `{{ var }}`/`{% if %}`/`{% for %}`/filters 以及模板缓存能力,但尚未用于 YAML DSL.

本变更希望在“读取 YAML 文本”阶段增加一个可选的预编译步骤:

1) 读取 YAML 文件文本
2) 使用 LiteJinja2 基于 `template_vars` 预渲染为“纯 YAML 文本”
3) 再进入既有链路: YAML parse → imports expand → validator → `DemandConfig -> IR` 编译 → execution

约束:

- `src/scalim/` 运行时边界必须兼容 Python 3.6.
- 文档治理: `.gen.*` 文件与 AUTOGEN 注入块不可手改;该变更仅新增/修改 OpenSpec 工件,不直接改 docs 生成物.
- 安全边界: allowlist 针对 Python 引用解析,但模板预编译发生在 allowlist 之前;因此该能力需明确“仅对受信 YAML/受信输入启用”.

## Goals / Non-Goals

**Goals:**

- by_yaml `run/compile` 与 workflow `run_workflow` 提供显式 `template_vars` 注入入口.
- 在 demand/workflow YAML parse 前执行 LiteJinja2 文本预编译,使 `path: {{ x }}` 等“非引号占位符”可工作.
- 预编译覆盖范围:
  - workflow YAML
  - demand YAML
  - demand 的 import fragments(通过 `imports/$import` 加载的 YAML 文件)
- 缺失变量 fail-fast: 若模板引用未在 `template_vars` 中提供且未通过模板自身兜底(例如 `| default(...)`)处理,必须抛出明确错误并带上下文.
- 提供“预编译缓存”以避免重复解析相同模板文本.
- 与 `$init_var` 形成互补: 文本参数化用于广覆盖配置复用,结构化注入继续用于类型保真与避免字符串拼装歧义.

**Non-Goals:**

- 不在 YAML authoring surface 内新增 `template_vars:` 段或其它“YAML 自声明变量”机制(v1 仅 API 注入).
- 不提供 env/文件/secret 等自动注入来源.
- 不引入完整 Jinja2 能力(不支持 include/macro 等).
- 不承诺对不可信 YAML 的安全沙箱(仅提供使用约束与文档警示).
- 不保证模板错误能精确映射到 YAML path/行列位置(v1 只保证入口/文件上下文 + 变量名等诊断信息).

## Decisions

### 1) 启用条件: 显式 opt-in

**Decision**: 仅当调用方显式提供 `template_vars`(非 `None`)时启用模板预编译;否则完全跳过,保持现有行为.

**Rationale**:

- 避免把 YAML 中的 `{{ ... }}`(可能是 SQL/其它系统模板)误解释为 LiteJinja2,造成隐式 breaking.
- 满足“对选定 YAML 进行预处理”的诉求: 调用方通过 API 参数显式选择是否预编译.

实现上可在 opt-in 前做一次快速文本探测(`{{` 或 `{%`)以避免无模板时的额外开销(优化,非语义要求).

### 2) 渲染层级: 文本层预编译(先 render 再 parse)

**Decision**: 在 YAML parse 之前对原始文本做模板渲染,渲染结果再交给 PyYAML safe_load.

**Rationale**:

- 支持 `path: {{ x }}` 这类不加引号的写法(对象层渲染无法覆盖).
- 语义清晰: “模板输出必须是合法 YAML 文本”,随后所有语义校验与编译逻辑都复用既有链路.

### 3) 缺失变量语义: strict-undefined + default 兜底

**Decision**: 当启用预编译时,模板渲染处于 strict-undefined 语义:

- 直接引用未提供变量(例如 `{{ missing }}`)必须 fail-fast.
- 若模板显式提供兜底(例如 `{{ missing | default('x') }}` 或 `if missing is defined`),则允许渲染成功.

**Rationale**:

- 与调用方期望一致: 缺失变量应尽早暴露,避免 silent empty-string 导致难排查.
- 保留模板自身“显式兜底”能力,便于写兼容模板.

这要求对 `src/scalim/vendor/litejinja2/` 增加 strict 模式支持(默认行为保持不变,避免影响现有使用方).

### 4) 覆盖 imports: fragments 也必须预编译

**Decision**: 当 demand YAML 启用预编译时,imports expansion 读取的 fragment YAML 文件也必须在 safe_load 前执行同一份 `template_vars` 的预编译.

**Rationale**:

- imports 的核心价值是“复用片段”. 若 fragments 不支持模板化,会导致“顶层可模板化、片段不可模板化”的不一致,降低复用价值.
- imports loader 当前在 `_load_yaml_mapping` 内直接 safe_load 文件,需要将“读取文本→预编译→safe_load”能力下沉到该层.

### 5) API 形态: mapping 注入 + 统一命名

**Decision**:

- by_yaml `run/compile` 与 `RunOptions` 增加 `template_vars: Optional[Dict[str, object]]`.
- workflow `run_workflow` 增加同名参数,并将其用于 workflow YAML 本身的预编译.
- workflow 运行中对 demand YAML 的加载复用 by_yaml runtime loader,从而自动获得同一 `template_vars` 能力(无需额外 per-run YAML 字段).

**Rationale**:

- 命名统一避免用户在不同入口记忆不同参数名.
- 将能力收敛为“预编译阶段的输入”,与 `init_vars`(结构化编译期注入)清晰区分.

### 6) 预编译缓存: 复用 litejinja2 缓存

**Decision**: 预编译阶段使用 `litejinja2.Environment`(或其等价全局实例)缓存解析后的模板(AST/nodes),以减少重复渲染的解析开销.

**Rationale**:

- LiteJinja2 已内置按 template_string 缓存 `Template` 的机制(`Environment.from_string`).
- 缓存对语义透明,且可通过现有 `clear_cache()` 做测试隔离.

## Risks / Trade-offs

- **[YAML 注入/转义复杂度]** 文本层渲染要求变量最终输出为合法 YAML;复杂对象的 `str(...)` 可能产生不可解析文本。→ **Mitigation**: v1 明确约束“调用方负责提供可渲染为 YAML 的值”;错误以 YAML parse failure 暴露;后续可扩展 `tojson/toyaml` filters.
- **[安全面扩大]** 模板表达式支持属性/方法访问,若传入不可信对象可能触发副作用。→ **Mitigation**: 文档强提示“仅对受信 YAML/受信 template_vars 启用”;尽量只传递 JSON-like/纯数据对象.
- **[可诊断性]** 模板错误发生在 YAML parse 前,无法给出精确 YAML path。→ **Mitigation**: 错误消息必须包含入口/文件路径(以及 import trace),并报告缺失变量名/表达式;后续可增强行列定位.
- **[imports 行为耦合]** imports loader 需要感知 template_vars,会增加函数签名传递。→ **Mitigation**: 将预编译封装为小的纯函数,并作为可选参数逐层透传,保持默认无行为变化.

## Migration Plan

- 该能力为 opt-in,默认关闭;无存量迁移要求.
- 迁移/启用方式:
  - 在 `run/compile/run_workflow` 调用时提供 `template_vars={...}`
  - 将 YAML 中需参数化位置改写为 LiteJinja2 模板(例如 `{{ output_path }}`)
- 回滚: 移除调用方 `template_vars` 参数并恢复 YAML 字面值.

## Open Questions

- 是否在后续版本引入安全序列化 filters(`tojson`/`toyaml`)以提升复杂类型注入的可控性?
> 暂时不需要, 但请在相关代码标注 'NOTE: ...'注释

- 是否需要提供更强的错误定位(例如渲染后 diff/行列号),以及其性能/实现复杂度权衡?
> 最好需要 在validate 阶段就要处理 还有一个考虑 我希望可以支持一些特殊处理 比如 在 workflow中支持 重映射之类 因为每个demand 可能通用化 我希望可以提供一个统一化方法


