## 1. Characterization tests (lock current semantics)

- [ ] 1.1 新增回归测试: `parallel_mode=adaptive` 下 per-task 子 runtime 继承 `key_normalization`,并与 `seq` 命中/诊断语义等价。
- [ ] 1.2 新增回归测试: workflow depends_on 传递可见性在 ctx refs 与 artifacts 可见性校验中一致(覆盖可见/不可见与错误 path)。
- [ ] 1.3 新增回归测试: workflow main_rows wiring 与 typed rows capture/release 行为不回归(仅对被引用 producer 捕获,最后 consumer 结束后释放)。
- [ ] 1.4 新增导入面回归测试: `InMemoryRows` 可从稳定 facade 导入,且 workflow/execution 不再直接 import `sinks._internal.rows`。

## 2. Adaptive runtime config propagation (key_normalization)

- [ ] 2.1 修复: 在 adaptive per-task `ExecutionRuntime` 构造时继承父 runtime 的 `key_normalization`(不依赖默认值)。
- [ ] 2.2 回归: 确保 capture+replay 顺序、错误语义不变(仅修正 key space 语义一致化导致的行为差异)。

## 3. Workflow visibility SSOT (VisibilityIndex)

- [ ] 3.1 新增 `WorkflowVisibilityIndex`(纯数据+纯函数,LBYL 校验;Python 3.6 兼容)并覆盖单测。
- [ ] 3.2 重构 `WorkflowArtifactsDirectory` 复用 VisibilityIndex,移除重复闭包实现。
- [ ] 3.3 重构 `WorkflowCtxStore` 复用 VisibilityIndex,移除重复闭包实现。

## 4. Workflow compile/runtime boundary (no compilation mutation)

- [ ] 4.1 引入显式的 workflow 节点 request overrides 结构,并通过纯函数合成 `ExecutionRequest`(替代对 compilation 的运行期回写)。
- [ ] 4.2 重构 workflow node 执行闭包:运行入口显式传入 `(demand_ir, request)` 或等价结构,避免依赖 compilation 为可 replace 的 dataclass。

## 5. Typed intermediate store stable import path (`InMemoryRows`)

- [ ] 5.1 将 `InMemoryRows`(及其必要配套类型)提升到稳定公开导入路径(优先 `src/scalim/sinks/__init__.py` 的显式 `__all__` 白名单)。
- [ ] 5.2 替换 workflow/execution 对内部实现路径(`sinks._internal.*`)的直接依赖,保持行为等价。
- [ ] 5.3 更新 public API 约定(如入口变化):更新 `docs/doc/getting-started/public-api.md`,并通过 `scripts/check-api-surface-governance.py` + `scripts/check-user-material-import-boundaries.py` + `tests/test_example_public_api_suite.py` 验收。

## 6. Execution contracts split (reduce run_ir hotspot)

- [ ] 6.1 抽离 execution contracts 到独立模块(例如 `execution/contracts.py`),保持 `execution/run_ir.py` 稳定入口与 re-export 兼容。
- [ ] 6.2 确保 contracts 模块无 orchestration 副作用,避免引入可选依赖与层级反转(遵守 `execution-structure`/`module-organization`)。

## 7. OpenSpec sync & verification

- [ ] 7.1 运行 `just openspec-check`(sanitize + `openspec validate --all --strict --no-interactive`)确保工件结构与脱敏可发布。
- [ ] 7.2 实现完成后运行 `openspec sync --change c0-reduce-runtime-entropy` 将本 change 的增量 specs 同步到 `openspec/specs/**/spec.md`(SSOT)。
- [ ] 7.3 运行 `just quick-qa-only-py` 或 `just qa` 做全量回归,确保 lint/typecheck/tests 与 drift gates 全通过。
