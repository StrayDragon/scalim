## Context

仓库当前已经具备一套 public API 治理与示例回归的基础设施：

- Tier1 curated entrypoints（SSOT）：`src/scalim/**/__init__.py` 中的 `# pragma: scalim-public-api tier1:...`
- 符号级导出契约（SSOT）：各模块的字面量 `__all__`（由治理脚本与 docs 生成器 `AST` 扫描；不 `import`）
- 文档投影：`just gen-docs` 生成 `docs/doc/getting-started/public-api.gen.md`
- 示例回归（headless/CI）：`just examples`（`justfile` 内联 runner）
- public API 教学/回归套件：`notebooks/marimo/example_public_api_suite/` + `tests/public_api/`
- YAML DSL skill 已具备受控生成与 drift gate：`just gen-agent-skill` / `just validate-agent-skill`

但目前仍存在一个核心维护痛点：**Tier1 public surface ↔ 示例套件 ↔ pytest public_api suite ↔ skills 的“覆盖绑定”缺少确定性 gate**。
这会导致当维护者调整 public surface（新增/删除/迁移 Tier1 入口，或重构 YAML DSL/public facade）时：

- 示例套件可能在局部仍能通过，但缺失某些入口的用法覆盖；
- pytest `tests/public_api/` 可能只覆盖部分章节，但缺少一个 fail-fast 机制指出“覆盖集合漂移”；
- skills 侧缺少一个可复用、可生成、可验证的 public API 指南与可运行样例索引，接手者需要反复翻仓库才能拼出正确用法。

本变更在不引入“符号级硬 manifest SSOT”的前提下，把上述投影串为一条确定性机制。

## Goals / Non-Goals

**Goals:**
- 以 Tier1 curated entrypoints 为公共入口治理边界，建立一个可回归的 drift gate：
  - Tier1 入口集合发生变化时，必须 fail-fast 提示缺失的示例/pytest 覆盖
  - 示例套件与 pytest public_api suite 覆盖集合必须一致（或至少都覆盖 Tier1 集合）
- 新增 `scalim-public-api` skill，并提供：
  - “推荐导入”与常用 gate/生成入口的可复制清单
  - 与 Tier1/示例套件一致的确定性生成 references（禁止手改）
  - 可运行样例代码的索引（以现有 notebooks/pytest SSOT 为真相，不依赖口口相传）
- 复用现有治理约束：
  - 用户材料不得引用 internal imports（`check-user-material-import-boundaries`）
  - docs/skills 的 `.gen.` 与 injected-block 规则（`just gen-docs`/`just gen-*` 刷新）

**Non-Goals:**
- 不重做 public API 设计（不在本变更内新增/删除 public facade 的导出面，除非为补齐 Tier1 缺口必须最小调整）
- 不引入“符号级 manifest 文件”作为通过 CI 的硬前置（仍以 markers + `__all__` + 可运行示例为主）
- 不把 notebooks 的执行迁移为 “只能在 marimo 内跑”（保持 headless SSOT 入口可被 `just examples`/pytest 复用）

## Decisions

### Decision 1: 以 Tier1 curated entrypoints 作为“必须有示例覆盖”的 public surface 边界

我们将 drift gate 的强约束范围收敛到 Tier1 curated entrypoints（markers），原因：

- Tier1 是 docs 明确推荐导入的稳定入口集合，最需要“可运行示例 + 回归门禁”；
- 全量 public API catalog（扫描所有 `__all__`）会包含大量 Tier2/贡献者入口，强制其都进入示例套件会拉高维护成本；
- Tier2 仍可通过 `__all__` 治理脚本与 docs catalog 生成保持可审阅，但不强制“每个模块都写教学示例”。

实现上，gate 将确保：
- Tier1 ⊆ example_public_api_suite 覆盖集合
- Tier1 ⊆ pytest public_api 覆盖集合
- 两条覆盖集合之间不允许出现 Tier1 漂移（缺失/新增必须 fail-fast）

### Decision 2: 覆盖集合推导使用静态扫描（AST/text），避免 import 带来的可选依赖与副作用

覆盖集合的推导不依赖执行 notebooks，也不依赖 import `scalim` 模块，主要通过：

- `scripts/public_api_tooling.py` 扫描 Tier1 markers 与 `__all__`（已存在且为 SSOT 工具）
- 对 `notebooks/marimo/example_public_api_suite/chapters/*.py` 做 AST 扫描，提取 `from scalim... import ...` / `import scalim...` 的模块前缀，用于近似“本章节覆盖了哪些 Tier1 模块”
- 对 `tests/public_api/test_example_public_api_suite.py` 提取 `chapter_ids=[...]` 列表，并限定只计算这些章节的覆盖集合，以表示 pytest public_api suite 的覆盖范围

在必要时，章节可通过一个小的“覆盖声明标记”（例如模块级常量 `COVERS_TIER1_MODULES = (...)`）对静态扫描做显式补充；
但该声明仍属于章节源码的一部分，不引入独立 manifest 文件。

### Decision 3: `scalim-public-api` skill 采用“手工 SKILL.md + 受控 generated references”的治理模型

参考 `scalim-yaml-dsl` skill 的既有成功经验，`scalim-public-api` skill 将分层：

- 手工维护（SSOT）：
  - `agentdev/skills/scalim-public-api/SKILL.md`：工作流说明、常用命令、迁移/排错入口
- 自动生成（禁止手改；可校验可再生）：
  - `agentdev/skills/scalim-public-api/references/**/*.gen.*`
  - `agentdev/skills/scalim-public-api/references/generated/**`

生成器以“markers + `__all__` + 示例套件结构”为输入，输出：
- Tier1 entrypoints 列表（含 desc/scenario/export count）
- Tier1 → 示例章节/pytest 的覆盖映射与推荐命令
- 可运行样例代码索引（指向 notebooks/pytest 的 SSOT 入口；必要时提供可复制片段）

校验模式与输出边界参考 `agent-skill-export` 规范：拒绝写入用户 skill 目录，且 validate 仅比较受控输出。

### Decision 4: marimo 升级作为“元信息修复”，不做大规模 notebook 结构重写

本变更把 marimo 升级限定为：
- 更新 `notebooks/marimo/**` 顶部 `__generated_with` 字段与当前依赖锁版本对齐

除非有明确收益（例如导出/格式化能力需要），否则不做 cell 结构重排，避免产生大量非语义 diff。

## Risks / Trade-offs

- [静态扫描覆盖推导不完美] → 提供章节内显式覆盖声明常量作为兜底，并在 gate 输出中打印“扫描推导结果 + 建议补齐方式”。
- [gate 过严导致贡献成本上升] → 范围仅锁定 Tier1；并把错误信息做成 fail-fast 且可操作（明确指出缺失模块 + 推荐新增章节位置）。
- [skill 生成器引入维护负担] → 复用 `scalim-misc` 的既有生成/validate 模式与 `just` 入口；仅生成 references，不覆盖 SKILL.md。

