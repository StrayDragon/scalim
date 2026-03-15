## Why

当前仓库的示例/教程与集成对拍已经具备“headless runner + SSOT 章节实现”的雏形,但 Marimo notebook 的组织仍偏“单入口 + 章节汇总”,不足以在读者视角形成稳定的逐章教学路径,也难以把更多“用户接口视角”的集成回归纳入同一套可维护的 examples 套件。

需要将 **notebooks 的示例体系全面 Marimo 化并章节化**,同时坚持“notebook 只做教学/展示,可运行与对拍逻辑下沉到 `packages/scalim-misc/`”的治理边界,让示例既可学、又可测: 以 headless 对拍脚本 + pytest 复用点的形式,作为单元测试的补充集成护栏。

## What Changes

- 建立 “Marimo-first 的 examples/teaching 套件” 组织规则(教学层统一为 Marimo):
  - 每个示例套件提供 hub/index notebook + 多个章节 notebook,每章聚焦一个能力点/视角
  - notebook 统一遵循固定写作模板(目标/SSOT/如何跑/结果展示/失败定位),提升教学一致性与可维护性
  - 章节 notebook 鼓励使用 Marimo 的结构化 UI 组件(表格/分页/折叠/告警提示等)提升教学效果,但不引入第二套执行真相
- 扩展并统一 headless 对拍入口(回归层不依赖 Marimo UI):
  - `just examples` 继续通过 headless runner 执行示例/对拍,输出可定位 PASS/FAIL 摘要
  - 每个章节 notebook 对应一个可复用的 SSOT `run_*()` 用例(或 example case),可被 runner/pytest 复用
- 共享逻辑下沉到 `packages/scalim-misc`:
  - notebook-support helpers(路径解析、结果结构化展示、YAML 片段摘录等)集中管理,且 **不得依赖 marimo**
- 分阶段推进(先主线,后铺开):
  - Phase 1: 优先将 `demo_big_data_report` 完整章节化(每章一本),作为教学与回归的主线样板(以 `_X/07-marimo-demo_big_data_report-notebook-reorg.md` 的方案 A 为基准)
  - Phase 2: 将其它示例套件按同一模板补齐/重排(例如 `example_public_api` 的教学一致性与可定位性)
  - Phase 3: 扩展 runner/pytest 复用点与 coverage 报告生成,确保新增示例不会“只写 notebook 不进回归”
- 不改变既有 SSOT 稳定入口(避免破坏引用半径):
  - canonical YAML 示例路径保持不变: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report*`
  - headless runner 继续不依赖 marimo UI,确保 CI 稳定

## Capabilities

### New Capabilities
- `marimo-notebooks-examples-suite`: 定义“示例全部以 Marimo notebook 作为教学载体 + headless runner 作为集成对拍入口 + SSOT 下沉到 scalim-misc”的组织规范与最低要求。

### Modified Capabilities
<!-- none -->

## Impact

- 受影响范围(预期):
  - `notebooks/marimo/**`: 增加/重组示例套件的 hub 与章节 notebooks
  - `packages/scalim-misc/src/scalim_misc/**`: 增加可复用的 examples/chapters 运行入口与 notebook-support helpers
  - `notebooks/marimo/run_examples.py` 与 pytest: 可能扩展用例清单或增加更细粒度的可选运行方式
  - `scripts/gen-marimo-coverage.py` + `notebooks/marimo/marimo_coverage.gen.md`: 自动生成“notebooks → SSOT → gate/pytest”的覆盖报告,替代手工维护
- 不影响:
  - `src/scalim/**` 的运行时语义与 Python 3.6 兼容边界
  - `agent-skill-export` 依赖的 canonical YAML 来源路径
