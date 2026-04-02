## Context

仓库内 notebooks 目录包含一套真实演进的 YAML DSL 示例与工作流示例，其价值在于：

- 覆盖 imports/跨目录引用、真实字段组合与常见 Python 引用形态（含 `call_by(ref(args...))`）
- 能作为 editor/LSP shared core 的“静态回归输入”，在不执行用户代码的前提下提升稳定性

现状问题是：如果回归只针对合成 YAML，很容易在“目录结构 + imports allowed roots + call_by 参数形态”等方面发生回归而不自知。

## Goals / Non-Goals

**Goals:**

- 新增 pytest 回归套件，复用 notebooks fixtures 作为输入：
  - 对每个“完整 YAML”执行 diagnostics，要求无 errors
  - 对 YAML 中的 Python 引用执行 definition/hover/completion 的无崩溃回归（允许空结果）
- 引入最小 `scalim.yaml` 以固定 imports allowed roots，避免 fixtures 因默认 allowed roots 过窄而误报
- 测试必须是静态的（不得执行用户代码、不得 shell-out CLI）

**Non-Goals:**

- 不要求所有 Python 引用都能解析到 locations（fixtures 可能引用未安装的依赖或仅示例用途）
- 不将 notebooks fixtures 变成新的“运行时 SSOT”（仅作为测试输入）

## Decisions

1) **fixtures 发现策略：只回归“完整 YAML”，跳过 fragments**

notebooks fixtures 中存在 `_shared/**` 与 `*_fragments.yaml` 这类“被 imports 引用的片段文件”，它们不满足完整 demand/workflow schema。
回归套件将：

- 发现 `*.yaml/*.yml`
- 排除：
  - `.tmp/**`
  - `scalim.yaml`
  - `_shared/**`
  - `*_fragments.yaml`

2) **通过 fixtures 根目录 `scalim.yaml` 固化 allowed roots**

默认 allowed roots 为入口 YAML 的所在目录，会导致 `support/` 下 YAML imports `../_shared/...` 时触发“越界”错误。
因此在 fixtures 根目录新增最小 `scalim.yaml`：

```yaml
yaml_dsl:
  import_allowed_roots:
    - .
```

这使得 fixtures 内部跨子目录 imports 在不修改示例 YAML 的情况下稳定通过。

3) **Python 引用回归由 pytest 显式注入 python_roots**

当前 `scalim.yaml` 中的 roots 解析约束要求路径不越界 `project_root`，因此不强依赖在 fixtures 内配置 `python_roots`。
pytest 侧将显式提供常用 python_roots（例如 `src/`、`packages/scalim-misc/src`）用于静态解析回归。

4) **不引入 allowlist：保持“发现 + 排除”**

- 回归套件保持“自动发现 `*.yaml/*.yml` + 排除 fragments/产物/配置文件”的策略
- 若未来出现“刻意用于演示错误”的 YAML，优先通过命名/目录约定（例如 `_invalid/**` 或 `*_invalid.yaml`）并加入排除规则，而不是引入全量 allowlist（降低维护成本与漏测风险）

## Risks / Trade-offs

- [fixtures 目录结构变化导致回归失效] → 以“目录发现 + 排除规则”实现，避免硬编码单文件列表
- [新增 scalim.yaml 被误当成 DSL YAML 参与回归] → 明确在发现规则中排除 `scalim.yaml`
- [解析失败导致 flaky] → 回归仅约束“不崩溃 + 输出可诊断 warnings”，避免对解析成功率做过强假设

## Migration Plan

- 新增测试与 fixtures 根 `scalim.yaml` 不改变运行时语义，无迁移步骤。

## Open Questions

（无；维持 “目录发现 + 排除规则” 的策略，不引入 allowlist）
