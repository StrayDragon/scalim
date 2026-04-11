# testing-quality Specification

**状态: ✅ 已实现**
## Purpose
定义测试分类、覆盖率门槛与 demo 对拍验证的最低要求,明确默认测试范围与质量门禁,确保持续集成结果稳定可复现.
## Related Code (as implemented)
- `pyproject.toml` (`[tool.pytest.ini_options]` addopts/cov gate + `[tool.coverage.run]` omit)
- `justfile` (`test`/`bench`/`schema-drift-check`/`lintfix`/`check-*` quality gates)
- `scripts/check-cast-usage.py` (`cast` 使用扫描器)
- `scripts/check-no-cover.py` (`# pragma: no cover` 使用扫描器)
- `scripts/check-dynattr.py` (`getattr`/`setattr`/`hasattr` 使用扫描器)
- `tests/test_yaml_schema_generation.py` (YAML schema generation drift guard)
- `tests/test_et_yaml_parse_regression.py` (INTEGRATION_APP YAML parse regression; parser-only, no business loaders)
- `notebooks/marimo/demo_big_data_report/_verification.py` (demo verification logic reused by pytest)
- `tests/bench/` (bench-only suite; marker `bench`)

## Implementation Notes (Current Behavior)
- 默认 pytest 配置由 `pyproject.toml` 的 `addopts` 提供(默认排除 bench + 禁用 benchmark 插件),因此直接运行 `pytest`/`just test` 会执行所有非 bench 测试,但不隐式强制启用 xdist + coverage 门禁(优先本地快速反馈).
- 质量门禁入口(`just qa`/CI)通过 `just test-gate` 显式启用 xdist 并行 + coverage 统计 + coverage gate,以保证 CI 结果稳定可复现.
- bench 入口通过 `-o addopts=""` + `--no-cov` 显式关闭默认 addopts(避免覆盖率/xdist 干扰),并启用 pytest-benchmark 的 `--benchmark-only` 工作流.
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

### Requirement: 覆盖率保持 100%
- 使用覆盖率统计时,核心模块的覆盖率 MUST 保持 100%.
- 核心模块定义为 `src/IMPL_ROOT/` 排除 `src/IMPL_ROOT/cli/**` 与 `packages/scalim-misc/**`.
- 覆盖率低于 100% 时 MUST 视为失败(例如通过 `--cov-fail-under=100` 强制).

#### Scenario: 覆盖率低于 100% 时失败
- **WHEN** 执行带覆盖率统计的非 bench 测试套件
- **THEN** 若核心模块覆盖率低于 100% 则执行失败

#### Scenario: 边缘模块被覆盖率忽略
- **WHEN** 生成覆盖率报告
- **THEN** `src/IMPL_ROOT/cli/**` 与 `packages/scalim-misc/**` 不参与覆盖率统计

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
- **AND** 若不允许,后续测试计划 MUST 包含“compile phase 不抢跑”的覆盖

### Requirement: cast usage MUST be inventoryable by an explicit scanner
系统 MUST 提供一个可重复运行的扫描入口,用于清点仓库中 `cast(...)` 的使用位置,并输出可审阅报告.

报告 MUST 至少包含:
- 文件路径
- 行列位置
- `cast` 来源摘要(例如 `typing.cast`、直接导入 `cast` 或别名)
- 当前是否被 allow

#### Scenario: scanner produces a reviewable cast baseline
- **WHEN** 开发者运行 `uv run scripts/check-cast-usage.py --report ...`
- **THEN** 系统 MUST 输出 `cast` 命中清单与汇总统计

### Requirement: no-cover pragmas MUST be explicit and reviewable
系统 MUST 提供一个可重复运行的扫描入口,用于清点 `# pragma: no cover` 的使用位置,并要求这些位置具备显式、局部、可审阅的理由说明.

系统 MUST NOT 允许无理由的 `# pragma: no cover` 作为默认写法长期扩散.

#### Scenario: scanner reports no-cover locations and justification state
- **WHEN** 开发者运行 `uv run scripts/check-no-cover.py --report ...`
- **THEN** 系统 MUST 输出 `# pragma: no cover` 的命中位置
- **AND** 系统 MUST 标记该位置是否具备允许该例外的显式理由

### Requirement: cast and no-cover exceptions MUST use explicit local allow markers
系统 MUST 要求 `cast` 与 `# pragma: no cover` 的例外均通过显式注释声明,不得依赖隐式白名单或 review 口头约定.

系统 SHOULD 支持与 `dynattr` 治理风格一致的局部 allow 机制,优先行级,谨慎使用文件级.

#### Scenario: explicit allow suppresses a justified cast hit
- **WHEN** 某个 `cast(...)` 调用所在行带有 `# pragma: allow-cast <reason>`
- **THEN** 扫描器 MUST 将该命中标记为 allow

#### Scenario: explicit allow marks a justified no-cover hit
- **WHEN** 某个 `# pragma: no cover` 命中携带 `# pragma: allow-no-cover <reason>` 或等价的局部允许标记
- **THEN** 扫描器 MUST 将该命中标记为 allow

### Requirement: guardrail checks MUST be promotable into just qa
系统 MUST 为 `cast` 与 `# pragma: no cover` 检查提供稳定的 `just` 命令入口与非零退出码模式,以便后续接入 `quick-check-only-py` / `just qa`.

#### Scenario: unallowed cast or no-cover usage causes check failure
- **WHEN** 开发者运行相应的 `check` 命令
- **THEN** 若存在未 allow 的 `cast` 或 `# pragma: no cover` 命中,命令 MUST 失败

### Requirement: dynattr usage MUST be inventoryable by an explicit scanner
系统 MUST 提供一个可重复运行的扫描入口,用于清点 `src/IMPL_ROOT/` 中的 `getattr` / `setattr` / `hasattr` 调用,并输出可审阅的报告.

报告 MUST 至少包含:
- 文件路径
- 行列位置
- 调用类型
- 属性表达式摘要
- 当前是否被 allow

#### Scenario: scanner produces a reviewable baseline report
- **WHEN** 开发者运行 `uv run scripts/check-dynattr.py --report ...`
- **THEN** 系统 MUST 输出 `dynattr` 命中清单与汇总统计

### Requirement: dynattr exceptions MUST be explicit and local
系统 MUST 要求所有 `dynattr` 例外均通过显式注释声明,不得依赖隐式白名单或隐藏规则.

系统 MUST 支持以下两类例外:
- 行级 `# pragma: allow-dynattr <prefix>: <detail>`
- 文件级 `# pragma: allow-dynattr-file <prefix>: <detail>`

其中 `prefix` MUST 为一组有限枚举,用于将例外原因聚类并提升可审阅性(例如: `compat` / `dispatch` / `dsl` / `introspection` / `legacy` / `metadata` / `optional-interface` / `plugin` / `third-party`).

文件级例外 SHOULD 仅用于框架型、反射型、整文件动态职责明显的模块;普通业务逻辑 SHOULD 优先使用局部 allow 或重构为静态访问.

#### Scenario: explicit allow suppresses only declared hits
- **WHEN** 某个 `dynattr` 调用所在行带有 `# pragma: allow-dynattr <prefix>: <detail>`
- **THEN** 扫描器 MUST 将该命中标记为 allow

#### Scenario: file-level allow marks the file as allowed
- **WHEN** 文件头注释区包含 `# pragma: allow-dynattr-file <prefix>: <detail>`
- **THEN** 扫描器 MUST 将该文件内命中标记为 allow

### Requirement: dynattr gate MUST be promotable into `just qa`
系统 MUST 提供 `--check` 模式,使 `dynattr` 扫描器可在存在未 allow 命中时返回非零退出码,从而接入 `quick-check-only-py` / `just qa`.

#### Scenario: unallowed dynattr causes non-zero exit
- **WHEN** 开发者运行 `uv run scripts/check-dynattr.py --check`
- **THEN** 若存在未 allow 的 `dynattr` 命中,命令 MUST 失败

### Requirement: 小规模数据与共享夹具
- 非 bench 测试 MUST 使用小规模、可重复的数据集与共享 fixture,避免重复构建高成本模型.
- 大规模数据集 MAY 使用,但必须通过配置显式控制且不作为默认规模.

#### Scenario: 非 bench 测试数据规模可控
- **WHEN** 非 bench 测试需要示例数据集
- **THEN** 使用可配置的小规模数据与共享 fixture

### Requirement: Notebook 对拍验证纳入默认测试
- 对于 `notebooks/marimo/` 下包含 `_verification.py` 的 demo,pytest MUST 至少提供一个非 bench 测试用例复用该对拍验证逻辑(小规模数据).

#### Scenario: demo 对拍验证被 pytest 覆盖
- **WHEN** 运行默认测试命令(非 bench)
- **THEN** 至少执行一个使用 `_verification.py` 的对拍验证用例并通过

### Requirement: `monkeypatch` 使用必须受控且可替换
测试套件 MUST 优先验证可观察行为与稳定契约,并将动态边界集中到显式 seam(overrides/provider/factory)中.
测试套件 MUST 遵循以下约束:

- 测试 MUST 优先通过公开 API、显式注入 seam 来进入边界路径,而不是 patch 生产代码内部实现细节.
- 测试 MUST NOT 通过 patch 私有方法/内部函数(例如 `_foo`)仅为了断言调用次数或缓存命中.
- 测试 MUST NOT patch 全局 import 机制(例如 `builtins.__import__`)来模拟可选依赖缺失;可选依赖缺失 MUST 通过受控 seam 进行模拟.
- 测试 MAY 使用 `monkeypatch` 注入受控边界故障(例如文件 I/O 失败、平台/环境差异、时间相关行为),但 patch MUST 限定在最小作用域并具备明确断言.

上述约束 MUST 由可独立运行的静态门禁守护,并在 `just qa` 的 fail-fast 阶段执行（例如 `uv run scripts/check-monkeypatch-policy.py --check`）。
pytest MAY 仅作为脚本门禁的单元测试载体（例如 `tests/governance/test_check_monkeypatch_policy.py`），但 MUST NOT 把门禁逻辑直接写在 pytest 用例里。

#### Scenario: 边界故障注入不影响实现解耦
- **WHEN** 测试需要覆盖文件写入失败等边界错误路径
- **THEN** 测试仅在该边界点注入失败(例如 patch 写入函数/文件句柄行为)
- **AND** 测试断言面向可观察行为(错误被捕获、日志/返回值符合约定),而不是依赖内部调用细节

#### Scenario: monkeypatch policy gate fails fast with locations
- **WHEN** 开发者运行 monkeypatch policy 的 check 脚本（例如 `uv run scripts/check-monkeypatch-policy.py --check`）
- **THEN** 若存在被禁止的 monkeypatch 模式,命令 MUST 失败并输出违规位置

### Requirement: 禁止以 re-export 稳定性作为测试护栏
当执行层(`execution/executor`/`execution/pipeline`)发生重构或模块拆分时,测试套件 MUST 不以 `__init__.py` re-export、`__all__` 列表或 import path 稳定性作为回归护栏.
测试 MUST 以稳定入口与可观察行为为准(例如 `run_ir` / `ScalesEngine` / 显式 overrides / 输出与事件顺序).

#### Scenario: 移除 re-export 不应导致“导出稳定性测试”失败
- **WHEN** `execution/executor/pipeline` 的 `__init__.py` 移除或调整 re-export
- **THEN** pytest 套件不应因为断言 `__all__` 或包级导入路径稳定性而失败
- **AND** 相关回归 MUST 通过行为断言(输出/事件/guardrails/可观察状态)覆盖

### Requirement: 结构重构必须具备行为等价回归护栏
系统 MUST 为核心可维护性重构提供行为等价回归护栏,至少覆盖:输出结果一致性、事件顺序一致性、错误语义一致性.
这些护栏 MUST 在默认非 bench 测试流程中可执行.

#### Scenario: 结构调整后输出与事件语义不变
- **WHEN** 对核心模块进行职责拆分或内部重组
- **THEN** 对应回归用例 MUST 证明输出结果与事件顺序保持一致
- **AND** 错误类型与关键错误语义 MUST 保持兼容

### Requirement: 可维护性边界必须由自动化测试守护
系统 MUST 提供可独立运行的自动化门禁来守护关键架构边界,至少包括:
- 核心依赖方向约束(如 `planning` 不依赖 `execution`)
- 热点模块体量防膨胀约束(基于明确阈值)
- 稳定入口导入可用性约束

这些门禁 MUST 可接入 `just qa` 的 fail-fast 阶段（pytest 之前）执行（例如以 `scripts/check-*.py --check` 的方式运行）。
pytest MAY 为门禁脚本提供单元测试,但 MUST NOT 把完整门禁逻辑隐藏在 pytest 用例里。

#### Scenario: 边界被破坏时门禁失败并可定位
- **WHEN** 新增变更引入反向依赖或突破热点模块体量阈值且维护者运行对应门禁
- **THEN** 门禁 MUST 失败
- **AND** 失败信息 MUST 指向具体模块路径与违规类型

### Requirement: 若存在 process backend,测试必须反映真实 pickling 约束
若系统支持 `adaptive` 的 `process` backend(跨进程执行),当测试覆盖该路径的调度决策与退化路径时,测试 MUST 以真实 pickling 约束为准:

- 不可 picklable 时,系统 MUST 按 policy 选择 fail-fast 或 fallback-serial 的既定语义.
- 测试 MUST NOT 通过 patch `pickle.dumps` 伪造“可 picklable”来覆盖成功路径.

#### Scenario: 不可 picklable 触发正确退化
- **GIVEN** `adaptive` 的 `process` backend 已启用
- **WHEN** `adaptive` 的 `process` backend 需要处理不可 picklable 的任务负载
- **THEN** 系统按 policy 正确 fail-fast 或 fallback 到 serial 执行
- **AND** 测试通过真实不可 picklable 构造验证该行为(而非 patch `pickle.dumps`)

### Requirement: 缓存/性能类验证以契约或 bench 为基准
测试套件 MUST 将缓存/性能类验证从“实现快照断言”迁移为稳定基准:

- 若验证内容是功能正确性(重复调用不改变结果/不重复产生副作用),测试 MUST 通过输出、事件或可观察状态断言.
- 若验证内容是性能/开销(避免重复昂贵计算),测试 SHOULD 使用 bench 或稳定的度量指标,而不是通过 patch 内部函数统计调用次数.

#### Scenario: 缓存命中不以 call-count 断言
- **WHEN** 测试需要验证某缓存策略不会改变对外结果
- **THEN** 测试断言输出/事件/可观察状态保持一致
- **AND** 测试不依赖 patch 私有函数来统计调用次数

### Requirement: `just` 质量门禁命令使用 `uv run`
项目的质量门禁相关 `just` 任务 MUST 使用 `uv run` 执行 Python 工具链入口(例如 `ruff`、`basedpyright`、`pytest`),以保证依赖来源一致且不依赖激活虚拟环境.

#### Scenario: 未激活 venv 仍可运行 lintfix
- **WHEN** 开发者未激活任何 venv 且已执行 `uv sync --dev`
- **THEN** `just lintfix` MUST 成功运行并通过 `uv run ruff ...` 执行格式化与修复

### Requirement: dev 依赖组去重与重复声明约束
项目的 `pyproject.toml [dependency-groups].dev` MUST 不包含同一包的重复声明(按规范化包名视为同一项),以减少维护噪声并避免约束漂移.
对已在 `[project].dependencies` 中声明的 runtime 依赖,dev 组 SHOULD 不再重复声明;若 dev-only 需要更严格的版本约束,dev 组 MAY 额外声明但 MUST 以注释说明原因.

#### Scenario: dev 依赖来源单一且无重复
- **WHEN** 审阅者检查 `pyproject.toml` 的 dev 依赖组
- **THEN** 不存在重复包声明,且 runtime 依赖不会在 dev 组中无理由重复出现

### Requirement: YAML DSL schema drift 质量门禁
项目 MUST 提供 `just schema-drift-check` 作为质量门禁的一部分,用于检测 YAML DSL JSON Schema 生成物是否与生成器保持一致且为 canonical 文本形式.
该命令 MUST 在 drift 存在时失败并提示开发者提交更新后的 `src/IMPL_ROOT/dsl/yaml_dsl/schema/demand.gen.json`.

#### Scenario: drift 检测失败并给出提示
- **GIVEN** 开发者修改了 `src/IMPL_ROOT/dsl/yaml_dsl/schema_dsl/` 中的 schema 元数据但未提交生成物
- **WHEN** 运行 `just schema-drift-check`
- **THEN** 命令 MUST 失败并提示运行 `just gen-yaml-dsl-schema` 并提交 `demand.gen.json`

### Requirement: INTEGRATION_APP YAML DSL configs must remain parseable

默认(非 bench) pytest 套件 MUST 覆盖仓内 INTEGRATION_APP 集成目录 `INTEGRATION_APP/INTEGRATION_APP/execute_batch_tasks/INTEGRATION_DIR/**` 下的 YAML DSL 配置,以确保其在 PROJECT_NAME 变更后仍可被 YAML DSL 的 parser/validator 成功解析.

该回归验证 MUST 仅做“配置可解析/可校验”检查,不得导入业务 loader 或触发 Django/DB 依赖.

#### Scenario: INTEGRATION_DIR configs stay parseable
- **WHEN** 运行默认(非 bench) pytest 套件
- **THEN** 回归列表中的每个 YAML 配置都能被 `YamlDemandLoader().load(...)` 成功解析
- **AND** 解析过程不会触发任何业务模块导入与执行副作用

### Requirement: planning 测试不得依赖 PlanBuilder 私有实现细节
测试套件 MUST NOT 直接调用 `PlanBuilder._*` 私有方法或断言其内部缓存状态来覆盖分支.
当需要覆盖 planning 的边界逻辑时,测试 MUST 通过以下方式之一完成:

- 通过 `PlanBuilder(...).build(...)` 的可观察输出断言(field_order/operators/stages/metadata/异常等).
- 将边界逻辑提取为纯 helper,并对该 helper 编写单元测试.

#### Scenario: 内部分支覆盖迁移为可观察行为断言
- **WHEN** 原有测试为覆盖边界分支而调用 `PlanBuilder._build_dependency_graph()` / `_extract_dependencies_from_relation()` 等私有方法
- **THEN** 测试 MUST 迁移为对 `build()` 输出或纯 helper 的断言
- **AND** 测试不以缓存命中/私有调用次数作为护栏

### Requirement: executor/planning 测试必须合并重复并保持命名规律
当调整 `src/IMPL_ROOT/execution/executor/**` 与 `src/IMPL_ROOT/planning/**` 的实现或测试时,测试套件 MUST 通过参数化与共用 helper/fixture 减少重复用例数量,并保持测试模块命名可预测:

- executor 相关测试文件前缀 MUST 使用 `test_executor_*.py`.
- planning 相关测试文件前缀 MUST 使用 `test_planning_*.py`.
- 跨 execution 子模块的集成/回归测试文件前缀 MUST 使用 `test_execution_*.py`.
- 新增/迁移测试 MUST 避免创建仅为覆盖率而存在的 `*_coverage.py` 文件;需要的覆盖 MUST 合并到语义更清晰的测试模块中.

#### Scenario: tests 目录不包含 `_coverage.py` 模块
- **WHEN** 维护者审阅 `tests/` 下的测试模块命名
- **THEN** 不应存在以 `_coverage.py` 结尾的测试文件

#### Scenario: 合并覆盖率驱动的重复用例
- **WHEN** 发现同一路径存在多个仅差输入变体/断言形式的重复用例
- **THEN** 测试 MUST 通过参数化合并为更少的测试函数
- **AND** 断言 MUST 聚焦可观察行为(输出/事件/guardrails/可观察状态),避免依赖私有实现细节

### Requirement: executor operators 测试模块按 operator 拆分
测试套件 MUST 将 executor operators 的行为回归测试按 operator 主题拆分为多个测试模块,以降低单文件体积并提高可维护性与可定位性.
拆分后的测试模块命名 MUST 使用 `test_executor_operator_*.py` 前缀(例如 `test_executor_operator_compute.py`).

#### Scenario: operator 测试可定位
- **WHEN** 维护者需要定位 compute operator 的测试覆盖
- **THEN** 应在 `tests/test_executor_operator_compute.py`(或同前缀的模块)中找到主要行为测试

#### Scenario: 避免单文件聚合多 operator
- **WHEN** 新增或迁移 executor operators 的测试用例
- **THEN** 不应将多个不同 operator 的测试持续聚合到同一个大文件中

### Requirement: planning 测试模块命名规律与重复用例合并
测试套件 MUST 将 planning 相关行为回归测试按主题组织为 `tests/test_planning_*.py` 模块,以降低单文件体积并提高可维护性与可定位性.
当用例仅输入变体不同且断言结构一致时,测试套件 MUST 使用 `pytest.mark.parametrize` 合并重复用例,并为 case 提供清晰 `id`.

#### Scenario: PlanBuilder 测试可定位
- **WHEN** 维护者需要定位 `PlanBuilder` 的回归护栏
- **THEN** 应在 `tests/test_planning_builder.py`(或同前缀模块)中找到主要行为测试

#### Scenario: 重复变体通过参数化表达
- **WHEN** 多个测试仅在输入模型/targets/期望字段集合上存在变体差异
- **THEN** 这些变体 MUST 通过参数化收敛到更少的测试函数中
- **AND** 失败输出 SHOULD 可通过 case id 快速定位变体

### Requirement: `just qa` 的 py36 兼容性门禁必须依赖 docker 且不得静默降级
系统 MUST 将 “py36 兼容性” 作为强门禁执行,并确保其语义不依赖当前开发机 Python 解释器的偶然行为.

具体要求:
- 当运行 `just qa`(或其子任务)触发 py36 兼容性检查时,检查 MUST 在 docker 中执行
- 当 docker 不可用时,检查 MUST 失败并给出明确指引(安装/启动 docker),不得静默降级为静态兜底检查并输出 warn 继续通过

#### Scenario: docker 不可用时 fail-fast
- **GIVEN** 开发机未安装或不可用 docker
- **WHEN** 开发者运行 `just qa`(或相关 py36 检查任务)
- **THEN** 命令 MUST 失败并提示需要安装/启动 docker

### Requirement: py36-typingext-check MUST include workflow import smoke test
系统 MUST 在 `py36-typingext-check`（docker 的 Python 3.6 + `typing-extensions==4.1.1` 隔离环境）中执行以下门禁:

- 对 `src/scalim/` 执行 `compileall`
- 对关键入口与 workflow 实现模块执行 import smoke test（至少覆盖 `scalim.dsl.yaml_dsl.workflow_entrypoints`）

该门禁 MUST 能在 “import 时炸（例如注解求值不兼容）” 的场景下 fail-fast。

#### Scenario: import-time annotation incompatibility fails the gate
- **WHEN** 任一关键模块在 Python 3.6 import 阶段因注解求值/语义差异抛错
- **THEN** `py36-typingext-check` MUST 失败

### Requirement: 稳定公开入口模块 `__all__` 必须被 examples gate 100% 覆盖
系统 MUST 将以下稳定公开入口模块的 `__all__` 视为“面向框架用户的公开 API 覆盖清单”，并在 `notebooks/marimo/` 下的 **独立 public API suite** 中提供 deterministic 的最小可运行示例以覆盖其全部导出符号：

- `scalim.dsl.yaml_dsl`
- `scalim.spec.ir`
- `scalim.planning`
- `scalim.execution`
- `scalim.ob`

覆盖要求：

- 每个入口模块 MUST 至少对应一个纳入 `just examples` 的章节 notebook。
- 每个章节 MUST 在执行时对其覆盖清单做断言：当模块 `__all__` 增加新符号而章节未更新时，该章节 MUST fail-fast 并给出可定位 summary（提示缺失符号集合）。
- 系统 MUST 额外提供至少一个章节演示扩展点（例如 hook/observer/events 或 `components` 注入），并将其纳入 `just examples` 的回归范围。

#### Scenario: `__all__` 新增符号但未被章节覆盖时 fail-fast
- **GIVEN** 某稳定入口模块的 `__all__` 增加了新符号
- **WHEN** 开发者运行 `just examples`
- **THEN** 对应公开入口覆盖章节 MUST 失败并报告缺失符号集合

### Requirement: 产物/数据输出示例必须提供 deterministic oracle
当纳入 `just examples` 的某个章节产生数据结果或文件产物时,系统 MUST 提供 deterministic oracle 用于对拍:

- oracle MUST 优先通过运行时计算得到 expected(小数据确定性)
- 当需要固化 expected fixtures 时,必须在章节或测试中明确其来源与更新策略
- 当使用“大但固定”的 expected fixtures 时,fixtures MUST 存放在 `packages/scalim-misc/**/fixtures/` 下(由 runner/测试引用),避免散落在 `tests/fixtures/`

#### Scenario: 产物章节的 oracle 可稳定对拍
- **WHEN** 在 pytest 中运行该章节的回归用例
- **THEN** oracle 对拍 MUST 通过且结果确定(顺序与数值口径稳定)

### Requirement: `demo_big_data_report` 覆盖 workflow YAML 的可运行对拍
系统 MUST 在 `demo_big_data_report` 主线中提供至少一个 deterministic 的 workflow YAML 示例,并将其纳入 `just examples` 的对拍回归范围。

该 workflow 示例 MUST 至少覆盖:
- `scalim.dsl.yaml_dsl.run_workflow(...)` 的运行入口
- 启用 `workflow.options.cache_pool` 的共享 `preload_forever` 行为(需可对拍/可断言)

#### Scenario: workflow 示例在 examples gate 中通过
- **WHEN** 开发者运行 `just examples`
- **THEN** workflow 示例 MUST 被执行
- **AND** 示例 MUST 通过对拍验证并返回稳定 summary(失败时可定位到章节/用例上下文)

### Requirement: `demo_big_data_report` 覆盖派生聚合 set 口径的可对拍边界
系统 MUST 在 `demo_big_data_report` 主线中提供至少一个示例,覆盖派生聚合 set 口径的关键原语与护栏边界,并可在 CI 中稳定回归。

该示例 SHOULD 覆盖(至少其一):
- `dedup_by`
- `two_stage_group_by`
- `count_distinct` 的 `max_distinct` / `distinct_on_overflow`

#### Scenario: 派生聚合示例在 examples gate 中通过
- **WHEN** 开发者运行 `just examples`
- **THEN** 派生聚合示例 MUST 被执行
- **AND** 示例 MUST 通过对拍验证且结果确定(输出顺序/数值口径稳定)

### Requirement: marimo_coverage.gen.toon 作为可检查的 examples coverage 报告
系统 MUST 提供 `notebooks/marimo/marimo_coverage.gen.toon` 作为 SSOT,用于将 `notebooks/marimo/` 下的示例套件回归点映射到:

- Marimo notebooks(教学入口)
- notebooks 侧 SSOT 入口/实现文件（执行真相）
- headless gate(`just examples`)与 pytest 复用点(如存在)
- canonical YAML fixtures 与其 schema 绑定(至少 demand/workflow 两类 schema)

该 coverage 报告 MUST 由脚本 `scripts/gen-marimo-coverage.py` 生成,不得手工维护.

#### Scenario: coverage 报告存在且可再生
- **WHEN** 维护者检查 `notebooks/marimo/` 目录
- **THEN** MUST 存在 `notebooks/marimo/marimo_coverage.gen.toon`
- **AND** 运行 `just gen-marimo-coverage` MUST 能稳定生成相同内容
- **AND** 运行 `just marimo-coverage-drift-check` MUST 在无漂移时返回 0

### Requirement: `just examples` 入口收敛为 `justfile` 内联 headless runner
系统 MUST 将 `just examples` 的执行入口收敛为 `justfile` 内联的 headless runner,并使其覆盖:

- `demo_big_data_report` 的示例/对拍（YAML DSL 主线教程 + IR 回归章节）
- public API suite 的示例/对拍（`__all__` 覆盖断言 + 扩展点演示）

该 runner MUST 自动发现并执行 `notebooks/marimo/` 下的 suites 与章节集合,并输出可定位的 PASS/FAIL 与章节级 summary.

#### Scenario: `just examples` 统一入口覆盖示例套件
- **WHEN** 开发者运行 `just examples`
- **THEN** 系统 MUST 执行 `justfile` 内联的 headless runner
- **AND** 该 runner MUST 覆盖上述示例套件的全部回归点
- **AND** 当存在失败时,进程退出码 MUST 非零

### Requirement: pytest MUST cover the public API catalog via a dedicated public_api suite
系统 MUST 在 pytest 非 bench 套件中提供一个专用的 `public_api` domain suite,用于从用户使用视角覆盖 public API catalog 与核心链路 API 的最小闭环回归.

该 suite MUST 至少覆盖:
- catalog 中模块的稳定导入（import smoke）
- catalog 中模块的 `__all__` 可解析（避免意外导出/导出破坏）
- 最小运行闭环（例如 `compile/run/run_workflow`、`PlanBuilder`、`ScalimEngine`、`Observability`、`events/sinks` 的基本用法）

#### Scenario: public API catalog is covered in pytest non-bench gates
- **WHEN** 开发者运行默认 pytest 非 bench 套件
- **THEN** `public_api` suite MUST 被收集并执行
- **AND** suite MUST 覆盖 public API catalog 的最小闭环并通过

### Requirement: examples gate and pytest public_api suite MUST both cover the public API catalog
系统 MUST 同时通过两条链路覆盖 public API catalog:
- `just examples`（public API suite 的示例/对拍）
- pytest `tests/public_api/`（用户侧最小闭环回归）

两者 MUST 覆盖同一份 public API catalog;若存在缺失/新增导致覆盖集合不一致,系统 MUST fail-fast 并输出差异.

#### Scenario: drift between examples and pytest public_api coverage is rejected
- **GIVEN** public API catalog 发生变化（新增/删除/重命名模块或导出）
- **WHEN** 维护者运行 `just examples` 与默认 pytest 非 bench 套件
- **THEN** 系统 MUST 检测到覆盖集合差异并 fail-fast
- **AND** 错误信息 MUST 指出缺失/新增的模块集合（或导出集合）

### Requirement: 静态治理门禁 MUST 独立于 pytest 执行
仓库 MUST 将“仅依赖文件系统与 AST/文本扫描的静态治理门禁”(例如导入层级/测试结构/monkeypatch 规则等)实现为可复用的 `scripts/check-*.py` 脚本入口.

这些脚本门禁 MUST:
- 支持 `--check` 模式并在发现违规时返回非 0 退出码
- 在 `just qa` 的 fail-fast 阶段（pytest 之前）可被独立执行
- 输出 MUST 包含可定位信息（至少文件路径与行号）

pytest MAY 提供对这些脚本门禁的单元测试（例如 `tests/governance/test_check_*.py`），但 pytest 用例 MUST NOT 直接承载完整门禁逻辑（避免门禁与覆盖率/pytest 执行模型强耦合）。

#### Scenario: scripts/check-* gates run before pytest
- **WHEN** 开发者运行 `just qa` 或直接运行某个 `scripts/check-*.py --check`
- **THEN** 静态门禁 MUST 在不运行 pytest 的情况下完成检查并 fail-fast

### Requirement: YAML DSL LSP MUST have protocol-level contract tests as a refactor baseline

当我们对 YAML DSL 的实现进行大规模重构（例如把 editor semantics 收敛为编译前端 SSOT）时，系统 MUST 通过协议级（JSON-RPC/LSP）contract tests 来验证行为没有无意漂移。

contract tests MUST：

- MUST 启动真实的 `scalim-yaml-dsl-lsp serve`（stdio）作为被测对象，而不是只调用内部函数。
- MUST 覆盖至少以下 endpoint 的关键路径：
  - `textDocument/publishDiagnostics`（didOpen/didChange 触发）
  - `textDocument/definition`
  - `textDocument/hover`
  - `textDocument/completion`
  - `textDocument/codeAction` 与 `workspace/executeCommand`
- MUST 具备跨环境稳定性（见下一个 requirement 的 normalize 要求）。

#### Scenario: run contract tests before and after a refactor

- **GIVEN** 一组固定的 LSP contract fixtures（包含 YAML、imports、以及必要的 Python 模块文件）
- **WHEN** 在 refactor 前后分别运行对应的测试套件
- **THEN** contract tests MUST 在两次运行中都通过
- **AND** 若行为发生变化，必须通过更新 golden/snapshots 或变更说明显式确认

### Requirement: LSP contract tests MUST normalize environment-specific paths and ordering

为了避免因 CI/tmp 目录差异导致的脆弱失败，contract tests MUST 对协议输出做稳定化处理：

- MUST 将 workspace 的绝对路径从 snapshots 中移除（例如用 `<WORKSPACE>` placeholder 表示根路径）。
- MUST 对 diagnostics/completions/locations 做稳定排序（避免由于内部 map/set 顺序变化导致的非行为性漂移）。

#### Scenario: snapshots do not embed tmp absolute paths

- **GIVEN** contract tests 在随机 `tmp_path` 下创建 workspace
- **WHEN** 生成/对拍 snapshots
- **THEN** snapshots MUST NOT 包含 `tmp_path` 的绝对路径字符串
