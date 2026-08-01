# Design: YAML vs Python policy boundary（调研壳）

## 范围

只做 **盘点 + 原则草案 + follow-up 列表**。不改 `src/scalim` schema，不 `change start` 除非承接 agent 升级为 Full。

## 与 c30 的关系

- c30 **保留** `sources.*.lookup_chunk_size`（keys 分片大小）。
- c30 **不**新增 YAML 并行键；并行 = Python opt-in。
- 本 change 评估该键（及其它策略键）是否 **中长期** 迁出 YAML——**独立决策**，不阻塞 c30 apply。

## 建议工作方式（后续 agent）

1. 读 `docs/doc/yaml-dsl/capability-matrix.md` + schema models 生成 R1 表。
2. 对照 `AGENTS.md` Hard Rules（YAML vs Python book policy 等）写 R2。
3. 输出 R3：0～3 个候选 `cN-...` 标题 + 一句范围；或「结论：暂不迁」。
4. 需要行为合约时再走 `llman-sdd-propose` / Specs landing。

## 非目标

- 实现迁移或 deprecation 警告（除非 R3 明确开子 change）。
- 与 c10/c20/c30 实现纠缠。
