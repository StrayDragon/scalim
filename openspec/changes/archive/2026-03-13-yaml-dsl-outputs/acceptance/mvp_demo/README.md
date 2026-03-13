# 最小脱敏样例(可运行 + 可扩展)

目的:提供一个“无需 DB、可直接跑起来”的最小样本,用来对齐下列需求的语义边界(均为脱敏表达):

- 同一份明细分发多 sheet(where/predicate)
- 在同一次运行中派生汇总 sheet(group_by + metrics)
- set 口径派生聚合:`count_distinct` / `dedup_by` / `two_stage`
- normalize 常见形状:list -> map、嵌套 dict 拍平、take_first 等

## 1) baseline(当前就能跑)

该 baseline 验证“事实流 + lookup + 多 outputs(workbook 多 sheet) + 派生汇总 + meta/audit”的最小闭环.

```bash
uv run python openspec/changes/archive/2026-03-13-yaml-dsl-outputs/acceptance/mvp_demo/run_demo.py
# 或(不依赖安装环境):
PYTHONPATH=src python openspec/changes/archive/2026-03-13-yaml-dsl-outputs/acceptance/mvp_demo/run_demo.py
```

它会写出:`/tmp/scalim_mvp_demo.xlsx`

- Sheet:
  - `direct` / `partner`: 明细分发(where)
  - `by_cs`: 派生汇总(aggregate)
  - `__meta__` / `__audit__`: 对拍友好产物(meta/audit)
- 行数据来自 `loaders.py` 的内存数据
- `demo_detail.demand.yaml` 负责主事实流 + `preload_forever` 小表 lookup + `outputs` 编排

## 2) 典型“多 sheet + 派生汇总”的脱敏需求表达

### 2.1 Sheet 列表与过滤条件(示例)

- `订单明细`
  - from: `detail`(支付订单宽表)
  - fields: `order_id,user_id,cs_id,cs_name,group_name,institution_name,channel,pay_datetime,amount_yuan,is_quick_pay`
- `直客明细`
  - where: `channel == "direct"`
  - fields: 同 `订单明细`
- `渠道明细`
  - where: `channel == "partner"`
  - fields: 同 `订单明细`
- `客服汇总`
  - from: `detail`
  - group_by: `cs_id,cs_name,group_name`
  - metrics: `order_cnt,sum_amount,new_paid_users,repeat_paid_users`

### 2.2 期望的 YAML authoring surface(示意)

这部分是“目标形态”,用于需求评审(当前版本可能还不能直接写).

```yaml
outputs:
  - name: detail
    container:
      type: workbook
      path: demo_report.xlsx
      sheet: 订单明细
    fields: [order_id, user_id, cs_id, cs_name, group_name, channel, pay_datetime, amount_yuan, is_quick_pay]

  - name: direct_detail
    from: detail
    where: "channel == 'direct'"
    container:
      type: workbook
      path: demo_report.xlsx
      sheet: 直客明细

  - name: by_cs
    from: detail
    aggregate:
      group_by: [cs_id, cs_name, group_name]
      metrics:
        order_cnt: {op: count, field: order_id}
        sum_amount: {op: sum, field: amount_yuan}
        new_paid_users: {op: count_distinct, field: user_id}
        repeat_paid_users:
          op: two_stage
          stage1:
            group_by: [user_id]
            metrics:
              pay_order_cnt: {op: count, field: order_id}
              cs_id: {op: first, field: cs_id}
          stage2:
            group_by: [cs_id]
            metrics:
              repeat_paid_users: {op: count_true, expr: "pay_order_cnt >= 2"}
    container:
      type: workbook
      path: demo_report.xlsx
      sheet: 客服汇总
```

## 3) set 口径聚合(distinct/dedup/two-stage)最小样例

### 3.1 `count_distinct`

需求:按客服统计“支付用户数”(distinct user_id).

- group: `cs_id`
- distinct key: `user_id`
- 期望:提供 `max_distinct` 护栏与稳定审计指纹(否则很难对拍定位偏差)

### 3.2 `dedup_by`

需求:同一个 `user_id` 在同一个客服下出现多行时,只保留 1 行作为“用户实体行”.

- dedup key: `(cs_id, user_id)`
- 冲突策略(MVP 推荐):`first|last|error`
  - 为可对拍与确定性,建议先不支持“任意 python 比较函数”

### 3.3 `two_stage`

需求:`repeat_paid_users`(复购支付用户):

- stage1(用户实体):`group_by = user_id`,统计 `pay_order_cnt`
- stage2(客服汇总):`group_by = cs_id`,统计 `count_true(pay_order_cnt>=2)`

## 4) normalize 的“非理想形状”样例(脱敏)

这些 loader 输出形状在业务报表里非常常见,业务方现在不得不写 Python wrapper.

### 4.1 list -> keyed map(取 first)

```python
[
  {"order_id": 10001, "recommend_cs_id": 9002},
  {"order_id": 10001, "recommend_cs_id": 9002},  # duplicate
  {"order_id": 10003, "recommend_cs_id": 9001},
]
```

期望 normalize 后(key = order_id, on_conflict=first):

```python
{
  10001: {"order_id": 10001, "recommend_cs_id": 9002},
  10003: {"order_id": 10003, "recommend_cs_id": 9001},
}
```

### 4.2 嵌套 dict 拍平(role key 为 int)

```python
{
  10001: {
    1: {"clearn_reason_level": 2},
    2: {"clearn_reason_level": 1},
    "review_status": 3,
  }
}
```

期望 normalize 后:

```python
{
  10001: {
    "order_id": 10001,
    "customer_level": 2,
    "operation_level": 1,
    "review_status": 3,
  }
}
```

关键点:role key 是 int(而不是字符串),仅靠 `a.b.c` 点路径无法表达;需要 normalize 支持“map key 为任意标量”的 path 语法,或提供受控 `normalize.call_by`.
