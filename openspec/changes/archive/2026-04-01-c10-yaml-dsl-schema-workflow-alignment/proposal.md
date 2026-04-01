## Why

本 change 聚焦当前最确定、最适合先落地的一组问题:

- `workflow.gen.json` 与 runtime parser 对 `workflow.resources` 的允许面不一致,典型问题是 schema 暴露 `$import` 但 parser/runtime 明确不支持.
- YAML schema 中存在多处“带数值约束但未声明显式数值类型”的洞,会导致 schema validate 与编辑器提示失真.
- 这类问题属于明确的 drift / hygiene 缺陷,不需要等更大的 control-plane 边界讨论结束就可以先收敛.

如果这层基础不先做好,后续无论是主线 YAML 收敛还是 `c999-yaml-dsl-lsp`,都会建立在不稳定的 schema/runtime 契约上。

## What Changes

- 明确并修复 workflow schema/runtime 在 `workflow.resources` 上的 drift:
  - schema 不再暴露 runtime 不支持的 keys
  - runtime 报错口径与 schema/文档一致
- 为 demand/workflow schema 增加数值约束自检:
  - 凡是声明 `minimum/maximum/...` 的字段,必须显式声明 `type:number|integer`
- 引入面向 CI 的 drift gate:
  - workflow 关键结构的 schema/runtime 允许字段集合一致性检查
  - schema numeric typing fail-fast

## Scope

本 change 仅处理“schema hygiene + workflow drift”。

包括:
- `workflow.resources` 的 schema/runtime 对齐
- schema numeric typing holes
- 相关错误信息与 drift gate

不包括:
- demand imports 的最终允许范围
- `observability` / `guardrails` / `retry` 等 control-plane 是否迁出 YAML
- `write_defaults` vs `outputs[*].write` 的 SSOT
- 面向编辑器/LSP 的内部语义接口设计

## Expected Outcome

- `demand.gen.json` / `workflow.gen.json` 的结构可信度提升,能作为更稳定的编辑器 schema 输入
- workflow 用户不再遇到“schema 通过但 runtime 不支持”的明显漂移
- 后续专题提案可以建立在一套更可靠的基础契约上
