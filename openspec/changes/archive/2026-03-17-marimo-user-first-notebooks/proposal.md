## Why

当前 `notebooks/marimo/` 的示例体系以“薄封装调用 `scalim-misc` SSOT”为核心治理边界，这保证了可回归，但也让用户在 notebook 里看不到“从导入到执行”的真实调用过程与可复用写法；大量适合用 Marimo 交互展示（过程可视化、UI 组件、排障面板、参数实验）的代码被搬运到了 `packages/scalim-misc/`，导致教学体验割裂、用户难以直接照抄改写成自己的代码。

我们需要把 notebooks 重新定义为“用户第一”的交互教学与集成对拍载体：让 notebook 自身就是用户会写的代码，同时仍能用绝对正确的 fixture/oracle 做 deterministic 对拍回归。

## What Changes

- 将 `notebooks/marimo/` 重写为用户视角的教学主入口：以 Marimo 交互 UI 组织“过程 + 结果 + 失败定位”，并补齐常用写法提示（以稳定公开入口模块的 `__all__` 为覆盖清单来源，目标 100% 覆盖）。
- **BREAKING** 删除 `notebooks/marimo/example_public_api/` 套件：其内容并入主线章节（以主线章节形式覆盖 `scalim.dsl.by_yaml` / `scalim.spec.ir` / `scalim.planning` / `scalim.execution` / `scalim.ob` 的 `__all__`，并额外提供 hooks/observer 等扩展点的演示）。
- 将“应被教学展示的主流程代码”从 `packages/scalim-misc/` 迁回 notebooks（允许 headless gate/pytest 直接 import marimo/notebooks 代码；runner 不启动 marimo UI server，仅复用 notebook 代码路径执行对拍）。
- 保持用户熟悉的对拍入口与 YAML SSOT：复用既有对拍脚本与 canonical YAML 配置（路径不变、语义不变），并继续提供可定位的 PASS/FAIL 与章节级 summary。
- 收敛 `scalim-misc` 职责边界：仅保留 fixture 数据/loader、oracle/verification、与少量跨 notebook 复用的工具函数（且避免把教学主逻辑继续下沉到 `scalim-misc`）。

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `marimo-notebooks-examples-suite`: 调整治理边界为“notebooks 作为用户第一的 SSOT 教学/执行代码来源；`scalim-misc` 仅保留 fixture/oracle/工具函数；runner/pytest 允许直接 import notebook 代码执行 deterministic 对拍”。
- `marimo-demo-big-data-report-chapters`: 主线章节组织与最小章节集合扩展为同时覆盖 demo 主线 + public surface（`__all__` 100% 覆盖）+ 扩展点（hook/observer 等）演示，并更新“章节 SSOT 归属”与“回归入口复用”约束。
- `testing-quality`: 移除/替换对 `example_public_api` 套件目录的强约束；将公开入口模块 `__all__` 覆盖要求迁移到主线章节；更新 examples gate/coverage 报告的映射口径以反映新的 SSOT 归属。

## Impact

- 受影响范围（预期）：
  - `notebooks/marimo/**`：目录结构重排、主线章节扩展、删除 `example_public_api/`，并引入更丰富的 Marimo UI 组织方式（tabs/table/callout/form 等）。
  - `notebooks/marimo/run_examples.py` + pytest：runner/测试将改为复用 notebooks 侧 SSOT（允许 import marimo），但仍保持 deterministic 对拍语义与可定位输出。
  - `packages/scalim-misc/src/scalim_misc/**`：删除/迁移教学主逻辑，仅保留 fixture/oracle/工具与少量共享模板代码（不得依赖 marimo）。
  - `scripts/gen-marimo-coverage.py` + `notebooks/marimo/marimo_coverage.gen.md`：映射规则需更新以反映“notebook 即 SSOT”的新结构。
- 不影响：
  - `src/scalim/**` 的运行时语义与 Python 3.6 兼容边界（本变更只调整示例/教学与回归组织方式）。

