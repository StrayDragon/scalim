# language: zh-CN
# capability: testing-quality
# purpose: 定义测试分类、覆盖率门槛与 demo 对拍验证的最低要求,明确默认测试范围与质量门禁,确保持续集成结果稳定可复现. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: testing-quality

  @req:r77 @human
  场景: 测试分类与默认执行
    - 测试套件 MUST 使用 bench marker 标识基准用例。默认测试入口 MUST 运行所有非 bench 测试。质量门禁入口 MUST 显式启用 xdist 并行 + coverage 统计 + coverage gate。

  @req:r321 @human
  场景: non-bench tests MUST be xdist-parallel-safe
    - 系统 MUST 确保所有非 bench 测试在 pytest-xdist 并行执行下稳定通过,且不依赖执行顺序或隐式全局状态耦合。若确需修改模块全局状态,MUST 通过集中化的隔离工具实现。对 tests.fixtures.workflow_loaders 的全局计数与 timing gate,使用该 fixture 的测试模块 MUST 通过 autouse fixture 在每个用例前后重置。

  @req:r444 @human
  场景: 覆盖率保持 100%
    - 使用覆盖率统计时，核心模块的覆盖率 MUST 保持 100%。核心模块定义为源代码根目录排除 CLI 与 misc 包。覆盖率低于 100% 时 MUST 视为失败（例如通过 --cov-fail-under=100 强制）。

  @req:r533 @human
  场景: runtime-only policy changes MUST define a boundary coverage matrix
    - 当某个能力被定义为 runtime-only policy 时，系统的测试与评审材料 MUST 明确定义其边界覆盖矩阵，至少包括 schema/parse 层、compile/preload 层、runtime policy merge 层等。

  @req:r607 @human
  场景: compile/preload layers MUST be reviewed against premature runtime-policy consumption
    - 对于 runtime-only policy，系统 MUST 在设计与测试评审中显式检查 compile/preload 阶段是否可能提前消费该策略。

  @req:r77 @human
  场景: default-non-bench
    - 必须成立：当 使用默认测试命令执行 pytest；那么 运行所有非 bench 测试且不包含 bench
    当 使用默认测试命令执行 pytest
    那么 运行所有非 bench 测试且不包含 bench

  @req:r77 @human
  场景: qa-gate-coverage
    - 必须成立：当 使用质量门禁入口执行测试；那么 MUST 显式启用 coverage 统计与覆盖率阈值门禁
    当 使用质量门禁入口执行测试
    那么 MUST 显式启用 coverage 统计与覆盖率阈值门禁

  @req:r321 @human
  场景: workflow-loader-counters-autouse-reset
    - 必须成立：假如 测试模块引用 tests.fixtures.workflow_loaders；当 任一用例开始执行；那么 autouse fixture MUST 重置 _PRELOAD_CALLS 与 timing gates
    假如 测试模块引用 tests.fixtures.workflow_loaders
    当 任一用例开始执行
    那么 autouse fixture MUST 重置 _PRELOAD_CALLS 与 timing gates

  @req:r444 @human
  场景: coverage-fail
    - 必须成立：当 执行带覆盖率统计的非 bench 测试套件；那么 若核心模块覆盖率低于 100% 则执行失败
    当 执行带覆盖率统计的非 bench 测试套件
    那么 若核心模块覆盖率低于 100% 则执行失败

  @req:r444 @human
  场景: edge-excluded
    - 必须成立：当 生成覆盖率报告；那么 CLI 与 misc 包不参与覆盖率统计
    当 生成覆盖率报告
    那么 CLI 与 misc 包不参与覆盖率统计

  @req:r533 @human
  场景: boundary-review
    - 必须成立：当 维护者新增或修改某个已迁出 YAML 主线的 runtime-only policy；那么 review 文档 MUST 指出该 policy 在各层的最早生效边界
    当 维护者新增或修改某个已迁出 YAML 主线的 runtime-only policy
    那么 review 文档 MUST 指出该 policy 在各层的最早生效边界

  @req:r607 @human
  场景: compile-phase-risk
    - 必须成立：当 某个 runtime-only policy 会影响 demand/workflow 的运行期诊断或行为；那么 review 文档 MUST 说明 compile/preload 阶段是否允许读取该 policy
    当 某个 runtime-only policy 会影响 demand/workflow 的运行期诊断或行为
    那么 review 文档 MUST 说明 compile/preload 阶段是否允许读取该 policy

  @req:r607 @human
  场景: no-compile-premature-test
    - 必须成立：当 runtime-only policy 被禁止在 compile 阶段消费；那么 后续测试计划 MUST 包含 compile phase 不抢跑的覆盖
    当 runtime-only policy 被禁止在 compile 阶段消费
    那么 后续测试计划 MUST 包含 compile phase 不抢跑的覆盖
