## Why

金融/支付/清结算等场景对数值精度非常敏感；`float` 的二进制表示会引入不可控的舍入误差（例如 `0.1 + 0.2 != 0.3`），一旦进入 `compute` 或输出链路，误差会被放大且难以审计。

目前 YAML DSL 已支持源字段 `value_cast`（`auto/int/str`）与派生字段 `compute/call_by`，但缺少“显式 Decimal”写法：
- 源字段无法声明 `value_cast: decimal` 来把 loader 返回值稳定转换为 `decimal.Decimal`
- `compute` 沙箱不允许 `Decimal(...)`，用户只能写 float 字面量或把逻辑迁移到 `call_by`
- 可观测性/报表 JSON 输出在遇到 `Decimal` 等非 JSON 原生类型时可能崩溃，影响 QA 与线上诊断

本变更以“反推”的方式补齐规范/提案：实现与测试已完成，OpenSpec 用于固化行为边界并归档。

## What Changes

- 新增源字段 `value_cast: decimal`：
  - 将字段值转换为 `decimal.Decimal`
  - 对 `None` 透传；对空白字符串（strip 后为空）视为缺失并返回 `None`
  - 对 `float` 采用 `Decimal(str(value))` 以避免 `Decimal(float)` 的二进制精确展开带来的“意外小数”
- `compute` 安全沙箱新增 `Decimal` 构造器白名单：允许在表达式中写 `Decimal("0.1")`，以显式避免 float 精度问题
- 关系可观测性 JSON 报告输出更稳健：对 `Decimal`/`datetime` 等不可 JSON 序列化对象使用 `str(...)` 兜底，避免输出阶段崩溃
- 同步 YAML DSL schema 与文档示例，并更新生成物

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `field-compute`: `value_cast` 增加 `decimal` 选项；`compute` 沙箱新增 `Decimal` 构造器白名单。
- `yaml-dsl-schema`: `value_cast` 枚举增加 `decimal`，schema hover/示例同步更新并重新生成 schema 输出。

## Impact

- 受影响代码（SSOT）：
  - `src/scalim/dsl/by_yaml/runtime/_internal/conversion_lookup.py`（`value_cast` 注册表与 `decimal` 转换）
  - `src/scalim/dsl/by_yaml/config_parsing/security.py`（`SecureComputeEngine` safe functions）
  - `src/scalim/ob/presets/relations.py`（relations report JSON 输出稳健性）
- 受影响 schema（SSOT/生成物）：
  - SSOT：`src/scalim/dsl/by_yaml/schema_dsl/constants.py`、`src/scalim/dsl/by_yaml/schema_dsl/models/field.py`
  - 生成物：`src/scalim/dsl/by_yaml/schema/demand.gen.json`（以及前端编辑器内的 schema 镜像文件）
  - 生成入口：`scripts/gen-yaml-dsl-schema.py` / `just gen-yaml-dsl-schema`
- 受影响文档（SSOT/生成物）：
  - SSOT：`docs/doc/yaml-dsl/user-guide.md`
  - 生成物：`docs/doc/yaml-dsl/schema-reference.gen.md`（`.gen.` 文件禁止手改）
  - 生成入口：`just gen-docs`
- QA/验收建议：`just qa`（包含 lint/tests + drift gate + OpenSpec checks）

