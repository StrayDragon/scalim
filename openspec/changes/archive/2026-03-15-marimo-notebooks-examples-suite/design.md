## Context

仓库现状(真值)：

- `notebooks/marimo/` 已存在 Marimo 示例与 headless runner：
  - Marimo UI：`notebooks/marimo/example_public_api/*.py`、`notebooks/marimo/demo_big_data_report/demo_main.py`
  - headless runner：`notebooks/marimo/run_examples.py`（`just examples`/`just qa` 链路）
- 可复用 SSOT 运行逻辑已下沉到 `packages/scalim-misc`：
  - public API 示例：`packages/scalim-misc/src/scalim_misc/examples/public_api/*`
  - demo 主线章节：`packages/scalim-misc/src/scalim_misc/demo_big_data_report/chapters/*`
- canonical YAML SSOT 路径被脚本/测试/spec 依赖（尤其 `agent-skill-export`），必须保持不变：
  - `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`
  - `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report_fragments.yaml`

当前痛点：

- 交互教学层仍偏“单入口汇总”，缺少稳定的逐章学习路径；读者很难从 notebook 直接定位到对应的 SSOT 执行/对拍逻辑与失败定位入口。
- 如果后续不断新增示例/回归点，缺少治理规则会导致：
  - notebook 内复制粘贴共享逻辑（路径解析/展示/对拍摘要），形成第二套真相；
  - examples gate 漂移（示例跑不进 `just examples` 或不可对拍），回归信号丢失；
  - “教学 notebook”与“集成回归用例”混在一起，导致 CI 变慢或 flaky。

约束与治理边界：

- notebook 只做 UI/讲解；可运行/对拍逻辑必须下沉到 `packages/scalim-misc`，且 **不得依赖 marimo**（保证 headless runner/pytest 复用）。
- 不触碰 `src/scalim/**` 运行时语义；不引入新的 runtime 依赖；Python 3.6 运行时边界保持。
- doc governance：notebooks 不属于 docs-site 的受控生成物与 drift gate；如需要导出 notebook 到文档，仅作为可选流程，不能变成强门禁。

## Goals / Non-Goals

**Goals:**

- 建立仓库级“Marimo-first examples/teaching 套件”结构与约定：示例以 notebook 为教学载体，SSOT 用例以 headless runner/pytest 为回归入口。
- 将示例拆成“可学 + 可测”的双层：
  - **可学**：每个示例套件提供 hub/index notebook + 章节 notebooks
  - **可测**：每章对应一个 SSOT `run_*()`/example case，可对拍并纳入 `just examples`
- 固化“共享逻辑下沉”策略：提供少量 notebook-support helpers，避免 notebook 内复制样板。
- 以 `notebooks/marimo/marimo_coverage.gen.md` 作为可检查 SSOT 报告，确保 notebooks/SSOT/gate 的映射可审计且无需手工维护。

**Non-Goals:**

- 不把 Marimo UI 运行纳入 CI gate（CI 只跑 headless runner/pytest）。
- 不迁移/重命名 canonical YAML SSOT，不改变 `agent-skill-export` 的输入来源。
- 不在本变更中改动 YAML DSL/IR/planning/execution 的语义或公开 API。

## Decisions

### Decision 0: notebook 目录按用途前缀组织（demo_/example_/tutor_）

为同时满足“教学阅读体验”与“集成回归稳定性”，约定：

- `demo_*`：端到端主线 demo（覆盖更多组合 cov，必须 deterministic）
- `example_*`：稳定 public surface 的最小可运行示例（小数据、快回归）
- `tutor_*`：长篇教学 notebook（更强调阅读体验；默认不纳入 CI gate，如需纳入必须小数据且 deterministic）

理由：避免把所有内容堆到单一 demo 目录，且为“教学 vs 回归”的取舍提供清晰边界。

### Decision 1: “章节实现 + runner”为单一真相来源（UI 薄封装）

- SSOT 运行逻辑统一放在 `packages/scalim-misc/src/scalim_misc/**`：
  - 返回 `ChapterResult`/`ExampleResult`（包含 `passed/summary/details`）
  - 负责 oracle/fixture 策略与失败摘要
- Marimo notebook 只负责：
  - 解释目标/关键入口
  - 调用 SSOT `run_*()` 并将结果结构化展示
  - 提供“如何在 gate 里跑”的可复制命令/片段

理由：保证 “可学” 与 “可测” 同源，避免 notebook 复制实现导致漂移。

### Decision 2: headless runner 保持为 `notebooks/marimo/run_examples.py`

- `just examples` 继续执行 `notebooks/marimo/run_examples.py`
- runner 只依赖 `scalim-misc`，不依赖 marimo
- 允许扩展 runner 支持：
  - 选择性运行（按 suite/chapter 过滤）
  - 更丰富的失败定位输出（但保持稳定、简洁）

理由：符合现有 `testing-quality` 约定（examples gate），同时允许以用户接口视角扩展回归覆盖。

### Decision 3: notebook-support helpers 下沉且不得依赖 marimo

新增轻量 helper（建议落点）：

- `scalim_misc.notebook_support.pathing`：repo_root 注入、示例资源路径解析
- `scalim_misc.notebook_support.yaml_excerpt`：展示 canonical YAML 局部片段（教学用，不参与执行）
- `scalim_misc.notebook_support.results_view`：把 `details` 结构化为 key/value rows，供 notebook 渲染

理由：减少 notebook 复制粘贴；同时保证 headless runner/pytest 可复用这些 helper（不会引入 marimo 依赖）。

### Decision 4: drift gate 以“存在性 + coverage 报告”为主

- 测试守护：`tests/test_notebook_examples_readme_paths.py` 扩展为 “notebook 套件结构存在性” 护栏（防止悄悄丢失/漂移）。
- 映射守护：`scripts/gen-marimo-coverage.py` 生成 `notebooks/marimo/marimo_coverage.gen.md`；新增/调整示例时必须同步更新并可在 CI 检测 drift。

理由：notebooks 本身不纳入 docs-site drift gate；用轻量结构性检查守护“示例体系不回退”。

### Decision 5: 分阶段交付,先以 `demo_big_data_report` 打样

为降低一次性重排示例体系的风险,采用分阶段推进：

- Phase 0: 固化治理与写作模板,补齐 hub/index 与 coverage 报告生成约定
- Phase 1: 以 `demo_big_data_report` 完整章节化作为样板(每章一本 + hub/index),并将其作为后续套件的参照实现
  - 以 `_X/07-marimo-demo_big_data_report-notebook-reorg.md` 的 **方案 A** 为基准：1:1 对齐 `packages/scalim-misc/.../chapters/*.py` 的 `run_*()` 章节 SSOT
- Phase 2: 将其它示例套件按同一模板补齐/重排(例如 `example_public_api` 的教学一致性与可定位性)
- Phase 3: 扩展 runner/pytest 复用点与 coverage 报告生成,使新增示例天然落入回归入口

## Risks / Trade-offs

- [风险] notebook 数量增多 → 缓解：严格薄封装 + shared helper 下沉 + 固定写作模板
- [风险] examples gate 变慢或 flaky → 缓解：默认只纳入 fast/deterministic 用例；tutor 默认不进 gate；oracle 对拍优先结构化数据而非二进制字节
- [风险] 目录与映射清单长期漂移 → 缓解：存在性测试 + coverage 报告 drift-check

## Migration Plan

Phase 0) 固化目录与约定（新增顶层 hub/index；补齐 coverage 报告生成；统一写作模板）。

Phase 1) 完整章节化 `demo_big_data_report`（每章一本 + hub/index），作为主线样板（按 `_X/07...` 方案 A：与 `scalim-misc` chapters 1:1 对齐）。

Phase 2) 将其它示例套件按同一模板补齐/重排（例如 `example_public_api` 的教学一致性与可定位性）。

Phase 3) 抽取 notebook-support helpers 到 `packages/scalim-misc` 并复用；扩展 headless runner（可选过滤能力）与 pytest 复用点；补齐 coverage 报告生成与 drift gate。

验证：`just examples`、`just qa`、`just openspec-check`。

回滚：

- 若章节化导致 marimo 体验不佳，可先保留 hub 与原入口并逐步迁移；headless runner 与 canonical YAML 不受影响。

## Open Questions

- tutor notebooks 是否需要单独 runner（例如 `just tutor`）以避免与 CI examples 混用？
- 章节 notebook 的最小写作模板是否要用脚本生成（避免人工漂移），还是只在文档中约定？
- headless runner 的过滤参数形式：`--suite`/`--pattern`/`--slow-ok` 等的最小集合是什么？
