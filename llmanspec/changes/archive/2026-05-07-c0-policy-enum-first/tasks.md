## 1. Policy SSOT & Helpers

- [x] 1.1 Inventory 当前 policy-like 定义与入口，列出需要迁移的点位（至少覆盖 `LoaderResultPolicy` / `ObserverManagerMode` / `CaptureOverflowPolicy` / `FailurePolicy`，以及它们被写入 state/pickle 的路径）。
  - `LoaderResultPolicy` 定义/SSOT: `src/scalim/_internal/utils/loader_result.py`
  - `HookManager` public 输入落地: `src/scalim/hooks/_base.py`
  - `HookManager` state/pickle 边界: `src/scalim/hooks/_internal/manager_state.py` (`__getstate__`/`__setstate__`)
  - `ObserverManagerMode`/`CaptureOverflowPolicy` 定义/SSOT: `src/scalim/ob/_internal/common.py`
  - `ObserverManager` public 输入落地: `src/scalim/ob/manager.py`
  - `ObserverManager` state/pickle 边界: `src/scalim/ob/_internal/manager_state.py` (`__getstate__`/`__setstate__`)
  - `FailurePolicy` 定义/SSOT: `src/scalim/typedefs.py`
  - `FailurePolicy` 解析入口(跨边界): `src/scalim/typedefs.py::parse_failure_policy`
  - `FailurePolicy` public 输入落地(严格 Enum): `src/scalim/typedefs.py::normalize_failure_policy`
- [x] 1.2 引入通用的 policy Enum parse/format SSOT 工具（Python 3.6 兼容）：从 Enum 派生允许值列表与稳定 label，并提供大小写/`-/_` 归一化策略（用于 YAML/反序列化入口）。

## 2. LoaderResultPolicy（hooks/ob 共用）

- [x] 2.1 将 `LoaderResultPolicy` 恢复为 `StrEnum`（或等价 Enum SSOT），移除手工维护的 `Literal[...]` 允许值集合（保持 DRY）。
- [x] 2.2 调整 public 构造器/Options：接口层严格只接受 Enum；为 YAML/反序列化边界提供 parse（builtin `str` → Enum）入口。
- [x] 2.3 内部表示保持 canonical builtin `str`（由 Enum `.value` 一次性落地），避免热路径改写；内部比较继续使用字符串（但允许值/label 从 Enum 派生，禁止手写重复列表）。
- [x] 2.4 调整 `HookManagerStateMixin.__getstate__/__setstate__` 与 `ObserverManagerStateMixin.__getstate__/__setstate__`：
  - state 输出必须只包含 builtin `str`（无 Enum 实例/`str` 子类）
  - state 输入从 builtin `str` fail-fast 校验（通过 Enum SSOT parse），并落地为 canonical builtin `str`

## 3. ObserverManagerMode / CaptureOverflowPolicy

- [x] 3.1 将 `ObserverManagerMode` / `CaptureOverflowPolicy` 恢复为 Enum SSOT，移除 `Literal[...]` 允许值集合与重复常量列表。
- [x] 3.2 更新 `ObserverManager` / Observability options：对外 API 只接受 Enum；配置入口（YAML/反序列化）使用 parse 将 builtin `str` 恢复为 Enum。
- [x] 3.3 确保 manager/state 的序列化边界不包含 Enum 实例（只输出 builtin `str`）。

## 4. FailurePolicy DRY Cleanup

- [x] 4.1 清理 `FailurePolicy` 的 Enum + Literal 双定义：保留 Enum 作为唯一 SSOT；删除手工维护的 `FailurePolicyValue = Literal[...]`（或改为内部不重复的等价表达）。
- [x] 4.2 更新所有调用点：public API 类型收窄为 Enum；YAML/反序列化入口从 builtin `str` 校验并落 canonical builtin `str`（基于 Enum SSOT）；内部 normalize/比较逻辑对齐新的 parse/format SSOT。
- [x] 4.3 更新/新增回归测试：覆盖 Enum 输入、字符串 config 解析、以及 pickle/state roundtrip（要求 state 中对应字段为 builtin `str`，恢复后仍为 canonical builtin `str`）。

## 5. Docs / Governance / Release Notes

- [x] 5.1 更新用户侧示例与升级说明：将 policy 示例统一为 Enum 写法（`XPolicy.FOO`），并明确 state/wire 仍是字符串值。
- [x] 5.2 将 policy SSOT 约束写入仓库级 SSOT（`AGENTS.md`），避免未来回归到 Enum/Literal 双定义或边界泄漏 Enum 实例。
- [x] 5.3 若涉及 docs 生成物或 injected blocks：只改 SSOT，运行 `just gen-docs` 生成/注入；禁止手工编辑任何 `*.gen.*` 文件或 `BEGIN/END AUTOGEN:*` 区块内部。
- [x] 5.4 运行质量门禁：`just openspec-check` + `just qa`；并确保变更点对应的 governance tests 全部通过。
