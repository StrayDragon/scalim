# 版本亮点

??? note "适用读者"
    - 准备升级到某次 release 的使用方
    - 需要给业务方讲清「本版默认变了什么 / 要不要改 YAML」的维护者与 agent

本目录收录**版本级重点特性**（默认行为变化、opt-in 能力、对拍证据），与 YAML DSL **breaking 升级批次**分开：

| 文档类型 | 放哪 | 何时看 |
|----------|------|--------|
| Breaking / 字段迁移 | [YAML DSL 升级指南](../yaml-dsl/upgrades/index.md)（SSOT：`agentdev/skills/.../upgrades/`） | 旧配置 validate 报错、字段已删 |
| 版本亮点 / 性能与默认行为 | **本目录** | 发版说明、评估要不要改运行参数、看对拍数字 |

运行期语义正文仍在架构 / 用户指南；本目录不替代它们，只做「升级时先读」的入口。

## 已发布

- [0.10.0 重点特性](0.10.0.md) — write-precompute / row-wise fusion / lookup chunk 并行
