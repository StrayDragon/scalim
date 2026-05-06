## Context

在 `v0.9.9`（`v0.9.8..v0.9.9`）区间引入的 `d78f9d2f`（`refactor: policy-normalization-breaking-cleanup`）将多组 policy-like 值从 `StrEnum` 迁移到了 `Literal[str] + normalize_* -> builtin str`，并在入口强制 `type(x) is str`，以满足 “state/pickle 边界只存 builtin 类型” 的约束。

当前问题集中在两点：
1. 用户侧更偏好 Enum（强约束、IDE 体验、可扩展语义），而 Literal/字符串字面量更像 wire/config 形态。
2. 现状容易出现 “Enum + Literal 双定义” 的维护负担（非 DRY），并且让 API 使用口径变得模糊。

该变更希望保持原有“边界稳定”诉求：对外以 Enum/`StrEnum` 作为 SSOT 与 authoring surface，但运行期内部优先保留 canonical builtin `str`（最小热路径扰动）。

约束：
- `src/scalim/` 运行时必须兼容 Python 3.6。
- state/pickle/JSON/YAML 等边界输出必须是稳定的 builtin `str`。
- policy 值集合为封闭集合，解析需 fail-fast，错误信息必须列出允许值。

## Goals / Non-Goals

**Goals:**
- policy public surface 以 Enum 为主（推荐写法为 `XPolicy.FOO`）。
- 每组 policy 只维护一次 SSOT 定义（Enum），允许值集合/错误信息/边界字符串从 Enum 派生（DRY）。
- 统一 state/serialization 边界：输出 builtin `str`；配置/反序列化入口接受 builtin `str` 并经 Enum SSOT 校验与归一化（必要时映射到 Enum 后再落地为 canonical `str`）。

**Non-Goals:**
- 不在本变更中把仓库内所有 Enum/Literal 全部重做一遍；只覆盖 policy-like 且跨边界流动的值集合（含 `FailurePolicy` 这类已出现双定义的热点）。
- 不改变任何 policy 语义（仅改变表达方式与边界编码/解码策略）。

## Decisions

1. **单一 SSOT：Enum（`StrEnum`）**
   - 每组 policy 定义一个 `StrEnum` 作为唯一 SSOT（值为 builtin `str`）。
   - 不再手工维护 `...Value = Literal[...]` 这类“第二份允许值集合”；所有允许值列表/label/诊断信息均从 Enum 派生，确保顺序稳定（DRY）。

2. **边界分层（严进宽出）**
   - **公开 API 输入（严进）**：构造器/Options 等对外入口严格只接受 Enum；若传入字符串字面量，直接 fail-fast。
   - **配置/反序列化输入（宽进）**：YAML/JSON/state/pickle 等边界允许 builtin `str`，并通过 parse SSOT 恢复为 Enum。
   - **输出（宽出但稳定）**：任何 state/wire 表示统一输出稳定 builtin `str`（来自 `Enum.value`），禁止输出 Enum 实例或 `str` 子类。

3. **内部表示：优先 builtin `str`（最小热路径扰动）**
   - 运行时内部字段/热路径优先存储与比较 builtin `str`（policy value），避免把 Enum 对象引入热路径与大面积改写比较分支。
   - Enum/`StrEnum` 作为 SSOT 与 public surface：对外接收 Enum，一次性落到 `.value`；对内允许的字符串集合、错误信息 label 均从 Enum 派生，保证 DRY。

4. **统一 parse/format 辅助函数（SSOT 复用）**
   - 为每组 policy 提供 `parse_<policy>(...) -> <Enum>` 与 `format_<policy>(...) -> str`（或等价命名），并要求所有入口/派生复用。
   - parse 只接受 builtin `str`（拒绝 `str` 子类），并支持大小写/连字符归一化；format 保证输出 builtin `str`。
   - 对外入口不再直接暴露 `normalize_*` 的 “字符串收敛” 语义；统一通过 parse/format 管理跨边界映射。

5. **覆盖范围（优先级）**
   - P0：`LoaderResultPolicy`、`ObserverManagerMode`、`CaptureOverflowPolicy`（涉及 hooks/ob manager/state）
   - P0：`FailurePolicy`（清理 Enum/Literal 双定义，统一到 Enum-only）

## Risks / Trade-offs

- [风险] **BREAKING**：用户代码若当前传入字符串字面量会报错。
  - 缓解：仅在配置/反序列化入口接受字符串；更新 docs 与错误信息，提供明确迁移指引（`"foo"` → `XPolicy.FOO`）。

- [风险] 解析/序列化逻辑散落导致 drift。
  - 缓解：集中到 parse/format SSOT，并增加针对 pickle/state roundtrip 的回归测试。

- [权衡] 公开 API 强制 Enum 会增加配置入口的映射成本（字符串 → Enum → canonical `str`）。
  - 缓解：该映射发生在边界/构造期；热路径仍按 builtin `str` 比较，不引入额外 per-event 负担。

## Migration Plan

1. 为 P0 policy 增加 Enum（`StrEnum`）+ parse/format SSOT（不引入 Literal）。
2. 修改 hooks/ob 的 public 构造入口：只接受 Enum，并一次性落地为 canonical builtin `str`。
3. 修改 hooks/ob 的 manager/state：`__getstate__`/wire 输出只包含 builtin `str`；`__setstate__`/反序列化输入对 builtin `str` 进行 Enum SSOT 校验并归一化。
4. 修改 YAML DSL / CLI 配置入口：将 policy 字符串映射/校验到 Enum SSOT，并落地为 canonical builtin `str`。
5. 更新测试：
   - policy parse/format 覆盖
   - pickle/state roundtrip 覆盖
   - 错误信息包含允许值列表（来自 Enum）
6. 更新示例与升级说明（release notes / docs）。

## Open Questions

- 是否需要为所有 policy 提供统一的“归一化规则配置”（例如是否允许空串走默认）？本变更默认沿用既有行为，必要时再做扩展。
