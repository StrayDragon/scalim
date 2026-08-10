# Proposal: batch call_by only

> 一句话描述: 仅保留「列式 batch `call_by`」作为调用次数杠杆的候选；memo / 并行 / multi-output 已拆出或已落地，不在本草案范围。

> **状态（2026-08-10）**：范围已裁剪为 **batch call_by only**。旧「call-count-reduction + parallelism」大包已废止；`design.md` 已删，避免双源。

## 已由其它路径覆盖（勿重复开 change）

| 能力 | 现状 |
|------|------|
| compute-expr / 无 `$ctx` call_by rowwise fusion | 已落地：`archive/2026-08-02-c20-compute-expr-rowwise-fusion` |
| write-precompute | 已落地：`archive/2026-08-01-c10-write-precompute-derived-fields` |
| 有界 call_by memo | 已有实验开关：`SCALIM_EXP_CALL_BY_MEMOIZE_*`（`call_by_memoization.py`） |
| 显式 multi-output / call group（仍 row-mode） | 另案：`llmanspec/notplan/c0-call-by-multi-output-fusion/` |
| refloader chunk 并行 | 已落地：`archive/2026-08-02-c30-refloader-chunk-parallelism` |

## 本草案唯一开放范围

- **batch `call_by`**：按字段对当前批次做一次列式调用（输入/输出为列视图，避免 `List[Dict]` 打包）。
- 默认不启用；须 opt-in；须单独收敛 `$ctx` / 错误粒度 / 可观测性语义后再转正。
- 转正门控：真实或合成 bench 证明 **fusion + EXP memo 之后** 仍是「调用次数主导」。

## 非目标

- 不再包含：框架级并行 compute、通用 memo API、performance profiles、与 c20 重复的隐式 fusion。
- 纯标准库；不引入 C/Cython 扩展作为近期目标。

## Impact（转正时）

- DSL/IR/runtime 新增 batch 调用形态（破坏面：用户函数签名与 `$ctx`）。
- 与 `c0-call-by-multi-output-fusion` 互补：batch 改列式 API；multi-output 保 row-mode。
