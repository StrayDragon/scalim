## Context

Scalim 在“字段数很多、每行逻辑较薄、IO 不重”的报表类场景里，整体耗时往往被执行层的 per-row 固定开销主导：频繁的 Python 调度/封装、字段访问与写回、以及关联(join)阶段的纯 Python 循环与对象分配。此类开销会让 compute / call_by / load_ref 的表现明显落后于等价的手写循环，同时我们又希望保留 Scalim 的低内存优势与可观测性事件流。

约束/前提：

- 运行时必须兼容 Python 3.6（`src/scalim/**`）。
- 用户环境可能严格限制第三方依赖与 vendor 审核：本变更不引入任何新依赖。
- 阶段 1 目标：业务零改动，默认显著更快；内存占用增幅接近 0（不引入与 rows 线性增长的常驻结构）。
- 语义与观测：保持既有语义（值、错误类型/时机、事件顺序/边界）不变。
- 本地合成复现脚本位于 `.tmp/`（不提交），作为稳定热点复现与回归基线。
  - 注意：`.tmp/` 为 untracked dev artifacts；在多 worktree 开发时不会自动出现。若在其他 worktree 实施/验证，请从“主仓库工作目录”的 `.tmp/repro/scalim_hotpath_overhead/` 手动复制到当前 worktree（或重新生成同名脚本），且不要提交到 git。

## Goals / Non-Goals

**Goals:**

- 在不要求业务侧 YAML/代码改动的前提下，显著降低 compute / call_by / load_ref 的 per-row 固定开销（默认启用）。
- 保持低内存：仅引入与“字段数/算子数/批大小”相关的少量常驻缓存；不引入与“总行数”线性增长的额外常驻结构。
- 保持安全约束：compute 仍遵循现有安全校验与审计策略（含 redacted/full 模式），不放宽可用表达式能力边界。
- 保持可观测性：`PerformanceObserver` 与事件/Hook 仍能反映相同的阶段边界与核心事件序列。

**Non-Goals:**

- 不引入新的 DSL 语法/字段定义方式；不改变 IR 语义。
- 不引入并行/多进程执行（并行与 call 次数降低属于后续 `c2`）。
- 不引入依赖重的加速方案（如 pandas/arrow、C 扩展等）。
- 不在本变更中引入面向用户的“性能 profile”配置体系（属于后续 `c1`）。

## Decisions

### 1) 以“算子级 fastpath”重写 hotpath，而不是新增新的执行引擎

**决策：**在 `execution` 层对 compute / call_by / load_ref 各自引入默认启用的 fastpath 实现（对外语义不变），通过“提前绑定 + 减少对象分配 + 减少字典/反射访问”的方式缩短 per-row path。

**原因：**

- 对用户透明（业务零改动），且不引入新依赖。
- 能把优化聚焦在最确定的成本中心（调度/封装），避免大规模架构改动带来的风险。

**备选：**

- 新执行引擎（需重复大量语义/事件实现）→ 风险高、迭代慢。
- 引入第三方加速库/扩展 → 与环境约束冲突。

### 2) compute：复用“已编译表达式 + 预构建 globals”，并避免每次求值重建 `safe_globals`

**决策：**基于现有 `SecureComputeEngine` 的编译缓存，进一步把“常量/安全函数/自定义函数”组成的 globals 预构建为不可变基底，并在 `eval(code, globals, locals)` 中把“字段值”作为 locals 传入，避免每次求值创建/填充新的 `safe_globals` 字典。

**要点：**

- 仍使用现有表达式校验与审计回调；不改变允许的 AST 能力边界。
- 通过 locals 覆盖 globals，保持“字段名可遮蔽内置函数名”的既有解析优先级。
- 在可行处，执行层调用计算器时优先走“positional deps”路径，减少 kwargs dict 组装成本（在审计关闭时避免额外映射构建）。

**审计模式下的字段值视图（展开与推荐方案）：**

背景（当前实现的成本点）：

- `SecureComputeEngine._evaluate()` / `_evaluate_positional()` 每次求值都会构造并填充 `safe_globals`（常量/函数 + 字段值），且在审计开启时还会额外构造一份 `field_values` 映射用于传给审计回调。
- 我们希望把“每次求值都要新建 dict”的成本挪到编译期/引擎初始化期，同时保证审计回调看到的字段值与本次求值一致（同一份视图，不再额外拷贝）。

推荐方案（对外语义不变）：

- 在 `SecureComputeEngine.__init__` 预构建一次 `base_globals`（dict，包含 `__builtins__={}`、`True/False/None`、safe functions、custom functions），并保证后续不再修改它。
- 每次求值使用：`eval(code, base_globals, locals_mapping)`。
  - kwargs 路径：`locals_mapping` 直接使用传入的 `field_values`（通常是短生命周期 dict）。
  - positional deps 路径：使用一个轻量 `Mapping` 视图（例如 `PositionalFieldValuesView(dep_keys, dep_values)`），按需提供 `__getitem__`/`__iter__`/`keys()` 等能力，不再构造 dict。
- 审计回调使用“同一份 locals_mapping”：
  - `audit_mode="none"`：不调用回调，不产生任何额外结构。
  - `audit_mode="redacted"`：回调仅需要字段名列表（当前实现会取 `field_values.keys()`），因此用 `Mapping` 视图即可，无需额外拷贝。
  - `audit_mode="full"`：回调会把字段值原样写日志；推荐仍传入同一份 `Mapping` 视图保证一致性。为保持日志可读性/接近旧行为，`unsafe_audit_callback` 可选择在 full 模式下把 `Mapping` 显式物化为 `dict(...)` 再记录（full 本就是显式调试模式，允许额外开销）。

该方案的关键点是：**求值与审计共享同一个 locals 视图**，从而在开启审计时也避免“再建一份 dict”的固定开销；并且 locals 的解析优先级（字段名遮蔽函数名）与当前行为一致。

**实现草图（Python 3.6 兼容、易读优先）：**

- 目标文件：`src/scalim/dsl/yaml_dsl/_internal/config_parsing/security.py`
- 关键改动点：
  - 把 `AuditCallback` 的类型从 `Dict[str, Any]` 放宽为 `Mapping[str, Any]`（仅提升可表达性；回调内部如需 `dict` 可显式物化）。
  - 在 `SecureComputeEngine.__init__` 构建 `self._base_globals: Dict[str, Any]`（一次性），后续 `_evaluate*` 不再重复拼装常量/函数表。
  - 新增一个“按位置取值”的只读 locals 视图，避免 positional deps 每行构造 `dict`：

    ```python
    # pseudo
    class _PositionalLocalsView(Mapping[str, Any]):
        __slots__ = ("_keys", "_values", "_index")

        def __init__(self, keys: Tuple[str, ...], values: Tuple[Any, ...], index: Dict[str, int]) -> None: ...
        def __getitem__(self, key: str) -> Any: ...  # LBYL: if key not in index -> raise KeyError
        def __iter__(self) -> Iterator[str]: ...
        def __len__(self) -> int: ...
    ```

  - 在 `SecureComputeCalculator`（编译产物）上预先构建 `dep_index: Dict[str, int]`（name → positional index），并在 `evaluate_compiled()` 的 positional 路径中构造 `_PositionalLocalsView(deps, dep_values, dep_index)` 作为 locals 传入 `eval`。
- 约束（最佳实践）：
  - hotpath 里坚持 LBYL：不要用 `try/except KeyError` 做分支；用 `in` / `.get()` 先判断。
  - `__len__` / `__iter__` / `__getitem__` 必须 O(1) 或摊还 O(1)（dep_index 预构建到编译期）。

**备选：**

- AST 解释器替代 `eval` → 实现复杂，且性能未必更优；超出本阶段风险预算。

### 3) call_by：将“参数提取/ctx 构造/args-kwargs 组装”前移为一次性绑定，行内只做最少动作

**决策：**在 runtime linking 阶段为每个 `call_by` 字段构建一次性的“调用 runner”（包含：已解析的目标函数、参数提取器、必要的上下文视图/常量参数），执行阶段每行只做：

1) 通过预绑定的 `itemgetter`/轻量 getter 获取输入值；2) 以最小的封装调用目标函数；3) 直接写回目标字段。

**要点：**

- ctx 构造保持简单：阶段 1 以“避免无谓构造 + 减少 values 拷贝”为主（仅当 spec 引用 `$ctx` 时才构造 ctx；并尽量直接传入 `MappingProxyType(dep_payload)` 以避免二次 `dict(...)` 拷贝）。如仍需进一步压缩对象体积，再评估 `__slots__` 方案（但需保证对外属性与 pickling 语义不变）。
- args/kwargs：优先走 tuple args（当 DSL 映射允许且签名满足时），否则保持现状但减少中间对象。
- 保持异常语义（异常类型、堆栈、字段定位）不变：仅更换组装方式，不吞错/不重包装。

**ctx 合同（深入代码现状 + 推荐收敛）：**

当前 ctx 的允许属性集合是一个“语法级白名单”，由 call_by 解析器强约束（`src/scalim/dsl/yaml_dsl/_internal/config_parsing/call_by.py` 中 `ALLOWED_CTX_ATTRS`）：

- `row_id` / `batch_num` / `field_id` / `deps` / `values`

各字段语义（阶段 1 保持不变）：

- `row_id`: 当前行在执行引擎中的行标识（`BatchContext` 使用的 key）。
- `batch_num`: 当前批次编号（与 instrumentation/guardrails 事件中的 `batch_num` 对齐）。
- `field_id`: 当前正在计算/回填的字段标识（派生字段或 default.case 所在字段）。
- `deps`: 当前调用的依赖字段列表（tuple）。
- `values`: 只读映射（snapshot），内容为 `dep_key -> dep_value`（仅包含本次调用相关的依赖值，不是整行 row）。

运行时传入的 ctx 对象类型为 `ComputeCallContextIr`（`src/scalim/spec/ir/_fields.py`），并在以下位置构造：

- 派生字段 call_by：`src/scalim/execution/executor/operators/compute/executor.py` 在执行每行时创建 `ComputeCallContextIr(row_id, batch_num, field_id, deps, values)` 并以 `ctx=...` 传入派生 calculator。
- ref 字段 default.call_by：`src/scalim/execution/executor/operators/load_ref/flow.py::_eval_ref_default_call_by` 同样构造并传入。
- 运行时链接的 call_by calculator 会检查 `ctx` 类型（`src/scalim/dsl/yaml_dsl/runtime/runtime_linking.py::_build_call_by_calculator`）。

因此，“ctx 的最小集合”在阶段 1 的推荐答案是：**保持与语法白名单一致的 5 个属性，不新增 demand/runtime 等重对象引用**。

理由：

- 这是 DSL 已承诺的稳定接口（schema 文档也公开了可用属性）；阶段 1 以性能重写为主，避免引入新的 DSL/Schema 变更面。
- demand 元信息/运行时对象往往体量更大、容易导致无意的长生命周期引用，违背“几乎无内存损耗”的目标，也容易把内部结构暴露给用户（治理成本高）。
- 行索引（row nth）若确有诉求，更适合后续以“显式新增 ctx_attr + specs 更新”的方式推进，而不是在 c0 的纯性能改写中隐式塞入。

与性能相关的建议（不改变对外接口）：

- **避免无谓 ctx 构造：**如果 call_by 参数中完全没有 `$ctx` / `$ctx.<attr>`，则没有必要在执行层为每行创建 ctx；推荐在编译/转换阶段识别是否出现 ctx 引用，并仅在需要时设置 `DerivedFieldIr.call_ctx_key`（并同步让 runtime linking 的 calculator 在“无需 ctx”时不强制要求 `ctx`）。
- **避免 values 双重拷贝：**当前执行层会先构造 `dep_payload` dict，再由 `ComputeCallContextIr.__post_init__` 再拷贝一次以生成 `MappingProxyType`。推荐让执行层直接传入 `MappingProxyType(dep_payload)`（或引入专用 builder）以把“1 次 dict + 1 次只读包装”固定下来。

**实现草图（Python 3.6 兼容、低分配）：**

- ctx 需求判定（LBYL、无反射）：
  - 当 `CallBySpecIr.args/kwargs` 中不存在 `kind in {"ctx", "ctx_attr"}` 时，视为“不需要 ctx”。
- 绑定期（转换/链接阶段）：
  - `src/scalim/dsl/yaml_dsl/runtime/_internal/conversion_sources.py`：在生成 `DerivedFieldIr` 时，仅当“需要 ctx”才设置 `call_ctx_key=CALL_BY_CTX_KEY`，否则置 `None`（保持 DSL 不变，仅减少执行期开销）。
  - `src/scalim/dsl/yaml_dsl/runtime/runtime_linking.py`：
    - `_build_call_by_calculator()` / `_build_ref_default_call_by_calculator()` 仅在“需要 ctx”时校验 `ctx` 类型；否则允许不传 `ctx`，并完全跳过 ctx 分支。
    - 可选优化：把每个参数的求值逻辑预编译成结构化步骤（literal/field/ctx/ctx_attr），执行期避免创建多层中间对象。
- 执行期：
  - `src/scalim/execution/executor/operators/compute/executor.py`：当 `call_ctx_key is None` 时，直接调用 `calculator(*dep_args)`；否则才构造 ctx 并 `calculator(*dep_args, ctx=ctx)`。
  - `src/scalim/execution/executor/operators/load_ref/flow.py`：default.call_by 同理；构造 ctx 时传入 `MappingProxyType(dep_payload)` 以避免 `ComputeCallContextIr` 内二次复制。

**备选：**

- 约束用户函数签名（要求 batch / vectorized）→ 破坏“业务零改动”，留给 `c2`。

### 4) load_ref/join 写回：保持算法不变，优化循环与临时对象，减少纯 Python 开销

**决策：**在不改变 join 语义/事件的前提下，对 key 提取、分组、写回路径做“局部结构化”：

- join key 提取：预绑定 key getter（减少多次映射查找）。
- 分组：用 `dict.setdefault`/本地变量绑定减少热点属性查找；避免创建多层小对象（如频繁包装 row/field）。
- 写回：预计算写回计划（目标字段列表/写回函数），按列写回优先减少重复查找。

**备选：**

- 引入更复杂的 join 索引结构（如多级索引/排序 join）→ 可能增加内存常驻与实现复杂度，不符合阶段 1 目标。

### 5) Drift gates：以合成复现脚本作为性能回归入口；CI 仍以语义测试为主

**决策：**

- 性能回归入口：`.tmp/repro/scalim_hotpath_overhead/repro-execution-hotpath-overhead.py`（不提交、不在 CI 执行），用于本地对比优化前后 walltime/阶段占比。
- 语义回归：保持/补充现有单测覆盖（不依赖性能数值断言），确保 fastpath 与原语义一致。
- OpenSpec：变更共享前运行 `just openspec-check`，确保工件不包含业务数据与不该暴露的路径。

## Risks / Trade-offs

- **[风险] locals 传入字段值改变了 `eval` 的解析细节** → **缓解**：显式验证“字段遮蔽函数名”的语义一致；覆盖边界案例（同名字段、审计开关、异常路径）。
- **[风险] call_by runner 绑定不当导致 ctx/参数可见性变化** → **缓解**：runner 只做提取与传递，不改参数内容；对典型签名组合加单测。
- **[风险] load_ref 优化影响事件顺序或写回时机** → **缓解**：严格保持事件发射点不变；先做“等价重构”，再做微优化；用 `PerformanceObserver` 对齐阶段边界。
- **[权衡] 保持低内存会限制某些更激进的缓存/向量化** → **缓解**：将“用更多内存换时间”的方案集中到后续 `c1`（profile 可选）与 `c2`（批处理/并行）中讨论。

## Migration Plan

- 无 DSL/IR 迁移：升级框架版本即可获得默认加速。
- 回滚策略：如发现边界语义问题，可通过版本回退快速止血（后续如引入 profile/开关，则可提供更细粒度的运行时降级）。
