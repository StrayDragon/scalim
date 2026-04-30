## 1. Compute fastpath（安全求值）

- [x] 1.1 在 `src/scalim/dsl/yaml_dsl/_internal/config_parsing/security.py` 为 `SecureComputeEngine` 增加一次性构建的 `base_globals`，并重写 `_evaluate`/`_evaluate_positional` 以避免每次求值重建常量/函数表
- [x] 1.2 将 `AuditCallback` 的类型从 `Dict[...]` 放宽到 `Mapping[...]`，并确保 `none/redacted/full` 三种审计模式语义不变（full 仍需解锁环境变量）
- [x] 1.3 引入 positional deps 的只读 locals 视图（例如 `_PositionalLocalsView`）与 per-calculator `dep_index`，避免 `_evaluate_positional` 在审计开启时额外构造 `audit_field_values` dict
- [x] 1.4 为 “字段名遮蔽安全函数名（如 `len`）” 增加回归测试，确保 `eval(..., base_globals, locals)` 的解析优先级与旧行为一致

## 2. call_by fastpath（ctx 按需注入 + 低分配）

- [x] 2.1 增加 `call_by` 是否需要 ctx 的判定（扫描 `CallBySpecIr.args/kwargs` 中是否存在 `kind in {"ctx","ctx_attr"}`），形成可复用 helper（用于 derived call_by 与 default.call_by）
- [x] 2.2 在 `src/scalim/dsl/yaml_dsl/runtime/_internal/conversion_sources.py`：仅当 call_by 需要 ctx 时才设置 `DerivedFieldIr.call_ctx_key=CALL_BY_CTX_KEY`，否则置 `None`（业务零改动，仅减少执行期开销）
- [x] 2.3 在 `src/scalim/dsl/yaml_dsl/runtime/runtime_linking.py`：让 `_build_call_by_calculator()` / `_build_ref_default_call_by_calculator()` 支持 “无需 ctx” 的运行路径（不再强制要求 `ctx=ComputeCallContextIr`）
- [x] 2.4 在 `src/scalim/execution/executor/operators/compute/executor.py`：当 `call_ctx_key is None` 时不构造 ctx；当需要 ctx 时将 `values` 以 `MappingProxyType(dep_payload)` 传入以避免二次 `dict(...)` 拷贝
- [x] 2.5 在 `src/scalim/execution/executor/operators/load_ref/flow.py`：default.call_by 同步按需构造 ctx，并传入只读 `values`
- [x] 2.6 增加回归测试覆盖两类场景：call_by 不引用 `$ctx` 时用户函数无需 `ctx` 相关参数即可运行；引用 `$ctx` 时 `ctx.values` 为只读且包含期望依赖键

## 3. load_ref hotpath（join/写回微优化）

- [x] 3.1 在 `src/scalim/execution/executor/operators/load_ref/**` 的 key 提取、分组与写回路径中引入预绑定 getter/写回计划（局部变量绑定、减少中间对象），并保持事件边界与顺序不变
- [x] 3.2 为 load_ref 关键路径补充语义回归测试（relation miss default、required fields、transform/guardrails 行为），避免在微优化中引入行为漂移

## 4. 性能复现与多 worktree 提示（不提交）

- [x] 4.1 在主仓库工作目录（primary repo root）的 `.tmp/repro/scalim_hotpath_overhead/` 保留合成复现脚本；在其他 worktree 验证时手动复制该目录到对应 worktree 的 `.tmp/`（`.tmp/` 为 untracked dev artifacts，禁止提交）
- [x] 4.2 本地对比优化前后：运行 `.tmp/repro/scalim_hotpath_overhead/repro-execution-hotpath-overhead.py` 的 compute/call_by/load_ref 三个 case，记录 walltime 与 `PerformanceObserver` 分段占比作为人工验收

## 5. 治理与验收

- [x] 5.1 代码修改遵守 Python 3.6 兼容边界（`src/scalim/**`），不引入任何新第三方依赖
- [x] 5.2 若不慎触及生成物/注入区块：以对应 SSOT 修改并运行 `just gen-docs` 重新生成（禁止手改 `*.gen.*` 或 AUTOGEN 区块）
- [x] 5.3 提交前运行 `just qa` 与 `just openspec-check`，确保语义回归与 OpenSpec sanitize/validate 通过
