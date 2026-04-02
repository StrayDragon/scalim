## Why

`resources.books.*.write_defaults` 与 `outputs[*].write` 目前共同描述写入策略,再叠加 `meta` / `audit` 等输出附加能力,形成了典型的“同一语义多入口”问题:

- 文档难讲清优先级
- schema/runtime/tests 需要同时维护多套入口
- 用户也很难判断“这个配置应该写在 resource 还是 output”

这类问题与 control-plane 边界相关,但足够具体,值得拆成独立提案审。

## What Changes

- 明确 `resources` 在主线中的分层语义: 哪些是可移植声明,哪些是 runtime overlay / write policy
- 单独定义输出写策略的 SSOT
- 明确 `meta` / `audit` 应属于 YAML 还是 runtime overrides
- 为后续实现提供更聚焦的边界与迁移路径

## Scope

包括:
- `resources.books/files` 的声明 vs overlay 分层
- `resources.books.*.write_defaults`
- `outputs[*].write`
- `meta`
- `audit`

不包括:
- `observability`
- `guardrails` / `retry`
- demand imports 全局策略

## Expected Outcome

- `resources` 的分层语义更清晰
- 输出写入策略将有单一主入口
- `meta` / `audit` 的归属面更清晰
- 文档与 typed overrides 的职责边界更稳定
