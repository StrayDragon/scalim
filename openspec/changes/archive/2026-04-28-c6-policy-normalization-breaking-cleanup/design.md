## Context

### 关键路径清单(调研结果)

1. LoaderResultPolicy
- 定义: `src/scalim/_internal/utils/loader_result.py`
- 入口/存储:
  - `HookManager`/`ObserverManager` 构造函数接收 `loader_result_policy: LoaderResultPolicyLike`
  - state mixins 在 pickling/unpickling 时会序列化/恢复该字段
- 典型写入点:
  - `src/scalim/execution/run_ir.py` / `src/scalim/workflow/execute.py` 会在 capture 场景把 policy 切到 `summary`

2. ObserverManagerMode / CaptureOverflowPolicy
- 定义: `src/scalim/ob/_internal/common.py`
- 入口/存储:
  - `ObserverManager.__init__(mode=..., capture_overflow_policy=...)`
  - `ObserverManagerStateMixin`/`manager_state.py` 在状态序列化边界会经过这些字段

3. FailurePolicy(已完成模式样板)
- 定义: `src/scalim/typedefs.py` 中 `FailurePolicyValue + normalize_failure_policy`
- 多条关键链路已接入 normalize,并在状态/序列化边界输出内置 `str`

### 问题

- 现有 policy 多以 `StrEnum` 形式在对象图里流动。
- 即使 `StrEnum` 是 `str` 子类,它仍可能在 JSON 序列化/类型比较/跨边界传递时产生意外行为或额外复杂度。

## Goals / Non-Goals

Goals:
- 将 policy 值统一为 FailurePolicy 同款模式:
  - `...Value = Literal[...]`
  - `normalize_...(...) -> ...Value`
  - state/序列化边界一律存储内置 `str`
- 在调研基础上点名“必须先收口”的关键路径(优先覆盖 manager/state 与 workflow bridge)。

Non-Goals:
- 不在本 change 中把所有 StrEnum 都替换成 Literal(只处理 policy-like 且跨边界流动的值集合)。

## Decisions

1. 优先级与推进顺序
- P0: `LoaderResultPolicy` (hook/observer manager state + workflow bridge)
- P0: `ObserverManagerMode` / `CaptureOverflowPolicy` (manager/state)
- P1: 视影响面再评估 `SourceSpecIrCacheMode` 等其它封闭集合

2. 统一 normalize 风格
- 与 `normalize_failure_policy` 对齐:
  - 接受 `None` 走默认值
  - 接受 `str`(strip/lower/必要时 `-`→`_`)
  - 输出稳定内置 `str` (Value/Literal)
- 是否临时兼容旧 enum 入参:
  - 由于你希望 breaking 清理,默认倾向于“不再对外接受 enum 类型”,但可在内部过渡期保留 `isinstance(value, OldEnum)` 分支,并在 release note 中说明。

3. 状态边界收口
- manager/state 对外暴露或参与 pickling 的字段必须是内置 `str`。
- `__getstate__/__setstate__` 应确保序列化的数据结构仅包含内置类型(至少不包含 enum 对象)。

## Risks / Trade-offs

- [风险] BREAKING: 外部调用方若传入旧 enum 实例会失败。
  - 缓解: 提供清晰错误信息(期望值集合),并在变更说明里列出迁移方式(改传字符串)。

- [风险] 迁移范围跨 hooks/ob/workflow 多个模块。
  - 缓解: 按优先级拆任务并配套回归测试,每一步都能 `just qa` 验证。

## Migration Plan

- 先在 normalize 函数层引入 `...Value` 类型与统一 normalize。
- 再逐步把 manager/state 字段类型改为 `...Value` 并清理对 enum 的依赖。
- 最后清理/限制 enum 类型的 public surface(若仍有 re-export)。

## Open Questions

- 是否需要为 policy 值提供统一的“normalize utilities”模块(类似 `typedefs.normalize_failure_policy`),以避免未来再出现散落的 `str(...).strip()`?
> yes