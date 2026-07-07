## Status (2026-04-30)

- 本提案已降级为 not-plan 草案：先落地并验收 `c0-execution-hotpath-fastpaths`，仅当 `c0` 后仍存在“调用次数主导”的瓶颈时再推进。
- `multi-output / fusion` 已拆为独立方向以降低本提案改动面：见 `openspec/notplan-changes/c0-call-by-multi-output-fusion/`。

## Why

当字段派生的“逻辑厚度”很薄但字段数量/行数很大时，单纯优化每次调用的固定开销仍然可能触顶；进一步的收益来自于减少调用次数或利用多核。但这类能力如果设计不当，会带来明显的内存膨胀、调试困难或语义不一致。

## What Changes

- 探索并引入“减少 call 次数 / 并行化”的一组可选能力（默认不要求业务修改；必要时提供 opt-in；仅在 `c0` 之后仍必要时推进）：
  - `call_by` 批处理（batch call）：按“字段”而非“行”调用，把 N 行的输入以列式视图传入一次性计算（避免 `List[Dict]` 打包造成内存爆炸）。
  - **除 batch call 以外的可选路径**（需要在设计阶段选择/裁剪）：
    - 有界缓存（bounded memoization）：对纯函数/小域输入（如枚举格式化、布尔格式化）提供框架级的有限容量缓存，降低重复调用次数（需严格上界，避免内存失控）。
    - 并行化：批次级并行或字段层并行（需明确内存上界与错误语义；默认仅在 `speed` profile 下启用）。
- 复用 `c0` 的合成复现入口作为无业务数据评测基线，并为上述策略补充 synthetic case：
  - `.tmp/repro/scalim_hotpath_overhead/repro-execution-hotpath-overhead.py`
- 环境约束：默认实现必须为纯 Python 标准库方案；任何需要额外依赖（包括 vendors 审核成本较高的依赖、或 C/Cython 扩展）的路径仅作为“远期可选项”记录，不作为近期交付目标。

## Capabilities

### New Capabilities
- `execution-call-count-reduction`: 通过 batch/multi-output/memoization 等机制减少 per-row 调用次数，并提供可控内存上界。

### Modified Capabilities
- `parallel-execution`: 在保持语义与可观测性契约的前提下，扩展到 compute/loadref 方向的并行能力（以 opt-in 方式提供）。

## Impact

- 该方向的收益上限很高，但风险也更集中（内存放大、并发安全、错误语义与可观测性一致性）。因此必须与 `c0`/`c1` 分离推进，并以 profile/flag 方式逐步启用。
