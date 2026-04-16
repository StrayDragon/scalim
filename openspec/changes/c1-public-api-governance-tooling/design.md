## Context

当前 public surface 的事实 SSOT 是两部分的组合：

- Tier1 curated entrypoints：通过 `src/scalim/**/__init__.py` 中的 `# pragma: scalim-public-api tier1:...` 显式编目稳定入口模块。
- 符号级导出面：通过每个模块的字面量 `__all__` 约束可被 `from <module> import *` 视作稳定契约的符号集合。

我们已经具备 “规则/SSOT”，但缺少低摩擦的工具链让维护者：

- 快速看清当前“官方 re-export 的模块与符号集合”（用于评审、排错、迁移、与门禁对齐）。
- 在 IDE/LSP 中一键跳转到 Tier1 curated exports 的定义位置（用于理解框架结构，而不是运行行为）。

此外，public surface 的治理依赖 doc governance（`.gen.` / injected-block 禁止手改）与 `just qa`/`just openspec-check` 的漂移门禁；因此 design 必须明确：哪些是 SSOT、哪些是生成物、以及对应生成入口。

## Goals / Non-Goals

**Goals:**

- 提供确定性生成物（全部写入 `.tmp/`，不提交）：
  - `.tmp/public_api_jump_imports.py`：用于 IDE/LSP jump-to-definition 的辅助导入文件（基于 Tier1 markers + `__all__`）。
  - `.tmp/public_api_exports_catalog.md`（名称可调整）：用于 review 的 public exports 审计视图（至少覆盖 Tier1 curated entrypoints 的 `__all__` 清单）。
- 统一 `justfile` 入口，减少“记脚本路径”的心智成本：
  - `just gen-public-api-jump-imports`
  - `just gen-public-api-exports-catalog`（待实现）
- 增加一个可 gate 的一致性检查入口（scripts/just 形式均可）：
  - marker 语法合法、无重复 module
  - marker 指向的模块必须存在且必须能解析到字面量 `__all__`
  - 输出按确定性顺序生成（无变更时输出稳定）
- 明确 SSOT 与生成边界，并纳入既有门禁体系（`just qa` / `just openspec-check`）。

**Non-Goals:**

- 不修改任何运行时行为（不改 `src/scalim/**` 的执行逻辑）。
- 不引入“符号级硬 manifest SSOT”（保持 `__all__` 为唯一符号级事实来源）。
- 不在本 change 内强制把 docs 站点生成逻辑重构为新系统（如需改动，作为后续独立 change）。

## Decisions

### Decision 1: 继续以 `# pragma ... tier1` + `__all__` 作为 SSOT（工具链只做投影）

理由：

- 已有 specs（`public-api-manifest` / `public-api-surface-governance`）明确不要求维护符号级硬 manifest。
- `__all__` 可直接与 import-boundary gates、docs 生成、public API suite 形成闭环。

备选方案：
- 引入手工维护的符号 manifest → 维护成本高、且容易制造“为过 gate 写文件”的反模式，拒绝。

### Decision 2: 生成物统一落在 `.tmp/`，并用 `just` 提供统一入口

产物（不提交）：

- `.tmp/public_api_jump_imports.py`
- `.tmp/public_api_exports_catalog.md`

入口：

- `just gen-public-api-jump-imports`：调用 `uv run python scripts/gen-public-api-jump-imports.py`
- `just gen-public-api-exports-catalog`：调用新脚本（待实现）

### Decision 3: 生成器必须 “AST-only、无 import、确定性输出”

实现约束：

- 扫描导出面只解析字面量 `__all__`（tuple/list of string constants）。
- 禁止通过 import 方式收集 exports（避免 side effects、性能、以及可选依赖导致的不稳定）。
- 输出按稳定排序规则生成（order by tier1 marker order，再按 module 名字等）。

选择该约束的原因：

- public surface 治理强调“可审计、可重复”。
- 对动态 `__all__` 的支持会显著放大复杂度与不确定性；此类模块应在治理上被拒绝或在未来单独讨论。

### Decision 4: 增加 check 入口，作为 `just qa` 可接入的 fail-fast gate

建议实现一个独立脚本（例如 `scripts/check-public-api-curated.py`），校验：

- Tier1 markers 的语法与去重
- marker 指向模块存在且 `__all__` 可解析
-（可选）`__all__` 不包含非 dunder 的 `_...` 符号（与现有 spec 对齐）
- internal modules 的 `__all__` 显式为空（与现有 spec 对齐）

输出要求：

- 错误必须包含“文件路径 + 行号（若可得）+ module 名 + 失败原因”，确保可定位可修复。

## Risks / Trade-offs

- [风险] AST-only 会拒绝动态 `__all__` → [缓解] 这是治理目标的一部分：动态 exports 属于不透明 public surface，应在 gate 中 fail-fast 并推动模块整改。
- [风险] 新 gate 增加贡献者负担 → [缓解] 用 `just gen-public-api-*` 提供“一键修复/复现”路径，并保证错误信息可定位。
- [风险] Tier1 entrypoints 扩大后 jump 文件变大 → [缓解] 生成物仅用于编辑器跳转，不参与运行时；且产物在 `.tmp/` 不提交。

## Migration Plan

1. 补齐 `just gen-public-api-exports-catalog` 与对应脚本（产物 `.tmp/public_api_exports_catalog.md`）。
2. 引入 `scripts/check-public-api-curated.py --check`（或等价），并将其接入 `just qa`（或生成物漂移门禁的一部分）。
3. 若 docs public API 页依赖 catalog，按 doc governance 更新 SSOT 并运行 `just gen-docs` 刷新 `.gen.` 生成物。

## Open Questions

- 生成器是否需要支持 tier2/tier3（当前脚本只聚焦 Tier1；若要扩展，需明确用户材料与门禁策略）。
