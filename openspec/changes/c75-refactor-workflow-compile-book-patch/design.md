## Context

workflow YAML 支持对 `workflow.resources.books.<book_id>` 做 patch/overlay（例如 `write_defaults`、`budget`、`export_xlsx`、`allow_formulas`、`write_lock` 等）。这类配置对用户是结构化 mapping，但对实现而言往往演化为：

- 动态 dict patch 合并
- 深层字段校验（类型/枚举/必填）
- unknown key 检测
- 精确 path 拼接与一致的错误消息

当前 `workflow_compile.py` 中存在手写的 overlay/apply 逻辑（并伴随 C901 放行），导致：

- 控制流复杂、review 成本高；
- 同类“unknown key/类型不匹配/path 拼接”的处理重复；
- 新增字段需要在多个 if/else 中同步，容易漏改与语义漂移；
- 测试只能偏集成，难以对规则分支做小单测覆盖。

该问题属于“配置 patch 领域”的通用能力，适合先在 compile 模块内抽象出通用 helper，再逐步推广到其它 overrides 路径。

## Goals / Non-Goals

**Goals:**

- 抽离通用 patch apply 能力（unknown keys、类型窄化、path 组合、错误口径）
- 降低 `_apply_book_patch` / `_overlay_book_write_defaults_patch` 的复杂度（减少 C901 风险）
- 保持行为不变：同一输入生成同一 IR / 同样的错误结论（必要时保持关键错误字段一致）
- Python 3.6 兼容

**Non-Goals:**

- 不引入“全仓通用 patch 框架”（本次只治理 YAML DSL books patch/overlay 的实现结构）
- 不改变 books/outputs 的对外 authoring surface 与语义（只做实现结构治理）

## Decisions

### 1) Phase 0 直接抽到 `dsl/yaml_dsl/_internal` 作为 SSOT（方案 B）

Phase 0 直接将通用 patch apply helper 抽离到：

- `src/scalim/dsl/yaml_dsl/_internal/patch_apply.py`

并在该模块中提供：

- `assert_no_unknown_keys(patch, allowed_keys, path)`：统一 unknown key 诊断
- `as_opt_mapping/as_opt_bool/as_opt_str/as_opt_int`：统一类型窄化与错误口径
- （可选）`overlay_dataclass(...)` 或 “field specs + 小函数组合” 的轻量抽象，用于把嵌套 mapping 的 apply 变成声明式增量

优先目标是：

- 规则分支可命名、可单测
- 主函数仅保留“按字段调用 helper”的薄逻辑

### 2) 以对拍测试守护“行为不变”

由于该逻辑属于配置入口核心路径，回归风险主要来自：

- path 拼接变化导致定位回归；
- 默认值/枚举校验漂移；
- unknown key 检测范围变化。

Phase 0 将补充/整理回归用例：

- unknown key 报错路径一致（含嵌套字段）
- write_defaults 的枚举校验一致
- budget/export_xlsx 等嵌套 mapping 的错误口径一致

为下一步抽成公共模块（方案 B）提供稳定基线。

## Risks / Trade-offs

- **错误文案/路径回归**：哪怕行为结论一致，诊断文本变化也可能影响 CLI/LSP 快照；通过对拍测试锁定关键字段并谨慎调整文案。
- **抽象过度**：过早引入复杂的通用 patch 框架会增加心智负担；Phase 0 选择最小 helper + 轻量 field specs。

## Migration Plan

- Phase 0：引入 `_internal/patch_apply.py` SSOT helper + 重构两处 hotspot 函数 + 回归用例对拍
- Phase 1（可选）：将该 helper 推广到其它 overrides（例如 outputs overrides），形成 YAML DSL 域内的 SSOT

## Open Questions

- 无。
