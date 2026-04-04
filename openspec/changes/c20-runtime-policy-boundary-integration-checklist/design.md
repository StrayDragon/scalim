## Context

这次 `compile_workflow_ir._load_demands()` 抢跑 `validate_unique_field_names`，暴露出当前验证体系的一个结构性缺口：我们已经有“字段从 YAML 主线迁出到 runtime entrypoint”的设计原则，但缺少一套稳定、系统、可复用的验收框架，去保证这些 runtime-only policy 不会在 parse / preload / compile 阶段被提前消费。

现状问题不在于单个测试缺失，而在于缺少统一分层：

- schema / parse 层负责 authoring surface 与迁移提示
- compile / preload 层负责结构分析
- runtime compile 层才负责消费 effective runtime policy
- workflow per-run patch 层负责在具备 run context 时合并 override
- user-entry 层负责验证 notebook / public API 等真实入口没有绕过上述边界

本 change 目标不是立即实现新的测试，而是先把 review 文档和验收口径整理清楚，避免后续补测试时又落回“想到一个补一个”的局部修修补补。

## Goals / Non-Goals

**Goals:**
- 定义 runtime policy boundary 的统一测试分层与责任边界。
- 列出哪些 runtime-only policy 必须进入该验证框架。
- 明确 notebook / public API smoke gate 在这类问题上的职责。
- 输出可 review 的后续任务拆解，供之后逐步实施。

**Non-Goals:**
- 本 change 不直接新增任何测试、gate 或 CI 实现。
- 不在此阶段调整已有 `just qa` 结构或 benchmark 组织方式。
- 不重新设计 YAML 主线 / runtime policy 的语义边界，只做验证体系收敛。

## Decisions

### 1. 用“分层矩阵”而不是零散 case 管理这类问题

后续 review 与实施应以固定矩阵思考，而不是围绕某一个 bug 写单点回归。矩阵建议至少包括：

- **Schema / parse 层**: 迁出的字段仍写在 YAML 时必须 fail-fast，并给 migration guidance。
- **Compile / preload 层**: 只允许消费结构信息，不允许消费 runtime-only policy。
- **Runtime compile 层**: effective global policy 开始生效。
- **Workflow per-run 层**: `run_patches_by_id` 的 override 在具备 run context 后开始生效。
- **User-entry 层**: notebook / public API / integration smoke 证明真实入口没有绕过上述分层。

### 2. 首批纳入 checklist 的对象必须是“已迁出 YAML 主线”的 policy

优先范围建议收敛到已经明确定义为 runtime-only 的能力，包括但不限于：

- `demand_diagnostics`
- `guardrails`
- `loader_retry`
- `batch_size`
- `demand_failure_policy`
- 其它未来被标注为 “moved out of YAML mainline” 的字段

这样可以让 checklist 直接对齐现有 spec，而不是泛化到所有运行参数。

### 3. Notebook / public API gate 作为用户侧 smoke，而不是唯一回归层

真实入口 smoke gate 很重要，但不应承担全部验证责任。正确的职责分工应该是：

- 单元 / internal coverage：打中具体分支与合并逻辑
- workflow/integration：验证 global / per-run / default 行为
- notebook/public API：证明用户侧示例入口没有出现“底层已修，但真实入口仍坏”的问题

### 4. 评审阶段先形成文档，再决定落地位置

这套 checklist 最终可能落到：

- `tests/yaml_dsl/`
- `tests/workflow/`
- `tests/public_api/`
- `tests/integration/`
- PR / OpenSpec review checklist

但本阶段先不锁死具体目录与命令，只把验收要求写清楚，避免过早绑定实现细节。

## Risks / Trade-offs

- [风险] checklist 写得过泛，后续无法落地。 -> 缓解：要求每条规范都映射到明确测试层与至少一个候选入口。
- [风险] notebook gate 变多后运行时间上升。 -> 缓解：文档里明确 smoke gate 必须保持最小 fixture、最小 oracle。
- [风险] 把所有运行参数都塞进同一框架，范围失控。 -> 缓解：首批仅覆盖“已迁出 YAML 主线”的 runtime-only policy。
- [风险] review 只停留在文档，不进入实施。 -> 缓解：`tasks.md` 预先拆出可逐步落地的任务序列。

## Migration Plan

建议后续实施按以下顺序推进：

1. 先 review 并冻结 checklist 文档。
2. 选定首批 policy（建议从 `demand_diagnostics` 开始）做完整矩阵试点。
3. 将 notebook/public API smoke 明确成固定 gate。
4. 再把 checklist 扩展到其它 runtime-only policy。

## Open Questions

- 首批 checklist 的权威承载 spec 是否只挂在 `testing-quality`，还是还需要在具体 capability spec 中逐条挂靠？
- notebook/public API smoke 最终是继续挂在现有 suite 中，还是抽成更明确的 boundary suite？
- 是否需要新增一个 repo-level review checklist 文档，作为 PR 审查模板的一部分？
