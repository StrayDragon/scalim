## Why

来自 cus_collect_infos 迁移实践反馈（基于 Scalim 0.3.2 实际使用；FR4/FR3）：在多 demand 项目里，经常需要跨多个 demand 复用同一段 sources/fields/aggregate 模板片段（例如 `customer_info` source 在 8 个 demand 中重复声明、d70 outputs 的 aggregate fields 大量重复）。

当前仓库的 `imports/$import` 已经解决了“跨文件复用”的主问题，但 V1 约束过严：仅允许同级文件名（禁止子目录路径）。这会迫使用户：

- 把大量 fragments 平铺在同一个目录（结构混乱）
- 或者继续复制粘贴（重复与 drift 风险高）

仓库现状（as implemented）：

- imports 机制规范：`openspec/specs/yaml-dsl-imports/spec.md`
- 实现入口：`src/scalim/dsl/by_yaml/config_parsing/imports.py`
- V1 明确限制：`imports.*` 仅允许同级文件（可选 `./`），不允许出现目录分隔符

本变更希望把 imports 从 V1 升级到 V2：在不放开“任意文件 include”的安全边界前提下，允许**相对路径的子目录 fragments**（例如 `./_shared/sources.yaml`），以更自然地组织可复用片段。

## What Changes

- 放宽 `imports.<alias>` 的路径规则（V2）：
  - 允许相对路径包含子目录（例如 `./_shared/sources.yaml`、`_shared/sources.yaml`）
  - 路径解析基准仍为 demand YAML 文件所在目录（保持确定性）
  - 仍拒绝以下路径（保持治理与安全边界）：
    - 绝对路径（含 Windows 盘符/UNC）
    - `..`（父目录逃逸）
    - `@`/`:` 等 alias/URI 语法
- 继续保持 imports 的关键契约：
  - import trace 可诊断（错误包含 fragment 文件路径与引用链路）
  - cycle detection（含最大展开深度上限）
  - `$import` 深度合并与类型一致性检查（mapping deep-merge；list replace；类型不匹配 fail-fast）
- Non-Goals：
  - 不引入新的“模块 root / workspace roots / 多根”推断机制（仍以 YAML 所在目录为 base）
  - 不允许从 fragments 目录外部读取文件（因此 v1/v2 都禁止 `..`）

## Capabilities

### New Capabilities
- （无）本变更为现有 imports 能力的 v2 升级，不引入新的顶层能力名。

### Modified Capabilities
- `yaml-dsl-imports`: 放宽 imports path 的合法范围（允许子目录 fragments），并在规范中明确 V2 的边界与拒绝规则。

## Impact

- 受影响代码：
  - `src/scalim/dsl/by_yaml/config_parsing/imports.py`（`_normalize_import_path` 及其错误信息/诊断）
  - CLI validate 路径（复用 imports expansion）：`src/scalim/cli/yaml_dsl.py`
- 兼容性：
  - 向后兼容：原先合法的同级 imports 继续合法；新增子目录 imports 使更多配置变为可表达
- 文档治理：
  - 规范 SSOT：`openspec/specs/yaml-dsl-imports/spec.md`
  - 若后续需要更新 docs/参考页，生成物走 `just gen-docs`（不手改 `.gen.`/AUTOGEN blocks）
