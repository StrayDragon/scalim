## Why

今天新增的 workflow/runtime 相关变更显著扩展了能力边界,但也暴露出几个会长期拖慢迭代的质量问题：

- 复杂度集中在少数“巨型函数/文件”（例如 workflow 执行编排、workflow config 解析、sheetbook 资源实现）,大量依赖 `# noqa C901/...` 压住复杂度。
- 重复实现与隐式注入降低可读性与并发可预期性：
  - JSON-like 校验逻辑存在重复实现,未来易 drift
  - workflow 入口通过写模块全局变量实现依赖注入,并发/并行测试下存在串扰风险
- 部分并发/诊断类测试依赖真实时间阈值与短 timeout,在慢 CI 下易抖动（flaky）或误报死锁。

需要一个收敛性的 change,把这些问题作为“可测试的质量护栏”固化下来,降低后续改动的回归成本。

## What Changes

- 以“保持语义不变”为前提,将关键模块拆分为更小的阶段化单元,降低单函数圈复杂度与嵌套分支。
- 将 workflow 的执行器依赖注入从“写模块全局变量”改为显式参数/选项传递,避免并发串扰。
- 合并 JSON-like 校验为 SSOT（供 workflow ctx 与缓存签名等路径复用）,减少 drift 风险。
- 稳定化测试：
  - 并发/诊断测试避免依赖亚 0.1s 的真实时间阈值与 `time.sleep`
  - 为 `subprocess.check_output` 等调用增加 timeout,避免卡死
  - 合理提升 join/wait 超时,避免慢 CI 误判死锁

## Capabilities

### New Capabilities

- `workflow-runtime-quality-and-test-stability`: 定义 workflow runtime 的可维护性与测试稳定性护栏（显式依赖注入、SSOT 校验、避免时间抖动）。

### Modified Capabilities

（无）

## Impact

- 受影响实现（预期）：
  - `src/scalim/dsl/by_yaml/runtime/workflow_execute.py`
  - `src/scalim/dsl/by_yaml/workflow_config.py`
  - `src/scalim/dsl/by_yaml/runtime/workflow_resources_sheetbook.py`
  - `src/scalim/dsl/by_yaml/runtime/workflow_entrypoints.py`
  - `src/scalim/execution/workflow_cache_pool.py`
  - 测试：`tests/test_preload_cache.py`、`tests/test_workflow_cache_pool.py`、`tests/test_workflow_resources_coverage.py`、`tests/test_deterministic_ordering.py`
- 该变更以“结构性重构 + 测试稳定性”为主,不期望引入对外行为变化；若出现行为变化,必须在对应 spec 中显式声明并补齐场景。

