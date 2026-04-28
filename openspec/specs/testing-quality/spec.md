# testing-quality Specification

## Purpose
定义测试分类、覆盖率门槛与 demo 对拍验证的最低要求,明确默认测试范围与质量门禁,确保持续集成结果稳定可复现.

## Related Concepts
- Pytest 配置 (pyproject.toml)
- Justfile 质量门限 (test/bench/schema-drift-check/lintfix/check-*)
- 脚本扫描器 (check-cast-usage, check-no-cover, check-no-branch, check-core-coverage, check-dynattr)
- YAML schema 生成测试
- YAML parse 回归测试
- Demo 验证
- Bench 套件 (tests/bench/)

## Requirements

### Requirement: 测试分类与默认执行
- 测试套件 MUST 使用 `bench` marker 标识基准用例.
- 默认（本地/轻量）测试入口 MUST 运行所有非 bench 测试,并以快速反馈为优先(不得隐式强制开启 xdist + coverage 门禁).
- 质量门禁（CI/qa）入口 MUST 显式启用重型参数(例如 xdist 并行 + coverage 统计 + coverage gate),并运行所有非 bench 测试.
- 非 bench 测试 MUST 在质量门禁入口中参与覆盖率统计与覆盖率阈值校验.

#### Scenario: 默认执行非 bench 测试
- **WHEN** 使用默认（本地/轻量）测试命令执行 pytest
- **THEN** 运行所有非 bench 测试且不包含 bench

#### Scenario: qa/ci gate runs coverage explicitly
- **WHEN** 使用质量门禁入口(CI/qa)执行测试
- **THEN** 测试 MUST 显式启用 coverage 统计与覆盖率阈值门禁
- **AND** 运行范围 MUST 覆盖所有非 bench 测试

### Requirement: non-bench tests MUST be xdist-parallel-safe
系统 MUST 确保所有非 bench 测试在 `pytest-xdist` 并行执行(例如 `pytest -n auto`)下稳定通过,且不依赖执行顺序或隐式全局状态耦合。

因此,所有非 bench 测试 MUST 满足:
- 在 `pytest -n auto` 下稳定通过(不允许依赖执行顺序)
- 测试不得通过"修改模块全局状态但未隔离/未加锁"的方式制造隐式耦合
- 若确需修改模块全局状态(例如 demo/misc 模块提供的全局配置),测试 MUST 通过集中化的隔离工具实现,并确保在并行执行下不会跨测试污染(必要时通过锁序列化)

#### Scenario: repo QA gate passes under xdist
- **WHEN** 运行 `just qa`
- **THEN** 非 bench 测试 MUST 在 `pytest -n auto` 下稳定通过

#### Scenario: global-state patches are isolated and restored
- **GIVEN** 某测试需要临时修改一个模块全局状态(例如 demo 的全局 config)
- **WHEN** 测试执行并结束
- **THEN** 修改 MUST 被可靠恢复
- **AND** 并行执行的其它测试不得观察到该修改

### Requirement: 覆盖率保持 100%
- 使用覆盖率统计时,核心模块的覆盖率 MUST 保持 100%.
- 核心模块定义为源代码根目录排除 CLI 与 misc 包.
- 覆盖率低于 100% 时 MUST 视为失败(例如通过 `--cov-fail-under=100` 强制).
- Rationale: 将"未覆盖的执行路径"视为质量债务并强制清零；若确有不可覆盖/不可达分支,必须使用 `# pragma: no cover` 并附带 `# pragma: allow-no-cover <reason>` 进行显式治理。
- 该阈值 MUST 与 test-gate 配置中的 `--cov-fail-under` 参数保持一致(SSOT 对齐).

#### Scenario: 覆盖率低于 100% 时失败
- **WHEN** 执行带覆盖率统计的非 bench 测试套件
- **THEN** 若核心模块覆盖率低于 100% 则执行失败

#### Scenario: 边缘模块被覆盖率忽略
- **WHEN** 生成覆盖率报告
- **THEN** CLI 与 misc 包不参与覆盖率统计

### Requirement: runtime-only policy changes MUST define a boundary coverage matrix
当某个能力被定义为 runtime-only policy（尤其是已从 YAML 主线迁出的字段）时,系统的测试与评审材料 MUST 明确定义其边界覆盖矩阵,至少包括以下层次:

- schema / parse 层
- compile / preload 层
- runtime policy merge 层（workflow 入口内形成 per-run effective options 的边界）
- workflow preflight 层（如适用）
- runtime compile 层
- workflow per-run override 层（如适用）
- user-entry smoke 层

#### Scenario: a moved-out YAML field is reviewed for boundary coverage
- **WHEN** 维护者新增或修改某个已迁出 YAML 主线的 runtime-only policy
- **THEN** review 文档 MUST 指出该 policy 在各层的最早生效边界
- **AND** review 文档 MUST 明确哪些层需要测试覆盖

### Requirement: compile/preload layers MUST be reviewed against premature runtime-policy consumption
对于 runtime-only policy,系统 MUST 在设计与测试评审中显式检查 compile / preload 阶段是否可能提前消费该策略.

#### Scenario: review catches compile-phase policy consumption risk
- **WHEN** 某个 runtime-only policy 会影响 demand / workflow 的运行期诊断或行为
- **THEN** review 文档 MUST 说明 compile / preload 阶段是否允许读取该 policy
- **AND** 若不允许,后续测试计划 MUST 包含"compile phase 不抢跑"的覆盖
