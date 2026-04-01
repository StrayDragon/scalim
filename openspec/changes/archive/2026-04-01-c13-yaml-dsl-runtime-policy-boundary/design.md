## Context

相比 `observability`,`guardrails` / `retry` 更容易被用户误认为“业务建模的一部分”,但它们依然体现明显的 runtime policy 特征:

- 是否启用重试,取决于数据源稳定性与运行环境
- `batch_size` 明显取决于性能与内存预算
- `guardrails` 的成本和严格度常常因环境而异
- `failure_policy` 在 demand/workflow 两层的语义也并不完全相同

因此这组配置不能简单按“都迁出去”一句话带过,需要一个独立提案讨论边界与分组。

## Goals

- 明确哪些字段应被视为 runtime policy
- 给 `guardrails` 的环境/性能语义留出明确决策空间
- 避免在主线 YAML 收敛中夹带过多未定策略

## Non-Goals

- 不定义全部 runtime options 的最终 dataclass 细节
- 不处理 observability

## Final Direction

### 1. `guardrails` 完全迁出 YAML

当前结论已明确:

- `guardrails.*` 迁出 YAML
- 不保留 profile/preset 引用壳

理由是:

- 它更像开发/验证阶段的工程化策略
- 线上与开发环境往往有不同开关需求
- 放在 Python 入口更符合“临时启用、按环境切换、按变量关闭”的真实使用方式

### 2. 对性能有明显影响的 guardrails,明确要求由运行入口按环境开启

当前结论已明确:

- 这类 guardrails 不应由 YAML 声明
- 应由 Python / 运行入口按环境显式开启或关闭

这也是本提案对 runtime policy 的总口径:

- 受环境、算力预算、性能损耗显著影响的开关,不再继续留在 authoring YAML 中

### 3. workflow `diagnostics/staging/wait` 类入口继续放在本 change 内统一讨论

当前结论是,这些入口继续留在本 change 统一裁决,不再额外拆分:

- 它们和 `guardrails` / `retry` / `batch_size` 一样,都属于 runtime policy boundary
- 若再拆,反而会把“哪些环境敏感项应迁出 YAML”这个主题再次切碎

本提案继续覆盖:

- workflow `options.resources_wait.*`
- workflow `output_staging.*`

### 4. 这些 runtime policy 的最终归属面

在本提案中,最终目标状态确定为:

- demand `guardrails` 迁出 YAML
- demand `retry` 迁出 YAML
- demand `batch_size` 迁出 YAML
- demand `failure_policy` 迁出 YAML
- workflow `options.resources_wait.*` 迁出 YAML
- workflow `output_staging.*` 迁出 YAML
- workflow `failure_policy` 保留在 workflow YAML 中,作为稳定的 orchestration knob

这里保留 workflow `failure_policy` 的原因是:

- 它表达的是 workflow DAG 在节点失败时如何继续或终止
- 它直接影响编排语义,而不只是运行环境策略
- 相比 `guardrails/retry/staging/wait`,它更接近 workflow authoring 本体

### 5. 本提案当前覆盖的 runtime-policy 候选集合

为了避免后续边界再次发散,本提案当前明确接住的主题包括:

- `guardrails.*`
- `retry.*`
- `batch_size`
- demand / workflow `failure_policy`
- workflow `options.resources_wait.*`
- workflow `output_staging.*`


## Dependencies

- demand imports scope 应依赖这个 change 的结论,因为 imports 的允许范围取决于哪些区域还留在 YAML 中
