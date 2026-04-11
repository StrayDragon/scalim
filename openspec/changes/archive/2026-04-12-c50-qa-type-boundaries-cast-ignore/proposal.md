## Meta

- Type: `qa-0`
- Topic: runtime 边界处的 `cast()` / `type: ignore` 热点收敛（可读性 + 类型契约）
- Related code (样例点位):
  - `src/scalim/dsl/yaml_dsl/_internal/config_parsing/validator.py:164`（`outputs_raw` → `Optional[List[object]]` cast）
  - `src/scalim/spec/ir/_sources.py:256` / `src/scalim/spec/ir/_sources.py:294`（`type: ignore[call-arg]`：动态签名调用）
  - `src/scalim/execution/key_normalization.py:11`（`type: ignore[return-value]`：`Literal` 返回）

## 背景

本仓库的工程治理很强（`ruff` + `basedpyright`），同时运行时代码（`src/scalim/`）需要保持 Python 3.6 兼容，因此在“动态结构解析 / 运行时边界”处出现一定数量的 `cast()`、`type: ignore` 是合理的。

问题不在于“使用 cast/ignore”，而在于：

- cast/ignore 分散在业务逻辑中，导致可读性下降；
- 同类窄化逻辑重复实现（比如 list/dict 的检查与路径拼接）；
- 少量 ignore 可能掩盖真实 bug（尤其是 call signature 相关的调用）；
- 评审时很难判断某个 `type: ignore` 是“有意的边界豁免”还是“临时绕过”。

该提案目标是形成 **“runtime 边界窄化的统一模式”**：把必要的动态性集中在少量 helper/边界层里，让业务逻辑更像“处理已经被验证过的结构化对象”。

## 现状与例子

### 例子 1：`validator.py` 的 mapping/list 窄化散落

在 `src/scalim/dsl/yaml_dsl/_internal/config_parsing/validator.py:158` 起的逻辑中，反复出现：

- `outputs_raw = config.get("outputs")`
- `outputs = cast("Optional[List[object]]", outputs_raw if isinstance(outputs_raw, list) else None)`
- 再对每项做 `dict` 判定与 cast

这类代码在 runtime 上是安全的，但阅读成本高（并且每个函数都要重新写一次）。

### 例子 2：动态签名调用导致 `type: ignore[call-arg]`

`src/scalim/spec/ir/_sources.py:230`~`:299` 的 `_call_normalize_call_by` 与 fallback 会根据 `inspect.signature` 推断参数形态：

- `fn(result, ctx)` / `fn(result, ctx=ctx)` / `fn(result)`

类型系统很难表达“根据签名动态选择调用形态”，于是出现 `type: ignore[call-arg]`。

风险在于：如果未来签名判定逻辑回归或增加新形态，类型检查不会帮助我们发现错误（只能靠测试/运行时暴露）。

### 例子 3：`Literal` 返回值的 `type: ignore[return-value]`

`src/scalim/execution/key_normalization.py:6`~`:13`：

- `KeyNormalizationMode = Literal["raw", "auto_str", "force_str"]`
- `raw` 是 `str`，即使做了枚举 membership check，类型推导仍不够智能，导致 `type: ignore`。

这类 ignore 属于“低风险、可被标准写法替代”的点。

## 目标

- 让绝大多数业务逻辑不直接写 `cast()/type: ignore`；
- 将“窄化/校验/路径报错拼接”集中到可复用 helper；
- 对必须 ignore 的地方建立“显式 allow”与回归测试；
- 保持 Python 3.6 兼容（使用 `src/scalim/vendor/compact/typing_extensionsx.py` 的能力）。

## 方案候选

### 方案 A：引入 `narrowing` helper（推荐）

做法：

- 新增一个内部模块作为通用 SSOT（推荐落在 `src/scalim/_internal/type_narrowing.py`，便于多领域复用）。
- 提供少量常用窄化函数，返回值自带类型收窄，避免到处写 `cast()`：
  - `as_mapping(value, *, path) -> Dict[str, Any] | None`
  - `as_list(value, *, path) -> List[Any] | None`
  - `require_str(value, *, path) -> str`
  - `mapping_get_str(mapping, key, *, path) -> Optional[str]`
- 在 `validator.py` 等模块逐步替换散落的 `isinstance+cast` 片段。

优点：

- 阅读体验提升明显；
- 能把错误信息生成口径统一（path/消息一致）；
- 后续新增解析逻辑更快，且更不容易写错。

缺点：

- 需要一次性引入基础 helper，并做小范围迁移（但可渐进）。

性价比：

- 高（中等成本，长期收益大）。

### 方案 B：把 ignore 聚拢到“边界函数”，并补回归测试（推荐作为方案 A 的补充）

做法：

- 对 `_call_normalize_call_by` 这类不可避免的 ignore：保证 ignore 只存在于 1~2 个函数内；
- 为其补“签名矩阵测试”（至少覆盖：`fn(result, ctx)`、`fn(result, *, ctx)`、`fn(result, **kwargs)`、`fn(result)`、以及 `inspect.signature` 不可用的 fallback）。

优点：

- 即使类型系统无法覆盖，测试可以作为护栏；
- ignore 点位集中，审计更容易。

缺点：

- 需要新增/维护测试矩阵。

性价比：

- 高（非常值得做的防回归投入）。

### 方案 C：继续保持现状（不推荐）

缺点：

- 可维护性与评审成本继续恶化；
- ignore 扩散后，很难做“治理收敛”。

## 推荐方案

推荐 **方案 A + 方案 B 组合**：

- A 负责把“结构窄化”从业务逻辑中抽离；
- B 负责把“类型系统无能为力的动态调用”用测试兜住，并把 ignore 点位固定下来。

## 性价比与落地优先级

- 优先级 P0（值得尽快做）：`key_normalization.py` 这类 `Literal` ignore（改成 `cast(KeyNormalizationMode, raw)` 即可）与 `_call_normalize_call_by` 的签名矩阵测试。
- 优先级 P1：`validator.py` 等 YAML parsing/cleaning 的 narrowing helpers 重构。

## 验证建议（QA）

- `just quick-qa-only-py`（确保类型检查/format/lint 不回归）。
- 新增针对 `_call_normalize_call_by` 的测试矩阵，避免未来 Python 版本/inspect 行为变化引发回归。
- 对新 helper 的错误信息做快照断言（确保 path/消息稳定）。
