# SUPERSEDED（已转正）

本 notplan 草案 **不再作为讨论/实现 SSOT**。

| 项 | 值 |
|----|-----|
| 状态 | superseded |
| 替代 active change | `c20-compute-expr-rowwise-fusion`（`llmanspec/changes/c20-compute-expr-rowwise-fusion/`） |
| 转正日期 | 2026-08-01 |
| 范围修订 | 旧稿「第一期仅 `compute_expr`、不含 `call_by`」**已否决为默认范围**。Active change 在安全外壳下覆盖 **无 `$ctx` 的 `call_by`**（MVP 测到的 N×M 热点）；**不**隐式合并多次 call_by 为一次调用（那是 `c0-call-by-multi-output-fusion`，仍 notplan）。 |

请只读并修改：`llmanspec/changes/c20-compute-expr-rowwise-fusion/{proposal,design,tasks}.md`。

历史长文已移除，避免与 active change 双源漂移。
