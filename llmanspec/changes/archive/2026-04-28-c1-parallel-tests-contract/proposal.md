## Why

仓库的质量门禁(`just qa`)已经以 `pytest -n auto` 作为默认路径,但当前测试套件仍存在“通过修改模块全局状态来驱动测试”的模式(例如 `tests/conftest.py` 中对 `scalim_misc` 的全局 loader/config 的 patch)。

这类写法在单进程串行执行时通常可工作,但当我们**承诺支持并行测试**(xdist 或未来可能的线程并行执行器)时,它会带来:
- 难以推断的跨测试污染风险
- flaky 的潜在来源(尤其当后续引入更激进的并行策略/插件)
- 降低测试可读性与可维护性(测试依赖隐藏的全局副作用)

因此需要把“并行测试契约”写进规范,并把现存的全局状态 fixture 改造成并行友好的隔离/注入模式。

## What Changes

- 更新测试规范: 明确非 bench 测试 MUST 在 `pytest-xdist` (`-n auto`) 下稳定通过,并给出对全局状态/fixture 的约束。
- 修复现存不安全的全局状态 fixture:
  - `scalim_misc.example_report_ir.data_loader.random_delay` 的全局修改
  - `scalim_misc.demo_big_data_report.loaders.set_config/get_config` 的全局配置修改
- 引入测试侧的“显式隔离工具”(fixture/上下文管理器),使 patch/恢复变为可审计、可复用,并在需要时用锁序列化全局修改(保证线程并行下也安全)。

## Capabilities

### New Capabilities

- （无）

### Modified Capabilities

- `testing-quality`: 增量补齐“并行测试必须稳定”的要求,并对全局状态 fixture 给出约束与可验证场景。

## Impact

- 受影响代码:
  - `tests/conftest.py`
  - `tests/integration/test_demo_big_data_report_workflow_demo.py`
  - `tests/cases/notebook_ecommerce.py`
  - 可能需要对 `packages/scalim-misc` 增加更适合测试注入的辅助 API(若我们选择用注入替代 patch)
- 验证方式:
  - `just qa` (本身包含 `pytest -n auto`)
  - 可额外加入一个更“侵略”的并行 smoke(例如显式运行两次 / 更换 xdist 分发策略)来防回归
