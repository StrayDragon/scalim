# language: zh-CN
# capability: execution-derived-outputs
# purpose: 支持在同一次运行中基于详情行流生成派生输出(增量聚合 + finalize 阶段输出),并定义 IR/Python-only 配置入口、资源护栏与 `adaptive` 并发边界. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: execution-derived-outputs

  @req:r36 @human
  场景: 派生输出定义(同步聚合)
    - 系统 SHALL 支持在同一次运行中定义派生输出,派生输出可基于详情数据进行聚合/计算,并在运行结束时输出结果.

  @req:r280 @human
  场景: 增量聚合与批次累计
    - 系统 SHALL 支持派生输出以增量方式累计(按批次或流式),以避免加载全部详情数据.

  @req:r404 @human
  场景: 派生输出的数据来源选择
    - 系统 SHALL 允许派生输出明确选择其数据来源(例如直接消费运行期事件/批次结果,或基于已落盘的详情输出),以平衡内存与 I/O 成本.

  @req:r499 @human
  场景: 非增量指标的处理方式
    - 系统 SHALL 支持对不可增量的统计指标提供可行路径,包括可合并近似算法或二阶段后置聚合.

  @req:r577 @human
  场景: 聚合状态资源控制
    - 系统 SHALL 不在进程内为派生输出聚合状态提供基数护栏(如 max_groups/max_distinct);聚合状态规模不受限,内存过载风险交由宿主系统层(如 OOM killer)兜底.

  @req:r637 @human
  场景: IR/Python 配置入口
    - 系统 SHALL 仅提供 IR/Python 方式配置派生输出,并保持 YAML DSL 不变.

  @req:r683 @human
  场景: `adaptive` 一致性边界
    - 系统 SHALL 明确 `adaptive` 并发下派生聚合的一致性边界,并在不满足条件时 fail-fast.

  @req:r755 @human
  场景: 内置 set 口径聚合原语
    - 系统 SHALL 在派生输出的内置聚合能力中提供 streaming-friendly 的 set 口径 metric 原语,用于减少业务侧 Python state 并提升复用性. 系统 MUST 至少支持 `count_distinct`(支持复合 key). 系统 MUST NOT 再提供 `dedup_by` / `two_stage_group_by` 一等派生装配原语(见 r160/r199).

  @req:r137 @human
  场景: `count_distinct` 复合 key 与缺失值语义
    - 系统 MUST 支持 `count_distinct` 同时接受单字段与复合 key. 系统 MUST 明确缺失值语义: - 当 distinct key 的任一组成字段为 `None` 时,该行 MUST 被忽略 - 空字符串 MUST 作为普通值参与 distinct.

  @req:r160 @human
  场景: `dedup_by` 派生装配已移除
    - 系统 MUST NOT 再提供 `DedupBySpec` / `DerivedDedupByGroupBySpec` / `DedupByThenAggregator` / `ScalimDedupKeyConflictError` / `DedupOnConflictPolicy`. 去重需求 MUST 由 loader/上游先去重,或接受重复行后仅使用 `DerivedGroupBySpec`.

  @req:r181 @human
  场景: `adaptive` 下的确定性边界
    - 系统 MUST 明确 `parallel_mode="adaptive"` 下的确定性边界: 自定义 `IDerivedAggregationSpec.validate_parallel_mode` 在不支持该并发模式时 MUST fail-fast;内置 `DerivedGroupBySpec` MUST NOT 再因已移除的顺序依赖装配(`dedup_by.on_conflict=first|last`)拒绝 `adaptive`(该路径已删除).

  @req:r199 @human
  场景: `two_stage_group_by` 派生装配已移除
    - 系统 MUST NOT 再提供 `TwoStageGroupBySpec` / `TwoStageGroupByAggregator`. 两阶段聚合需求 MUST 由 workflow 两个 demand/run 表达(stage1 写出中间表 → stage2 再聚合).

  @req:r230 @human
  场景: 最小条件计数原语
    - 系统 MUST 提供至少一种"可对拍且可指纹化"的条件计数能力,用于覆盖常见口径. 系统 MUST 至少支持: - `count_true_gte(field_id, threshold)`

  @req:r242 @human
  场景: meta/audit 的稳定指纹与结构化审计
    - 系统 MUST 为每个 derived target 生成稳定聚合指纹,并写入 meta sheet. 系统 MUST 满足: - meta 中 MUST 写入聚合指纹 - 当聚合发生错误时,系统 MUST 写入结构化 audit 行(仅脱敏信息) - 指纹 MUST 使用 `sha256` 计算,不得用于签名/认证等安全目的

  @req:r251 @human
  场景: aggregate producer key enums MUST be centralized
    - 系统 MUST 为 aggregate 输出相关的 producer keys 提供一个 SSOT 模块,并要求 YAML 解析、运行时装配、工具自省、JSON Schema、前端 editor 共享同一份枚举集合. 该 SSOT MUST 包含并可被引用: - metric producer keys - rank producer keys - post producer keys

  @req:r800 @human
  场景: 派生输出不再提供基数护栏配置
    - 系统 MUST NOT 为派生输出提供基数护栏配置(max_groups / max_distinct / distinct_on_overflow);相关的 IR 字段、运行期构造参数、YAML 字段与警告 MUST 被移除. 高基数聚合的内存风险由宿主系统层兜底,框架不再在进程内做基数限界.

  @req:r802 @human
  场景: 派生输出不再提供 score_by_rank 内置函数
    - 系统 MUST NOT 再提供 score_by_rank 内置后置派生字段. score_by_rank 的等价计算能力 MUST 通过 compute 表达式实现,公式为 base - (rank - 1) * step. 相关的 schema 定义、parser 解析函数、runtime 编译函数、AGG_POST_PRODUCER_KEYS 枚举项 MUST 被移除.
  @req:r36 @human
  场景: 订单明细-供应商利润率
    - 必须成立：当 详情输出包含订单ID/订单金额/订单利润/供应商ID；那么 系统应生成包含供应商ID与利润率的汇总输出
    当 详情输出包含订单ID/订单金额/订单利润/供应商ID
    那么 系统应生成包含供应商ID与利润率的汇总输出
  @req:r280 @human
  场景: 分批累计
    - 必须成立：当 详情数据按批次处理；那么 派生聚合应跨批次累计并在结束时输出完整结果
    当 详情数据按批次处理
    那么 派生聚合应跨批次累计并在结束时输出完整结果

  @req:r280 @human
  场景: 可合并统计-均值-比率
    - 必须成立：当 派生输出需要计算均值或比率；那么 系统应仅累计必要的分子/分母状态并在结束时输出结果
    当 派生输出需要计算均值或比率
    那么 系统应仅累计必要的分子/分母状态并在结束时输出结果

  @req:r280 @human
  场景: top-k-近似聚合
    - 必须成立：当 派生输出需要 Top-K 排名且数据量巨大；那么 系统应允许使用可合并的近似算法并以有限内存完成累计
    当 派生输出需要 Top-K 排名且数据量巨大
    那么 系统应允许使用可合并的近似算法并以有限内存完成累计
  @req:r404 @human
  场景: 列式输出的后置聚合
    - 必须成立：当 详情输出采用列式或落盘模式；那么 派生输出可选择在详情落盘后进行聚合
    当 详情输出采用列式或落盘模式
    那么 派生输出可选择在详情落盘后进行聚合

  @req:r404 @human
  场景: 事件流增量聚合
    - 必须成立：当 派生输出选择消费运行期事件或批次结果；那么 系统应允许在详情写入后立即更新聚合状态而不保留明细
    当 派生输出选择消费运行期事件或批次结果
    那么 系统应允许在详情写入后立即更新聚合状态而不保留明细
  @req:r499 @human
  场景: 需要全量数据的指标
    - 必须成立：当 指标无法在单批次内增量计算；那么 系统应允许使用近似算法或选择后置聚合模式完成输出
    当 指标无法在单批次内增量计算
    那么 系统应允许使用近似算法或选择后置聚合模式完成输出

  @req:r499 @human
  场景: 精确分位数后置聚合
    - 必须成立：当 需要精确分位数且不允许近似；那么 系统应允许将该指标标记为后置聚合并在详情落盘后计算
    当 需要精确分位数且不允许近似
    那么 系统应允许将该指标标记为后置聚合并在详情落盘后计算

  @req:r577 @human
  场景: 无护栏默认运行
    - 必须成立：假如 派生输出未配置任何基数护栏；当 运行执行派生聚合；那么 系统 MUST 不发出基数相关 warn,且 MUST 不对聚合键数量做进程内限界检查
    假如 派生输出未配置任何基数护栏
    当 运行执行派生聚合
    那么 系统 MUST 不发出基数相关 warn,且 MUST 不对聚合键数量做进程内限界检查

  @req:r577 @human
  场景: 高基数场景不受限
    - 必须成立：假如 派生聚合键数量巨大；当 运行执行派生聚合；那么 系统 MUST 不抛出基数超限错误;内存压力由宿主系统层处理
    假如 派生聚合键数量巨大
    当 运行执行派生聚合
    那么 系统 MUST 不抛出基数超限错误;内存压力由宿主系统层处理
  @req:r637 @human
  场景: 仅使用编程方式配置
    - 必须成立：当 用户通过编程方式定义派生输出；那么 系统应无需修改 YAML DSL 即可运行
    当 用户通过编程方式定义派生输出
    那么 系统应无需修改 YAML DSL 即可运行
  @req:r683 @human
  场景: 内置可交换聚合在-adaptive-下可用
    - 必须成立：当 派生输出仅使用内置可交换/可结合的增量指标；那么 系统应允许派生聚合并确保结果确定性
    当 派生输出仅使用内置可交换/可结合的增量指标
    那么 系统应允许派生聚合并确保结果确定性

  @req:r683 @human
  场景: 自定义聚合器在-adaptive-下默认拒绝
    - 必须成立：当 派生输出使用自定义聚合器且未声明支持 `adaptive`；那么 系统应 fail-fast 并提示切换到 `parallel_mode="seq"`
    当 派生输出使用自定义聚合器且未声明支持 `adaptive`
    那么 系统应 fail-fast 并提示切换到 `parallel_mode="seq"`
  @req:r755 @human
  场景: count-distinct-统计-distinct-用户数
    - 必须成立：假如 详情流包含 `cs_id` 与 `user_id`；当 派生输出按 `cs_id` 分组并对 `user_id` 执行 `count_distinct`；那么 系统 MUST 输出每个 `cs_id` 的 distinct 用户数且结果确定性
    假如 详情流包含 `cs_id` 与 `user_id`
    当 派生输出按 `cs_id` 分组并对 `user_id` 执行 `count_distinct`
    那么 系统 MUST 输出每个 `cs_id` 的 distinct 用户数且结果确定性
  @req:r137 @human
  场景: 复合-key-的缺失值忽略
    - 必须成立：假如 distinct key 由多个字段组成；当 某行的任一字段为 `None`；那么 系统 MUST 忽略该行且不计入 distinct 计数
    假如 distinct key 由多个字段组成
    当 某行的任一字段为 `None`
    那么 系统 MUST 忽略该行且不计入 distinct 计数
  @req:r160 @human
  场景: dedup-by-types-不可导入
    - 必须成立：假如 用户尝试从 `scalim.execution.output_composition` 导入 DedupBySpec 或 DerivedDedupByGroupBySpec；当 执行 import；那么 系统 MUST 失败(ImportError/AttributeError),且公开导出 MUST NOT 包含这些类型
    假如 用户尝试从 `scalim.execution.output_composition` 导入 DedupBySpec 或 DerivedDedupByGroupBySpec
    当 执行 import
    那么 系统 MUST 失败(ImportError/AttributeError),且公开导出 MUST NOT 包含这些类型
  @req:r181 @human
  场景: adaptive-下自定义装配可拒绝
    - 必须成立：假如 自定义 `IDerivedAggregationSpec.validate_parallel_mode` 拒绝 `adaptive`；当 `parallel_mode="adaptive"` 且派生装配为该自定义实现；那么 系统 MUST fail-fast 并提示切换到 `parallel_mode="seq"` 或调整装配
    假如 自定义 `IDerivedAggregationSpec.validate_parallel_mode` 拒绝 `adaptive`
    当 `parallel_mode="adaptive"` 且派生装配为该自定义实现
    那么 系统 MUST fail-fast 并提示切换到 `parallel_mode="seq"` 或调整装配
  @req:r199 @human
  场景: two-stage-types-不可导入
    - 必须成立：假如 用户尝试从 `scalim.execution.output_composition` 导入 TwoStageGroupBySpec；当 执行 import；那么 系统 MUST 失败(ImportError/AttributeError),且公开导出 MUST NOT 包含该类型
    假如 用户尝试从 `scalim.execution.output_composition` 导入 TwoStageGroupBySpec
    当 执行 import
    那么 系统 MUST 失败(ImportError/AttributeError),且公开导出 MUST NOT 包含该类型
  @req:r230 @human
  场景: count-true-gte-阈值计数
    - 必须成立：假如 某行满足阈值条件；当 指标配置为 `count_true_gte`；那么 系统 MUST 对该行计数 +1
    假如 某行满足阈值条件
    当 指标配置为 `count_true_gte`
    那么 系统 MUST 对该行计数 +1

  @req:r242 @human
  场景: 聚合错误仍写审计
    - 必须成立：假如 派生聚合过程中发生非基数类错误；当 运行结束；那么 系统 MUST 在 audit 写入结构化错误行,且 meta 中 MUST 写入聚合指纹
    假如 派生聚合过程中发生非基数类错误
    当 运行结束
    那么 系统 MUST 在 audit 写入结构化错误行,且 meta 中 MUST 写入聚合指纹
  @req:r251 @human
  场景: parser-runtime-introspection-共享枚举
    - 必须成立：当 系统提供 SSOT 模块；那么 各层 MUST 共享同一份枚举集合,不得维护本地副本
    当 系统提供 SSOT 模块
    那么 各层 MUST 共享同一份枚举集合,不得维护本地副本

  @req:r251 @human
  场景: 默认配置一致性
    - 必须成立：假如 YAML primary output 包含 compute 字段且未显式指定输出字段；当 调用 introspection 加载输出配置；那么 返回的默认输出字段 MUST 与 runtime 默认一致
    假如 YAML primary output 包含 compute 字段且未显式指定输出字段
    当 调用 introspection 加载输出配置
    那么 返回的默认输出字段 MUST 与 runtime 默认一致

  @req:r251 @human
  场景: json-schema-editor-bundles-同步
    - 必须成立：当 系统生成 canonical JSON schema；那么 schema 中 producer keys 的可选集合 MUST 与 SSOT 一致
    当 系统生成 canonical JSON schema
    那么 schema 中 producer keys 的可选集合 MUST 与 SSOT 一致

  @req:r800 @human
  场景: 残留护栏字段被拒绝
    - 必须成立：假如 YAML 配置中残留 max_groups / max_distinct / distinct_on_overflow 任一字段；当 解析该配置；那么 系统 MUST fail-fast 报错并给出迁移提示(建议移除该字段)
    假如 YAML 配置中残留 max_groups / max_distinct / distinct_on_overflow 任一字段
    当 解析该配置
    那么 系统 MUST fail-fast 报错并给出迁移提示(建议移除该字段)

  @req:r800 @human
  场景: IR-构造不再接受护栏参数
    - 必须成立：假如 代码构造 DerivedGroupBySpec 时传入 max_groups/max_distinct/distinct_on_overflow；当 调用构造器；那么 系统 MUST 报 TypeError(参数不存在)
    假如 代码构造 DerivedGroupBySpec 时传入 max_groups/max_distinct/distinct_on_overflow
    当 调用构造器
    那么 系统 MUST 报 TypeError(参数不存在)

  @req:r802 @human
  场景: 残留 score_by_rank 字段被拒绝
    - 必须成立：假如 YAML outputs.<name>.aggregate.fields 中存在 score_by_rank producer key；当 解析该配置；那么 系统 MUST fail-fast 报错并给出迁移提示(建议替换为 compute 表达式)
    假如 YAML outputs.<name>.aggregate.fields 中存在 score_by_rank producer key
    当 解析该配置
    那么 系统 MUST fail-fast 报错并给出迁移提示(建议替换为 compute 表达式)

  @req:r802 @human
  场景: compute 表达式等价替代
    - 必须成立：假如 YAML 中用 compute 表达式替代 score_by_rank；当 运行派生输出；那么 系统 MUST 产生与原来 score_by_rank 相同的积分列输出
    假如 YAML 中用 compute 表达式替代 score_by_rank
    当 运行派生输出
    那么 系统 MUST 产生与原来 score_by_rank 相同的积分列输出

  @req:r802 @human
  场景: AGG_POST_PRODUCER_KEYS 不再包含 score_by_rank
    - 必须成立：当 读取 AGG_POST_PRODUCER_KEYS 枚举；那么 score_by_rank MUST NOT 出现在 post producer keys 中
    当 读取 AGG_POST_PRODUCER_KEYS 枚举
    那么 score_by_rank MUST NOT 出现在 post producer keys 中
