# 基准测试

??? note "适用读者"
    - 关注性能回归与基准对比的开发者/贡献者
    - 需要理解 benchmark 报告含义的使用方

本节包含 benchmark 的报告阅读与对比参考.

阅读顺序:

- 先了解运行时行为边界(尤其是 `adaptive`): [并行模式(seq/adaptive)](../architecture/parallel-modes.md)
- **0.10.0** 版本亮点总览（默认行为 / opt-in / 迁移最短清单）: [0.10.0 重点特性](../releases/0.10.0/)
- 对拍专页: [write-precompute](../releases/write-precompute-0.10.md) · [row-wise fusion](../releases/rowwise-fusion-0.10.md) · [lookup chunk 并行](../releases/lookup-chunk-parallel-0.10.md)
- **外部基线对比（scalim vs pandas 惯用法，选型参考）**: [External Baseline](external-baseline.md)
- 跑基准与保存基线: [Guide](guide.md)
- 阅读对比报告: [Compare Report](compare-report.md)
