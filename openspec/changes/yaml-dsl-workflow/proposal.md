## Why

在迁移“批量报表脚本”到 YAML DSL 时,常见形态是多事实流(demand) + Python 聚合 + 多 sheet 输出。
目前多条 demand 的编排主要靠 Python glue:
- 难以复用与标准化(每个团队/脚本各写一套调度代码)
- 无法统一失败策略与并发策略
- `preload_forever` 小表只能在单次 demand 内预加载复用,跨 demand 仍会重复加载,浪费时间与资源
- runs 级并发与 demand 内并行缺少统一约束,容易出现“并发乘法效应”(workflow 并发 * demand 内并行),导致资源不可控

因此需要一个独立于单 demand 的 declarative workflow/compose 层,用于编排多个 demand(串行/有限并发),并可选择跨 run 共享 `preload_forever` cache 与统一 failure_policy。

## What Changes

- 新增 workflow YAML 文件语法(独立于 demand),用于声明多条 demand 的 runs 编排:
  - runs 顺序
  - `max_concurrency`
  - `failure_policy`
  - `share_preload_cache`
- 不扩展 CLI。提供 Python 侧 workflow 运行入口(与现有 `run` 并列),并复用已有 demand 编译/执行链路。
- 路径解析规则明确且可复用:
  - run.demand 相对路径以 workflow 文件所在目录为基准
  - 支持通过 Python 入口注入 `path_aliases`(与 `yaml-dsl-imports` 共用),用于解析 `"@/..."` / `"ALIAS:/..."` 风格路径
- 并发/确定性边界固定:
  - `max_concurrency` 仅控制 runs 粒度并发(worker pool),不改变单条 demand 的既有执行语义
  - workflow 返回结果顺序必须与 `workflow.runs` 声明顺序一致(并发不影响顺序),保证对拍与回归可预测
- 失败策略提供可编程检查的错误结构(避免只靠日志):
  - `failure_policy=all_fail`: 首个失败 run 立即使 workflow 失败,错误中包含 run id 与 demand 路径
  - `failure_policy=primary_only`: 失败 run 被跳过但 workflow 继续,返回值包含成功结果 + 失败集合(含 run id 与错误摘要/指纹)
- 当 `share_preload_cache=true` 时:
  - `preload_forever` 小表在同一 workflow 执行中只加载一次并跨 runs 复用
  - 对同一 `source_id` 的 preload 规格做一致性签名校验,至少覆盖:
    - loader 引用(归一化后的 reference)
    - 渲染后的静态 params(含 runtime_vars 注入结果;`preload_forever` 禁止 `$keys/$rows` 后应为静态)
    - normalize 配置
    - key/lookup_cast/lookup_chunk_size 等会影响 mapping 形状与 lookup 语义的关键字段
  - 若签名不一致,系统 fail-fast 报错,错误信息包含冲突 runs 与差异字段,避免静默复用错误缓存
  - 并发下对单个 `source_id` 细粒度加锁,保证最多一次真实 loader 调用;其余等待复用结果(避免重复 IO)

## Capabilities

### New Capabilities
- `yaml-dsl-workflow`: YAML 层 declarative workflow 编排多 demand,支持有限并发、统一失败策略与可选共享 `preload_forever` 缓存。

### Modified Capabilities
- (none)

## Impact

- 新增 workflow 配置解析/校验与 Python 运行入口。
- 执行层需要支持把 `preload_forever` cache 从单次 demand runtime 提升为可注入/可共享的容器(仅 workflow 场景启用)。
- 增加 workflow 的单元/集成测试与文档说明(遵循生成物治理规则)。

## Notes / Recommendations

- 默认建议 workflow 的并发控制以“runs 粒度”做总闸,并在文档中强调: 若 runs 并发开启,单条 demand 的 `parallel_mode/adaptive` 与 `max_workers` 也会叠加贡献资源消耗。
- workflow MVP 不强制做“全局输出路径冲突检测”(避免与业务输出策略强耦合),但文档应明确建议: 在 workflow 中为每个 run 的输出路径做隔离或由调用侧 overrides 统一管理。
