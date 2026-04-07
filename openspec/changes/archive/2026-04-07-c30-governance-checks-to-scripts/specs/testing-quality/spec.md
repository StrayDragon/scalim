# testing-quality (delta)

## ADDED Requirements

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

## MODIFIED Requirements

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

