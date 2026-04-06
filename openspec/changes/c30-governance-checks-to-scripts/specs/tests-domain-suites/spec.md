# tests-domain-suites (delta)

## MODIFIED Requirements

### Requirement: tests MUST be organized as domain suites
仓库 MUST 将 `tests/` 下的测试用例按领域（domain）组织为显式套件目录,而不是长期依赖“平铺文件 + 文件名前缀”来表达归类.

该结构 MUST 至少包含以下领域目录（名称可固定,内容可随实现重构调整）:
- `tests/public_api/`
- `tests/yaml_dsl/`
- `tests/workflow/`
- `tests/execution/`
- `tests/governance/`
- `tests/integration/`
- `tests/bench/`（基准套件,保持 marker 隔离）

该约束 MUST 由可独立运行的静态门禁守护,并在 `just qa` 的 fail-fast 阶段执行（例如 `uv run scripts/check-tests-domain-suites.py --check`）。

#### Scenario: domain suites exist under tests/
- **WHEN** 维护者运行 tests domain suites 的静态门禁
- **THEN** MUST 能找到上述 domain suites 目录
- **AND** 新增的测试文件 MUST 放入某个 domain suites 目录中

### Requirement: YAML string-reference fixtures MUST live under tests/fixtures/
系统 MUST 将“会被 YAML/Workflow 字符串引用”的测试夹具（例如 `loader:`/`call_by:` 的 `tests.*` 引用）一次性收敛到 `tests/fixtures/` 稳定边界中.

系统 MUST 提供可重复运行的门禁,用于检测 `tests/**` 中所有字符串引用是否落在 `tests/fixtures/` 边界内;一旦发现散点引用,门禁 MUST fail-fast 并给出可定位的命中位置与建议迁移路径.

该门禁 MUST 以可独立运行的脚本形式提供,并在 `just qa` 的 fail-fast 阶段执行（例如 `uv run scripts/check-tests-domain-suites.py --check`）。

#### Scenario: string-reference boundary is enforced by a gate
- **GIVEN** 某个测试 YAML/配置中存在 `loader:`/`call_by:` 的 `tests.<module>:<name>` 字符串引用
- **WHEN** 维护者运行对应门禁（例如 `uv run scripts/check-tests-domain-suites.py --check`）
- **THEN** 若引用目标不在 `tests/fixtures/` 下,门禁 MUST 失败并输出命中位置

### Requirement: tests/support MUST NOT be referenced by YAML strings
系统 MUST 将 `tests/support/` 定义为“仅用于 Python import 的测试内部复用工具”目录;其中的模块 MUST NOT 被 YAML/Workflow 作为字符串引用目标（避免把可移动 helper 变成事实运行期契约）.

该约束 MUST 由与 string-reference boundary 相同的静态门禁守护（例如 `uv run scripts/check-tests-domain-suites.py --check`）。

#### Scenario: support helpers are not promoted into string-reference contracts
- **WHEN** 某个 YAML/Workflow 配置尝试引用 `tests.support.*` 作为 `loader:`/`call_by:` 目标
- **THEN** 对应门禁 MUST 失败并提示将该 callable 移动到 `tests/fixtures/` 再引用

### Requirement: additional test files MUST NOT split the same SSOT topic
系统 MUST 禁止通过 `test_*_additional.py` 的方式为同一主题引入并行套件.
同一能力的测试 SSOT MUST 收敛为单一 domain suites 内的明确入口（可通过参数化覆盖更多场景,但不得以“additional 文件”扩散主题分散）.

该约束 MUST 由可独立运行的静态门禁守护,并在 `just qa` 的 fail-fast 阶段执行（例如 `uv run scripts/check-tests-domain-suites.py --check`）。

#### Scenario: additional pattern is rejected
- **WHEN** 仓库中出现新的 `tests/**/test_*_additional.py`
- **THEN** 对应门禁 MUST 失败并提示将用例合并回主测试文件/套件

## ADDED Requirements

### Requirement: tests/governance MUST focus on contracts and check-script unit tests
`tests/governance/` MUST 聚焦于:
- 运行时契约测试（public entrypoints、optional deps boundary、vendor 兼容层等）
- `scripts/check-*.py` 的单元测试（验证脚本行为、退出码与定位输出）

`tests/governance/` MUST NOT 承载“纯静态扫描类门禁”的完整实现逻辑；该类门禁 MUST 以 `scripts/check-*.py` 的方式存在,并由 `just qa` 在 pytest 之前执行.

#### Scenario: governance gates are reachable without pytest
- **WHEN** 开发者未运行 pytest,仅运行 `just qa` 的 fail-fast 阶段或直接运行 `scripts/check-*.py --check`
- **THEN** 静态治理门禁 MUST 仍可完成检查并 fail-fast

