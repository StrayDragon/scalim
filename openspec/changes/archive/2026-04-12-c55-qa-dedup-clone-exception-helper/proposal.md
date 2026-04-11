## Meta

- Type: `qa-0`
- Topic: `_clone_exception_for_reraise()` 重复实现收敛（避免漂移 + 统一测试口径）
- Related code:
  - `src/scalim/workflow/resources_base.py:87`
  - `src/scalim/execution/preload_cache.py:96`
  - Call sites:
    - `src/scalim/workflow/resources_base.py:582` / `:611`
    - `src/scalim/execution/preload_cache.py:201` / `:252`
  - Existing tests reference workflow 版本：
    - `tests/workflow/test_workflow_resources_coverage.py:101`（`test_clone_exception_for_reraise_handles_fallbacks`）

## 背景

仓库在多个“跨线程等待/聚合”场景中，会把 owner 线程抛出的异常存入 inflight 状态，再由 waiter 线程重新抛出。为了避免：

- 复用同一个异常对象导致 traceback/上下文被污染；
- 在异常对象上携带大量 traceback 引用，造成不必要的内存占用；

实现了 `_clone_exception_for_reraise(exc)`：

1) 尝试 `copy.copy(exc)`；失败则 fallback；  
2) 尝试 `exc.__class__(*exc.args)` 构造；再失败则退回原异常对象；  
3) 存储前通常再 `with_traceback(None)` 清理 traceback（best-effort）。

这类 helper 的逻辑属于“基础设施”，一旦多处复制就会出现：

- 行为漂移：某处修 bug 但另一处未同步；
- 测试覆盖不一致：只测了一处；
- 维护者认知负担：需要记住哪个版本才是“权威实现”。

目前仓库中至少有两份实现，且几乎等价。

## 现状

两份实现：

- `workflow/resources_base.py` 版本：
  - `copy.copy` 失败后尝试 `exc.__class__(*exc.args)`。
- `execution/preload_cache.py` 版本：
  - 同样逻辑，但显式 `args = exc.args`（行为一致）。

调用语义也一致：

- owner 捕获异常后 clone + 去 traceback，存入 inflight；
- waiter 在 inflight.done 后若有 error，则 clone 再 raise。

## 例子（为什么需要 clone）

假设 preload owner 线程里 `load_fn()` 抛出异常 `ValueError("bad")`。

- 如果直接把原异常对象存入 inflight，再由 waiter 线程 `raise inflight.error`：
  - traceback 可能包含 owner 线程栈，且 error 对象可能被多次 re-raise 叠加上下文；
  - 在某些异常类型上，直接跨线程共享同一异常对象会让诊断与内存占用更不可控。

clone + `with_traceback(None)` 能把异常降维成“类型 + args”，更符合“跨线程传播错误信号”的语义。

## 目标

- 保证 clone 语义全仓一致；
- 把测试口径覆盖到“唯一实现”；
- 迁移成本低、避免引入导入环；
- `src/scalim/` 保持 Python 3.6 兼容。

## 方案候选

### 方案 A：保持重复实现（不推荐）

优点：

- 无需改动导入关系。

缺点：

- 长期必然漂移（已经重复，未来再出现第 3 份概率更高）。

性价比：

- 低。

### 方案 B：抽到共享内部模块（推荐）

做法：

- 新增一个稳定的内部 util：`src/scalim/_internal/utils/exceptions.py`
- 导出 `clone_exception_for_reraise(exc)`（不带下划线，表达为可复用的内部公共工具）。
- `resources_base.py` 与 `preload_cache.py` 都改为导入该函数，删除本地重复实现。
- 将现有测试迁移为测试该 util（并补一条覆盖 preload_cache 使用场景的断言，避免回归）。

优点：

- 消除漂移；
- 单点测试、单点修复；
- 评审更容易（知道“权威实现”在哪里）。

缺点：

- 需要选择合适的模块位置以避免循环依赖（但这是可控的：放在 `_internal/utils/` 通常最安全）。

性价比：

- 高（小改动，高收益）。

### 方案 C：直接依赖 workflow 版本（不推荐）

做法：`preload_cache.py` 直接 `from scalim.workflow.resources_base import _clone_exception_for_reraise`

缺点：

- 模块分层倒置（execution 依赖 workflow），容易引入环或未来治理门禁；
- 语义上不合理。

## 推荐方案

推荐 **方案 B**：抽到 `_internal/utils/`，统一实现与测试。

## 验证建议（QA）

- 迁移后跑 `just quick-qa-only-py`。
- 保留并扩展 `tests/workflow/test_workflow_resources_coverage.py:101` 中的覆盖点：
  - `copy.copy` 失败 fallback；
  - ctor 失败 fallback；
  - clone 后 args 保持一致；
  - clone 对象不是同一个实例（在可 clone 的异常上）。
