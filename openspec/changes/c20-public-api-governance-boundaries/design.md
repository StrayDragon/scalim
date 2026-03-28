## Context

Scalim 同时作为“框架 + 库”被使用：用户可以直接 `import scalim.*` 并依赖其稳定性。当前 repo 已具备一些公开面治理基础（例如 marimo public-api suite 对部分 `__all__` 做回归），但仍存在三类长期成本：

1) `_internal` 实现被 re-export 成事实公共 API（重构被外部导入路径锁死）。
2) docs/skills/examples 容易引用内部路径，逐渐形成“教程=契约”的隐性 SSOT。
3) 缺少统一、机器可读的 public surface SSOT，使得“新增导出/移动模块”缺少显式审计点。

参考借鉴（原则层面）：
- Dagster 将内部实现放在显式 internal 命名空间（例如 `dagster._core`），并鼓励用户只使用稳定入口；该模式的关键不在“是否有 internal”，而在“治理能否阻止 internal 变成教程/契约”。

约束：
- 运行时核心代码保持 Python 3.6 兼容（避免引入 3.10+ 语法到 `src/scalim/`）。
- 文档 `.gen.*` 与注入区块严格遵循 doc governance（入口 `just gen-docs`）。

## Goals / Non-Goals

**Goals:**
- 明确“稳定公开入口”清单，并将其变为 **单一事实来源（SSOT）**，可供：测试门禁、示例回归、文档引用复用。
- 默认 public facade 只导出经过编目的符号；内部实现路径与实验性入口不被面向用户材料引用。
- public surface 变更必须显式：修改 manifest + 对应 specs/docs/examples 同步。

**Non-Goals:**
- 不在此变更内一次性完成所有模块的大规模重构拆分（以“先治理边界、再按需迁移”为主）。
- 不在此变更内解决所有安全/并发问题（分别由其它 changes 处理）。

## Decisions

### 1) 引入 public surface manifest 作为机器可读 SSOT

决策：
- 新增一个机器可读 manifest（建议放在 `openspec/` 或 `scripts/` 的 SSOT 目录），内容至少包含：
  - 稳定模块入口列表（module import path）
  - 每个模块允许导出的符号白名单（对应 `__all__`）
  - 允许被 docs/skills/examples 引用的导入路径集合（curated entrypoints）
- 为 manifest 增加三个消费者：
  1) **测试/QA gate**：校验运行时 `__all__` 与 manifest 完全一致（缺失/新增都 fail-fast）。
  2) **示例回归**：marimo public-api suite 的覆盖集合与 manifest 互相校验（避免二者漂移）。
  3) **文档引用**：生成一页“Public API 导入指南”（SSOT=manifest，产物=docs 页面/注入区块）。

理由：
- 把“隐式公共面”变成“显式清单”，是降低长期维护成本的最有效手段。
- 同一份 SSOT 同时驱动测试、示例与文档，减少重复写作与漂移。

备选方案：
- 仅依赖 `__all__` + 手工审阅：拒绝（缺少审计点，变更不可控）。
- 仅依赖 marimo 覆盖集合：拒绝（覆盖集合按章节拆分，不适合作为单点 SSOT；且不表达“允许的导入路径”）。

### 2) 收敛 re-export：public facade 不再穿透 `_internal`

决策：
- 对外稳定入口（例如 `scalim.sinks`、`scalim.events` 等）仅导出经过编目的符号；
- `_internal` 作为实现细节可保留，但：
  - docs/skills/examples 禁止引用；
  - public facade 不再 re-export `_internal.*`（必要时引入 `api.py` 作为稳定 facade，实现可在内部自由移动）。

理由：
- “目录结构自由度”是演进能力的核心；公开面一旦穿透实现细节，后续任何拆分都变成 breaking。

### 3) 增加 docs/skills/examples 的导入治理 gate（窄且确定）

决策：
- 采用简单静态扫描（`rg`）实现 gate：
  - 禁止 `_internal` / `events._*` / `dsl.by_yaml.runtime.*` / `unsafe_entrypoints` 等明确 internal 路径出现在用户材料；
  - 允许列表由 manifest 驱动（“允许什么”优先于“禁止什么”）。

理由：
- 这是最便宜但长期收益很高的治理：阻止 internal 被写进教程。

## Risks / Trade-offs

- [维护成本] manifest 本身需要维护：→ 用 gate 强制同步，并尽量让 manifest 生成/校验工具自动化（降低“手维护多个地方”的风险）。
- [短期 breaking] 收敛 re-export 可能影响依赖 internal 的用户：→ 通过清晰的迁移提示与过渡窗口（必要时提供临时 shim，但优先遵循仓库“直接升级”偏好）。
- [误报] 静态扫描可能误伤：→ 规则保持“窄且确定”，并提供 whitelist/例外机制（仅限内部文档目录）。

## Migration Plan

- 阶段 1：引入 manifest + gate（先把现状固化），并确保 `just qa`/`just examples` 作为回归门槛。
- 阶段 2：逐包收敛 re-export（从最常用入口开始），并同步更新 docs/skills/examples 的导入路径。
- 阶段 3：将 public API 指南页面纳入 docs site（SSOT=manifest；产物=docs 页面）。

## Open Questions

- manifest 的落点：更偏 `openspec/`（治理 SSOT）还是 `scripts/`（工程工具 SSOT）？
- marimo suite 是否应由 manifest 生成覆盖集合（减少手工维护），还是保持“示例先行、manifest 跟随”？

