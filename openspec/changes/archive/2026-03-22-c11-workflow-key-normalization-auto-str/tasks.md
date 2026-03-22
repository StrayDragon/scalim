## 1. API / IR Threading

- [x] 1.1 为 `key_normalization` 定义取值域与校验(`raw | auto_str | force_str`),并在公共入口 fail-fast
- [x] 1.2 扩展 by_yaml `RunOptions`/`entrypoints.run`/`entrypoints.compile` 支持 `key_normalization`
- [x] 1.3 扩展 workflow `run_workflow` 入口 threading `key_normalization` 到执行期上下文
- [x] 1.4 扩展 execution core: `ExecutionRequest`/`ExecutionRuntime` 增加并持有 `key_normalization`(SSOT),并贯穿到 relations/derived outputs 所需位置
- [x] 1.5 当 `key_normalization` 启用非 `raw` 模式(`auto_str/force_str`)时,发出 `EXPERIMENTAL` 运行期告警/诊断事件(一次运行去重),且不得泄露明细 key 值

## 2. Relations: 缺省 lookup key 规范化

- [x] 2.1 在 `src/scalim/utils/converters.py` 增加可复用的 `auto_str_normalize_key`(支持单键与复合键),并确保 error message 不包含明细值
- [x] 2.2 在 `ExecutionRuntime._normalize_lookup_key_status` 中按 spec 实现 `auto_str/force_str` 语义(含显式 cast precedence)
- [x] 2.3 处理 cached/preload sources: 当该 step 实际使用字符串规范化口径匹配时(例如 `force_str`,或 `auto_str` 缺省 fallback),提供 mapping 的规范化视图用于命中(出现 collision 必须 fail-fast)
- [x] 2.4 增补 relations 覆盖测试: `1` 与 `"1"` 在启用后命中同一映射;并覆盖 multi-field key 的逐字段 normalize 与 cached source 命中

## 3. Derived outputs: group_by / dedup_by 合并边界

- [x] 3.1 扩展 output composition threading: 将 run-level `key_normalization` 传递到 derived aggregator 构造(必要时调整 `IDerivedAggregationSpec.build_aggregator(...)` 的签名并升级所有调用点)
- [x] 3.2 在 `GroupByAggregator` 中实现字符串 key 规范化(`auto_str/force_str`)(允许 raw `None`;非 `None` 但规范化失败则 fail-fast)
- [x] 3.3 在 `DedupByThenAggregator` 中实现字符串 key 规范化(`auto_str/force_str`)(冲突判定基于规范化后的 key;输出 key 字段与内部口径一致)
- [x] 3.4 增补 derived outputs 覆盖测试: `group_by`/`dedup_by` 在启用后合并 `1` 与 `"1"`;并覆盖“规范化失败时 fail-fast”的错误信息不泄露明细值

## 4. Specs / Docs / Gates

- [x] 4.1 将本 change 的 specs 同步到 `openspec/specs/`(以 specs 为 SSOT;同步后运行 `just openspec-check`)
- [x] 4.2 若新增/修改了 docs-site 生成物或 injected blocks,仅修改 SSOT 并通过 `just gen-docs` 刷新(不手改 `.gen.*` 与 injected blocks)
- [x] 4.3 验收门禁: `pytest`(含覆盖率门禁)、`just qa`、`just openspec-check`
