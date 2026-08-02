# 入门

??? note "适用读者"
    - 初次上手的使用方开发者/数据同学
    - 项目贡献者(需要从入口快速定位实现)

本节帮你把第一次上手要看的东西串起来: 先跑通,再补全细节,最后再考虑调参和排查.

- 写配置/跑起来: [写 YAML](../yaml-dsl/index.md) → [语法速查](../yaml-dsl/syntax.md) → [用户指南](../yaml-dsl/user-guide.md)
- Python 导入入口: [公共 API 导入指南](public-api.gen.md)
- 配套工具: [补全/编辑体验](../yaml-dsl/editor.md) / [集成AI环境](../yaml-dsl/agent-skill.md) / [可视化工具](../viz/scalim-viz.md) / [基准测试](../benchmark/index.md)
- 需要调参时再看: [并行模式(seq/adaptive)](../architecture/parallel-modes.md)
- 宽表 Excel 峰值 / 列式 HOLD vs WINDOW: [Excel 列式写出策略](excel-column-residency.md)
- **0.10.0** 写出前延迟物化（默认更快 / 更省驻留）: [write-precompute 性能](write-precompute-0.10.md)
- **0.10.0** 同 deps 行内融合（减 N×M 框架税）: [row-wise fusion 性能](rowwise-fusion-0.10.md)
- **0.10.0** 同 LoadRef 分片并行（opt-in 重叠 RTT）: [lookup chunk 并行](lookup-chunk-parallel-0.10.md)
- 想贡献代码: [仓库开发约定](../dev/repo-guide.md) → [如何阅读本项目](reading-guide.md)
