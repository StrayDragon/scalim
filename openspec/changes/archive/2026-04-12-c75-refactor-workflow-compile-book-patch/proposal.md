## Meta

- Type: `refactor-0`
- Topic: workflow `resources.books` 的 patch/overlay 逻辑抽象化（减少手写合并、统一校验与错误口径）
- Related code:
  - `src/scalim/dsl/yaml_dsl/workflow_compile.py:203`（`_overlay_book_write_defaults_patch`，C901）
  - `src/scalim/dsl/yaml_dsl/workflow_compile.py:300`（`_apply_book_patch`，C901）
  - 调用点：
    - `src/scalim/dsl/yaml_dsl/workflow_compile.py:422`（overlay write_defaults）
    - `src/scalim/dsl/yaml_dsl/workflow_compile.py:800`（apply book patch）

## 背景

workflow YAML 支持对 `resources.books.<book_id>` 做 patch/override（例如 `write_defaults`、`budget`、`export_xlsx`、`allow_formulas`、`write_lock` 等）。这类配置的特点是：

- 对用户而言是“结构化配置”；
- 对实现而言是“动态 dict patch 合并 + 强校验 + 友好错误路径”。

目前该逻辑在 `workflow_compile.py` 中以手写方式实现，造成：

- 函数体量大（C901），控制流复杂；
- 同一类错误处理（unknown key、类型不匹配、path 拼接）重复；
- 未来新增字段/改字段容易漏改（allowed_keys/默认值/路径/错误提示多处同步）。

从可维护性角度，这类 patch 合并非常适合抽象为“通用 helper + 少量字段定义”，让新增字段成为“声明式增量”。

## 例子（当前实现复杂度来源）

`_apply_book_patch` 做了很多事情：

- unknown keys 检测（allowed_keys 差集）；
- 对每个 key 做类型判断与转换；
- budget/export_xlsx 等嵌套 mapping 的深层校验；
- write_defaults 还要调用 `_overlay_book_write_defaults_patch` 再做枚举校验；
- path 错误信息要拼接到准确位置（`overrides.resources.books.<id>...`）。

这些都是“配置 patch 领域”的通用能力，但目前散落为手写 if/else。

## 目标

- 抽离通用 patch apply 能力：
  - unknown key 检测
  - 类型收窄（mapping/list/str/bool/int）
  - path 组合与错误消息一致性
- 让新增字段变得更便宜（改 1 处，不改 5 处）；
- 不改变行为（同一输入应生成同一 IR / 同样错误口径）；
- Python 3.6 兼容。

## 方案候选

### 方案 A：在 `workflow_compile.py` 内部引入通用 helper（最小改动）

做法：

- 新增几个小 helper（同文件或 `_internal` 子模块）：
  - `assert_no_unknown_keys(patch, allowed_keys, path)`
  - `as_opt_mapping(value, path)` / `as_opt_bool` / `as_opt_str` ...
  - `overlay_dataclass(base, patch, field_specs, path)`（field_specs 可是轻量的 tuple 定义）
- 保持现有数据模型不变（仍返回 `BookConfig` / `BookWriteDefaultsConfig`）。

优点：

- 改动范围小，回归风险最低；
- 先收敛重复逻辑，再考虑模块拆分。

缺点：

- helper 仍在 compile 模块内，复用范围有限（但足够解决当前问题）。

### 方案 B：抽到 `dsl/yaml_dsl/_internal/patch_apply.py`（长远更好）

做法：

- 将 patch apply helper 提供为内部公共模块；
- workflow_compile 与其他 runtime patch（如 overrides.outputs）都复用。

优点：

- 从机制上避免“每个地方都手写 patch merge”；
- 形成 SSOT。

缺点：

- 初期需要确定模块分层，避免 import 边界冲突；
- 需要更全面的测试以确保多个调用点不漂移。

## 推荐方案

推荐直接落地 **方案 B**（抽到 `dsl/yaml_dsl/_internal/patch_apply.py`），在保持行为不变的前提下：

- 降低 C901 复杂度；
- 统一错误口径；
- 形成 YAML DSL 域内的 SSOT（避免未来同类 patch/override 再复制实现）。

## 优劣分析与性价比

- 成本：中（需要重构核心配置解析逻辑，但可以渐进拆分）。
- 收益：高（减少漂移、降低新增字段成本、提升可读性与可测试性）。
- 风险：中（错误路径/默认值/边界行为易回归；必须对拍测试）。

## 验证建议

- 增加“输入 YAML → compile → IR”的对拍用例（可用 fixtures）：
  - unknown key 报错路径一致；
  - write_defaults 的枚举校验一致；
  - budget/export_xlsx 嵌套字段的错误口径一致。
- 跑 `just quick-qa-only-py` 与最小 workflow compile/validate 测试集。
