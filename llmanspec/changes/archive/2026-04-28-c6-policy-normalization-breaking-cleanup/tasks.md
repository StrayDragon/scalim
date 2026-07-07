## 1. Introduce Value Types + Normalizers

- [x] 1.1 为 `LoaderResultPolicy` 引入 `LoaderResultPolicyValue = Literal[...]` 与 `normalize_loader_result_policy(...) -> LoaderResultPolicyValue` (输出内置 str)
- [x] 1.2 为 `ObserverManagerMode` 引入 `ObserverManagerModeValue` 与 normalize
- [x] 1.3 为 `CaptureOverflowPolicy` 引入 `CaptureOverflowPolicyValue` 与 normalize

## 2. Migrate Runtime/State Boundaries

- [x] 2.1 将 `HookManager`/`ObserverManager` 的对应字段类型改为 `...Value` 并确保构造函数入口统一 normalize
- [x] 2.2 检查并更新 hooks/ob 的 manager state pickling 逻辑: `__getstate__/__setstate__` 序列化数据不得包含 enum
- [x] 2.3 检查 workflow bridge 中对这些 policy 的派生/覆盖逻辑,确保复用 normalize 并输出内置 str

## 3. Breaking Cleanup

- [x] 3.1 移除或限制对旧 enum 入参的支持(至少在公开入口 fail-fast 并给出迁移提示)
- [x] 3.2 更新文档/示例/类型注解,确保对外 surface 只暴露稳定 str 值集合

## 4. Tests

- [x] 4.1 新增回归测试: manager state 在 pickle roundtrip 后 policy 字段仍为内置 str
- [x] 4.2 新增回归测试: 不同入口传入的 policy 值都会收敛到同一个 normalize 结果

## 5. Verification

- [x] 5.1 运行 `just qa`
- [x] 5.2 运行 `just openspec-check`
