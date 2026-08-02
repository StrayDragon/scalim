# 基准测试

??? note "适用读者"
    - 关注性能回归与基准对比的开发者/贡献者
    - 需要理解 benchmark 报告含义的使用方

本节包含 benchmark 的报告阅读与对比参考.

阅读顺序:

- 先了解运行时行为边界(尤其是 `adaptive`): [并行模式(seq/adaptive)](../architecture/parallel-modes.md)
- **0.10.0** write-precompute 人类可读性能专页（图表 / 规模矩阵）: [write-precompute-0.10](../getting-started/write-precompute-0.10.md)
- **0.10.0** row-wise fusion 对拍专页: [rowwise-fusion-0.10](../getting-started/rowwise-fusion-0.10.md)
- 跑基准与保存基线: [Guide](guide.md)
- 阅读对比报告: [Compare Report](compare-report.md)
