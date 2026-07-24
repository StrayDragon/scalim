# tasks: c0-remove-score-by-rank-builtin

> 移除 `score_by_rank` 内置后置派生字段，用 `compute` 表达式等价替代。
> BREAKING：指纹变化（score_by_rank 指纹行消失）、AGG_POST_PRODUCER_KEYS 枚举变更。

## Propose

- [x] 0.1 写好 `proposal.md` / `design.md`（compute 等价性验证与迁移方案）
- [x] 0.2 delta：`execution-derived-outputs`（add r802）
- [x] 0.3 delta：`yaml-dsl-write-policy-and-output-extras`（add r803）
- [x] 0.4 `llman sdd validate c0-remove-score-by-rank-builtin --strict --no-interactive`
