# 2026-03-13: yaml-dsl-outputs

## 变更摘要

本批次将执行层既有能力(`output-composition` / `derived-outputs`)暴露为 YAML authoring surface:

- demand YAML 顶层新增 `outputs`(有序列表): 支持同一次运行写入同一 workbook 的多 sheet
- `outputs.*.where`: 安全表达式分发过滤(编译期静态分析依赖字段并注入 required fields)
- `outputs.*.aggregate`: 派生汇总输出(同一次运行内产出汇总 sheet)
- 顶层 `meta` / `audit`: 一键开启对拍友好产物
- 顶层 `failure_policy` / `include_full_error_message`: 对齐 composed outputs 失败策略与错误信息脱敏

OpenSpec 归档变更（含 proposal/design/spec/tasks）:
- `openspec/changes/archive/2026-03-13-yaml-dsl-outputs/`

对应主规范(节选):
- `openspec/specs/yaml-dsl-schema/spec.md`
- `openspec/specs/output-composition/spec.md`
- `openspec/specs/derived-outputs/spec.md`

下游同步盘点:
- 仅用于盘点与行动: `.tmp/known-outer-paths-using-this-package.txt`（请勿在公开输出中复述其内容）

## BREAKING: 顶层 `output:` 已移除

- 旧写法顶层 `output:` 已不再支持(会 fail-fast)
- 新写法使用顶层 `outputs:`(list)
  - 单输出: `outputs` 仅包含 1 个元素
  - 多输出: 用 `where` 分发到不同 sheet,用 `aggregate` 声明派生汇总

## 新语法要点

- `outputs` 是 **有序列表**: 顺序决定 primary 输出,并影响默认写入顺序
- `outputs.*.container`:
  - `type: workbook` → Excel 工作簿输出(支持 `sheet`,建议多目标共享 workbook 时开启 `write_lock: true`)
  - `type: csv` → CSV 文件输出
- 明细输出:
  - 使用 `fields: [field_id, ...]` 指定列顺序
- 派生汇总输出:
  - 使用 `aggregate`(与 `fields` 互斥)
- `where`:
  - 仅支持安全表达式(禁止任意 import)
  - 编译期静态提取依赖字段并注入 required fields;依赖字段缺失会 fail-fast
- `from`:
  - 可复用另一个 output 的字段集合与容器配置(未声明则继承; `where/aggregate` 不继承)
- `field_id` 必须全局唯一(不再支持用 `source.field_id` 在输出层做消歧)

## 最小迁移示例

旧写法:

```yaml
output:
  format: csv
  path: ./output/report.csv
  fields:
    - order_id
    - customer_name
```

新写法:

```yaml
outputs:
  - name: detail
    container: {type: csv, path: ./output/report.csv}
    fields: [order_id, customer_name]
```

## Migration Checklist

1) 将所有顶层 `output:` 升级为 `outputs:`(list)
2) 将旧 `output.*` 的输出策略迁移到 `outputs.*.container.*`
3) 将旧 `output.fields` 重写为 `outputs.*.fields: [field_id, ...]`
4) 若存在重复 `field_id`,先在 YAML 中重命名(必要时用 `extract` 指向真实 data_key)
5) 多 sheet 分发:
   - 增加多个 outputs
   - 用 `where` 表达式区分
   - 共享 workbook 时为每个 output 显式设置 `container.sheet` 并建议开启 `write_lock: true`
6) 需要汇总 sheet 时,新增一个带 `aggregate` 的 output
7) (可选) 启用 `meta: true` / `audit: true` 以输出对拍信息
