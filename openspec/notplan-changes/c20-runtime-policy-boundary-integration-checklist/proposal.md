## Why

这次 `compile_workflow_ir._load_demands()` 抢跑 `validate_unique_field_names` 的问题说明我们现有验证体系对“结构编译阶段 vs runtime policy 阶段”的边界覆盖不够完整。现有单元测试能覆盖局部 API，但缺少一组专门面向用户入口的回归规则，去验证 runtime policy 不会在更早的 compile / preload 阶段被提前消费。

## What Changes

- 建立一组面向 runtime policy boundary 的系统化验收清单，覆盖 standalone compile、workflow compile、run_workflow、per-run patch、public API notebook / example gate 等真实入口。
- 为这类检查定义推荐的测试分层：最小单元回归、workflow 集成回归、用户侧 notebook/public API smoke gate。
- 梳理哪些 diagnostics / policy 属于“不得在 compile preload 阶段抢跑”的类别，并把对应测试入口固定到现有测试套件或 `just` 入口中。

## Capabilities

### New Capabilities
- `runtime-policy-boundary-integration-checklist`: 为 runtime policy / compile boundary 建立统一的测试与验收清单，避免类似问题再次漏出。

### Modified Capabilities
- `testing-quality`: 增补“边界错位”类回归的测试分层与 gate 要求。
- `marimo-example-public-api-suite`: 明确 public API notebook suite 可作为 runtime policy boundary 的用户侧 smoke gate。

## Impact

- 受影响范围主要是测试策略、OpenSpec 规范与示例 gate，不直接改变用户 API。
- 预期涉及 `tests/yaml_dsl/`、`tests/public_api/`、`tests/integration/`、`notebooks/marimo/example_public_api_suite/` 等现有验证入口。
- 本 change 当前仅建立 proposal，后续在你复核后再决定是否继续补 design/specs/tasks。
