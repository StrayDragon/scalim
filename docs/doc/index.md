<p align="center">
  <img src="assets/logo.svg" alt="Scalim logo" width="100%">
</p>

# 首页

## 基本介绍

??? note "适用读者"
    - 使用方开发者/数据同学(写配置、跑任务、排查问题)
    - 项目贡献者(需要理解边界与结构)

这里整理 Scalim 的使用与开发文档,优先解决“怎么写配置/怎么跑/怎么排查”的问题.

如果你在改动框架行为/边界,建议先看: [OpenSpec 规范](specs/index.md)

## 第一次来先看这些

第一次上手,照这个顺序看就行:

1. 先跑通: [入门](getting-started/index.md) → [写 YAML](yaml-dsl/index.md) → [YAML 语法速查](yaml-dsl/syntax.md)
2. 写得完整: [YAML 用户指南](yaml-dsl/user-guide.md)(需要补全就看 [编辑器](yaml-dsl/editor.md))
3. 跑得更快: [并行模式(seq/adaptive)](architecture/parallel-modes.md)
4. 遇到问题: [可视化工具](viz/scalim-viz.md) / [基准测试](benchmark/index.md)

想弄清楚原理,再看下面这组:

- 原理与架构: [架构入口](architecture/index.md) → [架构详解](architecture/arch.md) → [OpenSpec 规范](specs/index.md)
- 参与开发: [仓库开发约定](dev/repo-guide.md) → [如何阅读本项目](getting-started/reading-guide.md)
