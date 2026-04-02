## Why

`imports` / `$import` 是 YAML DSL 中最有价值的复用能力之一,但当前问题也最明显:

- 允许范围过广,语义渗透到 authoring 与 control-plane 的混合区域
- workflow schema 甚至还曾经暴露 `$import`,而 runtime 不支持
- 一旦不澄清允许范围,imports 会继续放大 drift 与理解成本

与此同时,我们已经明确不希望把它整体替换为 profile/preset,因为 demand authoring 仍然需要复用“最佳实践片段”。

## What Changes

- 单独定义 demand `imports` / `$import` 的主线允许范围
- 明确 workflow 不支持 imports expansion
- 把 imports 允许范围与 authoring surface 绑定,而不是继续按“到处都能 overlay”扩张

## Scope

包括:
- demand `imports`
- demand `$import`
- workflow imports 的边界说明

不包括:
- imports expansion 的 editor/tooling 接口设计
- 具体 runtime policy (`guardrails` / `retry`) 的最终去留
- write policy 的最终 SSOT

## Expected Outcome

- demand 仍保留高价值复用能力
- imports 的边界与主线 DSL authoring surface 对齐
- workflow 不再被拉入 imports 语义扩张
