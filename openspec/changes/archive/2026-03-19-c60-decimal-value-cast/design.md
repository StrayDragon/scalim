## Context

该变更主要面向“精度敏感”用户（例如金融行业）：当数值以 `float` 形式进入 pipeline 时，二进制浮点会带来不可控的舍入误差；并且误差会在 `compute`/输出环节被放大，导致对账困难。

当前代码链路里已经存在两类相关能力：
- 源字段 `value_cast`：用于将 loader 返回值在写入上下文/输出前做类型归一化（此前仅支持 `auto/int/str`）。
- 派生字段 `compute`：通过 `SecureComputeEngine` 的 AST 沙箱 + 函数白名单执行表达式（此前无法直接构造 `Decimal(...)`）。

此外，可观测性中的 relations report 会把样本值写出为 JSON：当数据中出现 `Decimal`/`datetime` 等不可 JSON 序列化对象时，输出阶段可能崩溃，影响 QA 与线上诊断可用性。

说明：本 change 为“反推归档”。实现与测试已在工作区完成，本设计用于固化决策与文档/生成边界。

## Goals / Non-Goals

**Goals:**
- 为源字段提供显式 `Decimal` 写法：新增 `value_cast: decimal`。
- 在 `compute` 沙箱内允许 `Decimal("0.1")` 写法，减少 float 字面量引入的精度风险。
- 确保 relations report 的 JSON 输出对非 JSON 原生类型足够稳健（不因样本值类型导致崩溃）。
- 同步 schema 与文档，并明确 SSOT/生成物边界与生成入口，降低 drift 风险。

**Non-Goals:**
- 不在运行时“全局自动”将所有数值转为 `Decimal`；只在用户显式声明 `value_cast: decimal` 或在 `compute` 中显式构造 `Decimal(...)` 时生效。
- 不引入额外第三方精度库；使用 Python 标准库 `decimal`。
- 不改变 relations 的 `lookup_cast` 规则或其它既有数值归一化策略（本变更只增强字段值转换与 compute authoring surface）。

## Decisions

1. **`value_cast: decimal` 的落点与语义**
   - 落点：在 YAML DSL runtime 的 `value_cast` 注册表中新增 `decimal` 分支，保持与 `int/str/auto` 同一入口与错误归因路径。
   - 关键语义（与实现一致）：
     - `None` 透传为 `None`
     - `str` 先 `strip()`；strip 后为空视为缺失并返回 `None`
     - `float` 使用 `Decimal(str(value))`，避免 `Decimal(float)` 的二进制精确展开带来“意外小数”

2. **`compute` 沙箱允许 `Decimal` 构造器**
   - 在 `SecureComputeEngine` 的白名单函数中加入 `Decimal`。
   - 约束保持不变：依然禁止 method call/attribute call（例如 `x.quantize(...)`），复杂逻辑仍应迁移到 `call_by` 并受 allowlist 约束。

3. **relations report JSON 输出兜底**
   - 对 relations report 的 `json.dumps(...)` 使用 `default=str`，避免因 `Decimal`/`datetime`/tuple key 等导致输出崩溃。
   - 该兜底仅影响“诊断输出”，不改变 pipeline 的数据语义与计算结果。

4. **文档/生成边界与 drift gate**
   - Schema SSOT：`src/scalim/dsl/by_yaml/schema_dsl/`（手写元数据）。
   - Schema 生成物：`src/scalim/dsl/by_yaml/schema/demand.gen.json` 与前端编辑器 schema 镜像文件；生成入口 `scripts/gen-yaml-dsl-schema.py` / `just gen-yaml-dsl-schema`。
   - Docs SSOT：`docs/doc/yaml-dsl/user-guide.md`；docs 生成物（`.gen.`/injected blocks）统一通过 `just gen-docs` 刷新。
   - 验收口径：`just qa` 与 `just openspec-check`（包含 drift gate 与 OpenSpec 结构/脱敏校验）。

## Risks / Trade-offs

- [float→Decimal 仍可能丢失信息] 使用 `str(float)` 可以避免二进制展开的小数尾巴，但无法“恢复” float 已经丢掉的精度；推荐 loader 直接返回 `str`/`Decimal` 或让 upstream 在进入 pipeline 前完成归一化。
- [report 输出的类型信息弱化] `default=str` 会把未知类型序列化为字符串；这是诊断输出的折中选择，避免输出阶段崩溃比保留精确类型更重要。

