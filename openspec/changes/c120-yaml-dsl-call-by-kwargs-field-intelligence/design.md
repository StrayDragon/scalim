## Context

当前 YAML DSL LSP 对 `call_by: "pkg.mod:fn(...)"` 的支持偏“Python 引用”视角：当光标位于 `pkg.mod:fn` 上时，可以 definition/hover/completion 到 Python 定义；但当光标位于参数段（`(...)`）里时，LSP 目前不会识别 `kwargs` 的值部分其实常用于引用 YAML DSL 的 `fields.*`（例如 `order_amount=order_amount`）。

因此用户在写/改 `call_by` 时缺少：
- 通过 hover 了解字段含义
- 通过 definition 快速跳到字段声明
- 在 `=` 右侧通过 Ctrl+Space 补全可用 field ids

约束：
- 只解析 `=` 右侧的值为 field-id token；左侧参数名保持 Python 语义（不提供 field 跳转/hover）。
- 不执行用户代码；仅静态解析。
- 解析失败必须降级为空结果 + warnings，不能导致 LSP 能力整体失效。
- 性能敏感：应当是轻量字符串扫描/定位，复用已有 debounce 与缓存（effective_view / entity_index 等）。

## Goals / Non-Goals

**Goals:**
- 在 `call_by` 字符串的参数段内，对 `name=<value>` 的 `<value>` token 提供 field 智能：
  - hover：字段卡片（与 compute/where 一致）
  - definition：跳转到字段声明（跨 imports 展开可定位）
  - completion：在 `=` 右侧（含空值、部分输入）返回 field ids（Ctrl+Space 必须可用）
- token 识别只发生在 kwargs 值位置，不影响现有 Python 引用（`pkg.mod:fn`）的语义能力。

**Non-Goals:**
- 不在本变更中支持“复杂 Python 表达式”参数值（例如 `x=a+1`、`x=foo(bar)`）的完整解析；v1 仅把简单 identifier token 视为 field-id。
- 不提供 kwargs 左侧参数名的 Python 层智能（参数名补全/签名提示等）。

## Decisions

1) **在 cursor extraction 层引入 `call_by kwargs value token` 的识别**
- 现状：`call_by` 抽取会把 `pkg.mod:fn(a=1)` 视为 head reference `pkg.mod:fn`，且 range 不包含参数段。
- 变更：当光标落在参数段内时，新增抽取分支：
  - 若光标命中 `=` 右侧的 identifier token，则返回 `kind=expression_token`（或新 kind）并携带 token/range；
  - 若光标命中 `=` 左侧（参数名）或其它位置，返回空（或继续按 head reference 规则处理）。

2) **复用现有 field token 解析/渲染能力**
- hover/definition/completion 的 field 候选与解析，应复用现有表达式/输出字段智能的实现（以 effective_view 的 fields SSOT 为准），避免在 server 层复制字段解析规则。

3) **completion 触发策略**
- 保证 Ctrl+Space 可用（关键验收）。
- 自动触发仅依赖有限 triggerCharacters（如 `=`/`_`/字母不作为 trigger），避免输入每个字符都触发 completion 造成卡顿。
- 对空值（`x=` 或 `x= `）必须能稳定提取 value_range，确保 completion handler 会进入并返回候选。

## Risks / Trade-offs

- [误命中] 参数段内也可能出现字符串/数字等 → 仅把“未引用/未引号包裹的 identifier token”视为 field-id，其他类型直接降级为空。
- [解析复杂度] 需要在不引入完整 Python parser 的前提下定位 `=` 与 token range → 使用轻量扫描并处理最小必要的引号/括号嵌套规则，遇到不确定语法时降级为空 + warnings。
- [一致性] compute/where 与 call_by kwargs 值的字段集合一致性 → 使用同一套“可见 fields”来源，避免不同位置候选列表不一致。
