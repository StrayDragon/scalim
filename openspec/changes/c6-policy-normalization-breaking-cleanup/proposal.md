## Why

`_NEXT.md` 已经把 `FailurePolicy` 推进到了“对外/状态边界统一落到稳定内置 str”的模式: 通过 `normalize_failure_policy(...) -> Literal[...]` 收敛输入,并在关键链路复用。

但仓库内仍存在多组 policy-like 值沿用 `StrEnum`(或 `Union[str, StrEnum]`) 的混合模式(例如 `LoaderResultPolicy`、`ObserverManagerMode`、`CaptureOverflowPolicy` 等)。即使我们已经修复了 `StrEnum.__str__` 的跨版本坑,这些类型仍会带来:
- 状态/序列化边界不够“纯”: 值可能以 Enum 形态在对象图里流动
- 下游/三方代码若做 `type(x) is str` 或 JSON 序列化,可能出现不一致行为
- 规范层面难以声明“唯一允许的内置值集合”(缺少统一的 Value/Literal 类型)

你希望同步做 breaking change 清理,并把 normalize 模式推广到其它 policy。这个 change 将把这些 policy 统一迁移到 FailurePolicy 同款模式: 对外接收 `str`(必要时允许旧 enum 过渡),内部与状态边界一律存储稳定内置 `str`。

## What Changes

- 为一组高优先级 policy 引入 `...Value = Literal[...]` + `normalize_...(...) -> ...Value`:
  - `LoaderResultPolicy`
  - `ObserverManagerMode`
  - `CaptureOverflowPolicy`
  - （可选/后续）`SourceSpecIrCacheMode` 等其它封闭集合
- 将关键状态/序列化边界字段改为存储内置 `str` 值(而不是 enum 对象):
  - `HookManager` / `ObserverManager` / state mixins
  - workflow/execution 的 runtime options(若涉及)
- 清理旧写法(必要时做一次性 breaking 移除):
  - 移除对 enum 入参的支持或将其限制为内部-only
  - 更新 docs/specs/tests

## Capabilities

### New Capabilities

- `runtime-policy-normalization`: 定义 policy 值的 SSOT 归一化规则与“状态/序列化边界必须输出内置 str”的契约。

### Modified Capabilities

- （无）

## Impact

- 受影响代码(预期):
  - `src/scalim/_internal/utils/loader_result.py`
  - `src/scalim/ob/_internal/common.py`
  - `src/scalim/hooks/*` 与 `src/scalim/ob/*` 的 manager/state 逻辑
  - 可能涉及 `src/scalim/execution/run_ir.py` 与 workflow bridge 中对 policy 的设置
- **BREAKING**:
  - 公共 API 若暴露这些 enum 类型,将迁移为 `Literal[str]` 值集合(或至少在 runtime/state 边界只输出 str)
