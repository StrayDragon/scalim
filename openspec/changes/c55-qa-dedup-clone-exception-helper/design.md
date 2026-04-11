## Context

在跨线程等待/聚合的并发场景中（例如 preload cache inflight、workflow shared resources join/wait），owner 线程捕获异常后常需要把异常以“可跨线程传播”的形式存入状态，再由 waiter 线程重新抛出。

直接跨线程复用同一个异常对象会带来两个常见问题：

- traceback/上下文被多次 re-raise 污染，诊断信息混乱；
- 异常对象可能携带大量 traceback 引用，造成不必要的内存占用与生命周期延长。

因此仓库实现了 `_clone_exception_for_reraise(exc)` 的 best-effort 克隆逻辑（`copy.copy` → `exc.__class__(*exc.args)` → fallback 原对象，并尽量 `with_traceback(None)` 清理 traceback）。

当前至少有两份几乎等价的实现分别存在于：

- `src/scalim/workflow/resources_base.py`
- `src/scalim/execution/preload_cache.py`

重复实现会带来漂移风险（某处修 bug 另一处未同步）、测试口径不一致（只测了一处）、以及维护者认知负担（不知道哪个才是权威）。

## Goals / Non-Goals

**Goals:**

- 将异常 clone 语义收敛为全仓唯一 SSOT 实现，避免未来漂移
- 让测试口径覆盖“唯一实现”，并保持 workflow/preload 两条路径都被间接覆盖
- 迁移成本低，且不引入导入环/层级反转
- 保持 Python 3.6 兼容

**Non-Goals:**

- 不改变对外异常类型/消息语义（仅治理跨线程传播时的 clone 行为）
- 不追求强制所有异常都可 clone（best-effort，失败则回退）

## Decisions

### 1) 抽取到共享内部模块作为 SSOT（方案 B）

新增一个内部 util 模块 `src/scalim/_internal/utils/exceptions.py`，导出单一实现：

- `clone_exception_for_reraise(exc)`（不以下划线开头，表达为“内部共享工具”）

并在 `resources_base.py` 与 `preload_cache.py` 中改为导入该函数，删除本地重复实现。

模块位置选择原则：

- 放在 `_internal/utils/`，避免 execution/workflow 之间相互依赖导致层级反转或循环导入；
- util 模块不得依赖 workflow/execution 的高层符号。

### 2) 将现有测试迁移为测试 util，并保持调用路径回归覆盖

现有测试已覆盖 workflow 版本的 fallback 行为；Phase 0 将其迁移为直接测试 util（单点权威口径），并补充断言确保：

- `copy.copy` 失败时 fallback；
- ctor 失败时 fallback；
- clone 后 args 一致；
- 在可 clone 的异常上 clone 得到不同实例（且 traceback 被清理为 best-effort）。

同时在 preload_cache 路径增加一条间接覆盖（或最小 smoke），防止未来调用点偏离。

## Risks / Trade-offs

- **导入边界风险**：若 util 放置位置不当可能引入循环；通过 `_internal/utils` 层吸收可最大化避免。
- **行为一致性**：两份实现虽然近似，但仍需确认 edge cases（异常类型不可 copy/不可 ctor）的一致性；用迁移后的单测作为回归护栏。

## Migration Plan

- Phase 0：新增 util + 迁移两处调用点 + 迁移/补齐单测 + 跑 `just quick-qa-only-py`
- 后续：若未来出现第 3 个类似需求，必须复用 util 而不是复制粘贴

## Open Questions

- 无。
