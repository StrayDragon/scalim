## 1. 配置面与常量治理

- [x] 1.1 在 `pyproject.toml` 声明实验性 env：`SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES`、`SCALIM_EXP_CALL_BY_MEMOIZE_ALLOW`、`SCALIM_EXP_CALL_BY_MEMOIZE_DENY`、`SCALIM_EXP_CALL_BY_MEMOIZE_LOG_STATS`
- [x] 1.2 扩展 `scripts/gen-project-constants.py` 生成上述 env 常量（避免手写漂移）
- [x] 1.3 运行 `just gen-project-constants` 并通过 `just project-constants-drift-check`

## 2. Field filter 解析与契约

- [x] 2.1 实现 allow/deny CSV patterns 解析（按 `,` 分割、`strip()`、忽略空项）
- [x] 2.2 实现通配符匹配与优先级规则（allow 为空=不过滤；deny 覆盖 allow）
- [x] 2.3 补齐单测：覆盖 allow/deny 的典型组合与边界（空串、多逗号、空白）

## 3. Memoization 运行时集成（ctx-free call_by）

- [x] 3.1 在执行层识别 `ctx-free call_by` 字段，且仅在 `SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES>0` 时启用候选
- [x] 3.2 在候选字段上应用 allow/deny filter（未命中 allow 或命中 deny → 不缓存）
- [x] 3.3 引入“按字段 LRU（容量=N）”并保证硬上限；仅缓存成功返回值且缓存 transform 前结果
- [x] 3.4 引入字段级保护策略（高基数/低命中字段可 disabled 并清空缓存），并补齐单测覆盖禁用路径

## 4. `scalim.performance` 可选统计日志

- [x] 4.1 新增聚合统计采集结构（hits/misses/unique/evict/disabled 等，保证不保存依赖值本身）
- [x] 4.2 仅当 `SCALIM_EXP_CALL_BY_MEMOIZE_LOG_STATS` 启用时，在运行结束输出一次 top-n 摘要日志
- [x] 4.3 补齐单测：关闭时不输出；开启时输出包含字段 key 与计数字段

## 5. 验收与门禁

- [x] 5.1 运行 `just check-only-py` 与 `just qa`
- [x] 5.2 运行 `just openspec-check`，确保工件可共享且不含业务数据
