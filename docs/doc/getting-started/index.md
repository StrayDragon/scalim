# 入门

??? note "适用读者"
    - 初次上手的使用方开发者/数据同学
    - 项目贡献者(需要从入口快速定位实现)

本节帮你把第一次上手要看的东西串起来: 先跑通,再补全细节,最后再考虑调参和排查.

- 写配置/跑起来: [写 YAML](../yaml-dsl/index.md) → [语法速查](../yaml-dsl/syntax.md) → [用户指南](../yaml-dsl/user-guide.md)
- Python 导入入口: [公共 API 导入指南](public-api.gen.md)
- 配套工具: [补全/编辑体验](../yaml-dsl/editor.md) / [集成AI环境](../yaml-dsl/agent-skill.md) / [可视化工具](../viz/scalim-viz.md) / [Run Stats](../viz/run-stats.md) / [基准测试](../benchmark/index.md)
- 需要调参时再看: [并行模式(seq/adaptive)](../architecture/parallel-modes.md)
- 宽表 Excel 峰值 / `column_buffered` vs `column_chunked`: [文件写出布局](excel-column-residency.md)
- keys lookup 分片 / 何时用 `LookupChunking`: [用户指南 §4.4.3](../yaml-dsl/user-guide.md#443-lookupchunking-keys-分片python-runtime)
- **升级到 0.10.0**：先看 [版本亮点 · 0.10.0 重点特性](../releases/0.10.0/)（默认行为 / opt-in / 对拍专页）
- 想贡献代码: [仓库开发约定](../dev/repo-guide.md) → [如何阅读本项目](reading-guide.md)
