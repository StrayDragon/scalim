## ADDED Requirements

### Requirement: ranked group-by supports `row_number` / `rank` / `dense_rank`
系统 MUST 在派生聚合(group_by)的 finalize 排名能力中支持三种 rank 语义:
- `row_number`: 连续序号(1..N),不合并并列
- `rank`: SQL rank 语义(1,1,3...)：并列共享名次,下一个名次跳号
- `dense_rank`: SQL dense_rank 语义(1,1,2...)：并列共享名次,下一个名次不跳号

#### Scenario: dense_rank 同值同名次
- **GIVEN** 某 partition 内按降序排序后的 `by` 值为 `[10, 10, 8]`
- **WHEN** rank_kind 为 `dense_rank`
- **THEN** 系统 MUST 输出 rank 值为 `[1, 1, 2]`

#### Scenario: rank 跳号
- **GIVEN** 某 partition 内按降序排序后的 `by` 值为 `[10, 10, 8]`
- **WHEN** rank_kind 为 `rank`
- **THEN** 系统 MUST 输出 rank 值为 `[1, 1, 3]`

### Requirement: partitioned ranking resets rank per partition
系统 MUST 支持按 `partition_by` 对聚合输出行进行分区并在分区内重置排名.

#### Scenario: partition_by 重置
- **GIVEN** 聚合输出包含两个分区,每个分区各两行
- **WHEN** 用户配置 `partition_by=[group_id]`
- **THEN** 系统 MUST 在每个分区内分别从 1 开始计算 rank

### Requirement: top-k supports `rank`-based tie expansion and `rows` fixed-size mode
系统 MUST 定义 top-k 的两种模式:
- `top_k_mode=rank`(默认): 每个分区保留 `rank_value <= K`(含并列扩张)
- `top_k_mode=rows`: 每个分区强行保留前 K 行(允许截断并列),并要求提供稳定排序键以保证确定性

#### Scenario: top_k_mode=rank 含并列扩张
- **GIVEN** 某分区内 `by` 值为 `[10, 10, 8]`
- **WHEN** `top_k=1` 且 `top_k_mode=rank`
- **THEN** 系统 MUST 保留两条并列行

#### Scenario: top_k_mode=rows 强行取 K 行
- **GIVEN** 某分区内 `by` 值为 `[10, 10, 8]`
- **WHEN** `top_k=1` 且 `top_k_mode=rows`
- **THEN** 系统 MUST 仅保留 1 行(允许截断并列)

