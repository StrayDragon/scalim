
• 已完成 / 验证

  - just check-only-py ✅（含 100% statements + 100% branches coverage）
  - just qa ✅
  - StrEnum 兼容版补齐 __str__ -> self.value，让 py<3.11 的 str(StrEnumMember) 行为与 3.11+ 一致，避免 "EnumClass.MEMBER" 这个坑：src/scalim/vendor/compact/__init__.py:21

  “强约束只允许内置值”在 policy 上的推进

  - 新增 FailurePolicyValue/FailurePolicyLike + normalize_failure_policy(...) -> Literal[...]，把对外/状态边界统一落到稳定内置 str（并做 strip/lower/replace('-', '_')）：src/
    scalim/typedefs.py:155
  - 关键链路已接入并复用该 normalize（避免散落的 str(...).strip()）：
      - workflow：src/scalim/workflow/execute.py:412、src/scalim/workflow/execute_controller.py:316
      - output composition：src/scalim/execution/output_composition.py:567
      - multi-root workbook：src/scalim/execution/workbook_multi_root.py:37
  - 对应补齐了覆盖率与回归测试：tests/governance/test_failure_policy_normalize.py

  PreloadCache / 多进程 pickling

  - 由于当前 adaptive backend 明确只支持 thread（非 thread 会直接报错），PreloadCache 的 pickle roundtrip 支持属于“多进程假设”残留：已移除 PreloadCache.__getstate__/__setstate__
    与相关测试段落（锁/事件本来也不可 pickle）。
      - 实现：src/scalim/execution/preload_cache.py:100
      - 测试：tests/execution/test_preload_cache.py:1

  关于 Dict→Mapping 是否符合最佳实践

  - 是的：Mapping[K, V] 表达“只读接口”（调用方不应写入），Dict/MutableMapping 表达“可写/可变容器”。
  - 但注意：Mapping 只约束接口，不保证运行时不可变；如果你要运行时也强约束不可写，需要 MappingProxyType（浅冻结）或更深层的不可变结构。

  哪些地方“需要 pickle”（当前保留且有测试保障）

  - 观测/Hook 管理器：为重建锁、订阅缓存、运行期派生字段，保留 __getstate__/__setstate__：
      - src/scalim/hooks/_internal/manager_state.py:18
      - src/scalim/ob/_internal/manager_state.py:36
      - src/scalim/ob/hub.py:58
  - 冻结 IR（MappingProxyType 不可 pickle）：通过 state 钩子做 proxy↔dict 的 roundtrip：
      - src/scalim/spec/ir/_sources.py:207、src/scalim/spec/ir/_demand.py:83、src/scalim/spec/ir/_fields.py:129、src/scalim/spec/ir/binding/__init__.py:232

  如果你希望把“只允许内置值”的策略推到其它 policy（例如 ObserverManagerMode/CaptureOverflowPolicy/LoaderResultPolicy 等），我可以按 normalize_failure_policy 这套模式再做一轮：对
  外收 str/Literal，内部可保留 enum 常量，但所有状态/序列化边界一律输出纯 str。
