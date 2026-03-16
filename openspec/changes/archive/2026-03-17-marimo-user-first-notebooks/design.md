## Context

本变更目标是重写 `notebooks/marimo/` 的示例/教学代码，使其从“薄封装 + 隐藏在 `scalim-misc` 的 SSOT 逻辑”转向“notebook 即用户代码/即教学 SSOT”，并仍然满足 deterministic 对拍回归（`just examples`/pytest）与可定位失败输出。

仓库现状（真值）：

- examples gate：`just examples` → `notebooks/marimo/run_examples.py`（CI/本地均使用）
- canonical YAML SSOT（必须复用、路径不变）：`notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml` 等
- 当前治理（由 specs 定义）：notebook 只负责 UI，执行/对拍逻辑下沉到 `packages/scalim-misc`，runner 不依赖 marimo UI

本变更的前置约束（来自用户决策）：

- runner/pytest 允许直接 import marimo/notebooks 代码（不要求完全隔离 marimo 依赖）
- `example_public_api` 套件并入主线章节后删除
- 公开入口覆盖范围以 `__all__` 为清单：`scalim.dsl.by_yaml` / `scalim.spec.ir` / `scalim.planning` / `scalim.execution` / `scalim.ob`，目标 100% 覆盖，并补充 hooks/observer 等扩展点演示

文档/生成治理边界（实现前必须收敛）：

- notebooks 不属于 docs-site 受控生成物与 drift gate（可在站内引用路径，但不生成/注入 notebook 内容）
- `.gen.*` 与 `BEGIN/END AUTOGEN:*` 的规则不变；本变更如需更新 docs，只改 SSOT 并走 `just gen-docs`
- examples coverage 报告仍以 `scripts/gen-marimo-coverage.py` 生成的 `notebooks/marimo/marimo_coverage.gen.md` 为 SSOT；其规则需随新结构同步更新并纳入 drift-check

## Goals / Non-Goals

**Goals:**

- 将 `notebooks/marimo/` 重塑为“用户第一”的交互教学与回归入口：用户从 notebook 直接看到框架调用过程、关键对象与常用写法提示。
- 公开入口模块 `__all__` 覆盖：以主线章节形式覆盖 5 个稳定入口模块的全部导出符号，并提供 hooks/observer 等扩展点的最小可运行演示。
- 保持 deterministic 对拍：复用既有 fixture 与 YAML 配置，继续通过 `just examples`/pytest 提供可定位 PASS/FAIL 与 summary。
- 收敛 `scalim-misc`：仅保留 fixture/loader（含 YAML allowlist 引用）、oracle/verification、以及跨 notebook 复用的工具函数；避免将“教学主流程”继续沉到 `scalim-misc`。

**Non-Goals:**

- 不改变 `src/scalim/**` 的运行时语义与 Python 3.6 兼容边界。
- 不把 marimo UI server 的启动/导出纳入 CI gate（CI 只跑 headless runner/pytest 的 deterministic 对拍路径）。
- 不迁移或重命名 canonical YAML SSOT 路径（避免破坏引用半径与用户熟悉入口）。

## Decisions

### Decision 1: 将 notebooks 设为 examples SSOT（runner/pytest 复用同一份 notebook 代码）

约定：每个纳入 gate 的章节 notebook 提供一个可被导入调用的 `run_*()`（或 `run()`）入口，返回统一结果结构（`ExampleResult`/`ChapterResult` 或同等字段：`passed/summary/details`）。

- Marimo cells 负责 UI 组织（tabs/table/callout/form 等），但核心执行路径直接调用同文件/同目录下的 `run_*()`（保证“所见即所得”）。
- `notebooks/marimo/run_examples.py` 与 pytest 复用这些 `run_*()`，保证 headless 与交互同源。

备选方案（不选）：

- 继续将 SSOT 下沉到 `scalim-misc`，notebook 薄封装：与用户目标冲突（过程不可见、学习割裂）。

### Decision 2: 复用现有 fixtures/oracle，并将其收敛在 `scalim-misc`

保持两类真相来源分层：

- **确定性真值/对照组（oracle）**：保留在 `packages/scalim-misc`（可在无 marimo UI 环境复用，且便于多 notebook 共用）。
- **用户教学主流程**：迁回 notebooks（展示如何构建 IR/Plan/Engine、如何配置 observability/guardrails/loader_retry、如何组织输出与调试）。

这样可避免 notebooks 内复制大段对照组逻辑，同时满足“notebook 里能看到真实调用过程”的目标。

### Decision 3: `example_public_api` 并入主线章节，并以 `__all__` 驱动覆盖清单

- 删除 `notebooks/marimo/example_public_api/` 目录。
- 将公开入口覆盖拆成若干主线章节（可按“入口模块维度”分章，或按“用户任务流”分章，但必须能证明 `__all__` 100% 覆盖）。
- hooks/observer 等扩展点演示作为主线章节的一部分（可与 `components`/events 相关章节合并）。

### Decision 4: 结构性 drift gate 继续存在，但映射口径更新为“notebook 即 SSOT”

- `scripts/gen-marimo-coverage.py` 更新为映射 notebooks → (notebook-SSOT) → gate/pytest，并保留 canonical YAML/schema 绑定校验。
- `tests/test_notebook_examples_readme_paths.py` 更新为守护新的目录结构与章节集合（防止回退/丢失）。

### Decision 5: 文档治理保持不变（不生成 notebooks，不在 docs-site 注入 notebook 内容）

- docs-site 只更新“入口路径/运行方式/回归入口”文字与链接，不把 notebook 代码内容复制到 docs（避免二次真相）。
- 如需在 docs 展示片段，优先使用现有 SSOT（例如 YAML 片段 SSOT/注入机制），不引入新的 notebook 导出生成物门禁。

## Risks / Trade-offs

- [风险] gate/pytest 依赖 marimo 导入成本上升 → 缓解：runner 不启动 UI server；仅导入 notebook 模块并调用纯函数入口；避免在 import-time 执行重逻辑。
- [风险] notebooks 变大导致难维护 → 缓解：强制“每章一个明确入口 + 结果结构化 + UI 模板一致”；共享模板提取到工具模块（但不回流到 `scalim-misc` 的教学逻辑层）。
- [风险] 删除 `example_public_api` 影响既有引用 → 缓解：更新 docs/spec/tests/coverage 报告与 runner 的映射，提供清晰迁移路径与替代入口。
- [风险] `__all__` 覆盖随版本演进 drift → 缓解：coverage 报告生成器以 `__all__` 作为清单来源，自动检测缺口并在 `just qa` 中 fail-fast。

## Migration Plan

1) 更新 specs（本 change）：明确新治理边界、主线章节集合与 gate/coverage 报告映射口径。
2) 重写 notebooks：
   - 在主线章节中补齐公开入口模块 `__all__` 覆盖与扩展点演示。
   - 将现有 `scalim-misc` 中的“教学主流程”迁回 notebooks（保留 fixtures/oracle 在 `scalim-misc`）。
3) 更新 `notebooks/marimo/run_examples.py` 与 pytest：改为导入 notebooks 侧 `run_*()` 并保持 PASS/FAIL 输出与退出码语义。
4) 更新 drift gate：`scripts/gen-marimo-coverage.py`、`notebooks/marimo/marimo_coverage.gen.md`、与结构性测试。
5) 验证：`just examples`、`just qa`、`just openspec-check`。

回滚策略：

- 若 notebooks 侧 SSOT 导入导致 gate 不稳定，可临时保留旧 runner 路径与 `scalim-misc` 旧入口（双写），待稳定后再删除旧路径（以 tasks 中的阶段性拆解保证可回退）。

## Open Questions

- 主线章节的组织方式：按“稳定入口模块维度”分章还是按“用户任务流”分章？（两者都可满足 `__all__` 覆盖，但对学习曲线不同。）
- notebooks 侧共享模板的最佳落点：`notebooks/marimo/_support`（纯 Python 模块）还是继续使用 `scalim_misc.notebook_support`（需避免扩张为教学逻辑层）？
- `__all__` 覆盖的验证机制：由 `scripts/gen-marimo-coverage.py` 直接检查缺口，还是额外增加 pytest 检查（两者可以叠加，但要避免重复/增加门禁时间）。

