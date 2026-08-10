> 一句话描述: 将用户最常用且需稳定的能力收敛到 `scalim.shortcuts.*`（资源领域统一入口 `scalim.shortcuts.resources`），提供受 public API 治理约束的稳定 facade。

## Why

当前 `scalim` 的对外用户 API 分散在多个入口模块中（`dsl.yaml_dsl` / `workflow` / `sinks` / 若干内部落盘协议等），对框架用户而言常见任务的认知与实现成本偏高：

- 用户需要同时理解 “authoring 层”(YAML) 与 “execution/IO 协议层”(例如 D-2 的 `manifest/latest.json`) 才能完成非常常用的消费动作（例如加载最新 outputs）。
- 很多用户侧代码会退化为“手写 JSON + 手写路径拼接 + 手写容错”，把内部协议形状扩散为事实公共契约，放大未来重构成本。
- 既有 public entrypoints 虽已被 `public-api-surface-governance` 编目治理，但“对新用户更简单的唯一入口”仍缺失。

与此同时，用户在 YAML 中的主要心智入口是 `workflow.resources.*`：无论是 outputs（books/files）还是 workflow-managed input artifacts / ctx store 的可见形态，本质上都属于“资源/工件”的发现、定位与消费。

因此我们希望把“用户最常用、最稳定的快捷能力”收敛到 `scalim.shortcuts.*` 下，并以 `scalim.shortcuts.resources` 作为资源领域的统一入口，让用户先学会一套稳定、可治理的 facade；内部实现与协议可继续迭代而不迫使用户修改调用方式。

## What Changes

这是一个低优先级的方向性提案（notplan-change）。它不要求立即实现，只固化后续演进路线与治理约束。

### 1) 方向：以 `scalim.shortcuts` 作为“用户快捷入口”命名空间

- `scalim.shortcuts` 表达：这里的 API 是 **用户侧快捷用法**（facade/shortcut），不是内部实现细节。
- 该命名空间不追求覆盖所有功能，而是聚焦“用户最常用且需要稳定”的最小集合。
- `scalim` 顶层仍保持“避免公共重导出聚合”的策略；`shortcuts` 是显式、可治理的例外入口。

### 2) 方向：以 `scalim.shortcuts.resources` 作为“资源/工件”统一入口（逐步扩展）

`scalim.shortcuts.resources` 计划作为资源领域的长期统一入口，按阶段逐步扩展其覆盖面：

- v1（已在 active change 中定义）：从 output root 发现最新发布的 outputs（books/files），隐藏 D-2 协议细节。
  - 参见 active change: `openspec/changes/c999-output-discovery-facade/`
- v2（候选）：纳入 workflow-managed input artifacts 的消费 facade（例如 “从 workflow artifacts 目录按 node_id/output_id 取输入工件”）。
- v3（候选）：纳入 ctx resources 的对外可见/可消费形态（仍保持边界：ctx 不是大对象仓库；大对象继续走资源/工件路径）。
- vN（候选）：其它资源/工件发现能力（例如诊断工件、可回放工件、导出物索引等）。

### 3) 治理：`shortcuts` 的 public API 必须受 `public-api-surface-governance` 约束

为避免 `shortcuts` 演化为“无边界工具箱”，本提案建议将以下约束作为未来实现的硬门禁：

- `scalim.shortcuts.*` 中每个对外符号 MUST 由 `__all__` 固定导出面，并纳入 public API manifest / suite 回归。
- docs/skills/notebooks MUST 优先引用 `scalim.shortcuts.*` 的官方用法，且 MUST NOT 推荐手写内部落盘协议细节。
- `shortcuts` MUST NOT re-export internal modules（尤其是 `_internal`、底层协议工具模块等），只暴露稳定 facade。

### 4) 迁移策略（提案层面）

- 新能力优先以 shortcut 形式引入，并将用户材料一次性升级到 shortcut 写法（不在文档中保留“旧写法兼容教程”）。
- 原有入口模块可以保留为“进阶/领域入口”，但不再作为新手首选路径；必要时通过 public API 治理将其定位为 curated advanced entrypoints。

## Impact

- 对用户：减少“需要理解内部协议才能消费结果”的学习成本；常用路径更短、更稳定。
- 对维护者：内部落盘协议与执行层可迭代，但用户侧 API 可通过 facade 保持稳定；同时需要更严格的 `shortcuts` 边界治理以防 scope creep。
- 对仓库结构：`scalim.shortcuts.resources` 命名会与 repo 目录 `artifacts/` 等概念并存；建议持续在文档中强调：`shortcuts` 是 Python API 命名空间，仓库目录是开发资料/SSOT 存放位置，两者互不绑定。
