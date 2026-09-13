# language: zh-CN
# capability: execution-call-by-memoization
# purpose: 为 `ctx-free call_by` 派生字段提供实验性 LRU 记忆化：字段级 allow/deny 过滤、硬上限 LRU、与可选性能统计日志（默认关闭）。 [rev:c25]
# scope: src/scalim/
功能: execution-call-by-memoization

  @req:r33 @human
  场景: Opt-in ctx-free call_by memoization
    - 当且仅当启用实验性开关时，系统 MUST 对满足条件的 `ctx-free call_by` 派生字段启用“按字段 LRU”记忆化；默认 MUST 关闭。
      容量与准入由 `SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES` 单一决定：

      | 取值 | 结果 |
      | --- | --- |
      | 未设置 / `0` / 负数 | 不启用 `call_by` 记忆化（行为等价于未实现该特性） |
      | 正整数 `N` | 仅对“不需要 `$ctx` 注入”的 `call_by` 字段启用缓存候选，且每字段容量上限为 `N` |
  @req:r277 @human
  场景: Field allow/deny filter for memoization
    - 系统 MUST 提供字段级过滤策略（`..._ALLOW` / `..._DENY`），使用户可明确选择哪些字段参与 memoization、哪些被排除。

      | `..._ALLOW` | `..._DENY` | 缓存候选 |
      | --- | --- | --- |
      | 未设置或解析为空 | 任意 | 未被 deny 排除的字段 |
      | 非空 patterns | 任意 | 仅匹配任一 allow pattern 的字段 |
      | 任意 | 任意 | 同时匹配 allow 与 deny 的字段 MUST 被排除
  @req:r402 @human
  场景: Bounded memory and safe semantics
    - 系统 MUST 为 memoization 提供硬上限（见 r33 的 `MAX_ENTRIES` 表，不得无界增长），并保持可预测的语义边界。
    当 某 `ctx-free call_by` 字段被启用 memoization
    那么 系统 MUST 仅缓存 calculator 成功返回的结果
  @req:r498 @human
  场景: Optional performance logging for ROI
    - 系统 MUST 提供实验性日志开关，以 `scalim.performance` 输出 memoization 的聚合统计，用于线上判断 ROI；默认 MUST 不输出。
    当 未启用 `SCALIM_EXP_CALL_BY_MEMOIZE_LOG_STATS`
    那么 系统 MUST 不输出 memoization 聚合统计日志
    当 启用 `SCALIM_EXP_CALL_BY_MEMOIZE_LOG_STATS`
    那么 系统 MUST 仅输出字段级聚合计数/比率等元信息
