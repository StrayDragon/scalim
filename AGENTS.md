<!-- LLMANSPEC:START -->
# LLMAN 规范驱动开发

本项目使用 llman SDD。阅读 `llmanspec/config.yaml` 了解 SDD 命令行为配置，以及 `llmanspec/AGENTS.md` 获取项目附加规则。

## SDD 流水线

使用 `/llman-sdd-explore` 开始，然后按照 pipeline：`/llman-sdd-propose` → `/llman-sdd-apply` → `/llman-sdd-verify` → `/llman-sdd-archive`。

保留此托管块，便于 `llman sdd init --update` 刷新。
<!-- LLMANSPEC:END -->

# Repository Guidelines

## Quick Commands (SSOT Entry Points)
- `just --list`: discover tasks.
- `just qa`: repo quality gates (lint/tests + drift checks + llmanspec checks, etc.).
- `just gen-docs`: refresh docs-site generated pages and injected blocks.
- `just llmanspec-check`: sanitize + validate llmanspec artifacts.
- `just bump-versions <X.Y.Z>` / `just bump-versions <X.Y.Z> YES`: dry-run / apply unified package versions (see pre-release checklist).

## Hard Rules (SSOT)
- **YAML authoring vs Python policy** (workflow/books 迭代方向):
  - YAML DSL SHOULD stay orchestration + resource identity (`runs` / deps / `resources.*.id+variant+path` / `outputs.to` / content fields).
  - Book **write strategy** and **memory budget** are **Python SSOT** via `ResourcesPolicy` / `BookWritePolicy` / `BookBudgetPolicy` on `WorkflowRunOptions` / `DemandRunOptions` (builtin defaults / unlimited when omitted).
  - YAML `resources.books.*.write_defaults` and `xlsx_memory.budget` MUST NOT be reintroduced; runtime fail-fast + migration hints.
  - Agent-facing migration: `agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-07-12-book-write-policy-python-ssot.md`；统一 book identity 见 `.../2026-07-13-unified-xlsx-book-kind.md`；IR pathful/pathless 见 `.../2026-07-13-normalize-xlsx-book-ir-path-presence.md`；硬删旧 YAML 别名见 `.../2026-07-20-remove-deprecated-xlsx-file-memory-kinds.md`（仅 `resources.books.<id>.xlsx` 可选 `path`；`xlsx_file`/`xlsx_memory` 已移除）。
  - `allow_formulas` / `encoding` may remain YAML for now (usually static).
  - Archived track: `llmanspec/changes/archive/2026-07-12-c20-book-write-policy-python-ssot/`、`.../2026-07-12-c30-workflow-shared-book-memory/`、`.../2026-07-13-c15-decide-xlsx-memory-book-role/`、`.../2026-07-13-c20-add-unified-xlsx-book-kind/`、`.../2026-07-13-c25-normalize-xlsx-book-ir-path-presence/`、`.../2026-07-20-c999-remove-deprecated-xlsx-file-memory-kinds/`；后续 shared-book 优化见 `llmanspec/futures/xlsx-file-numeric-type-loss/future.md`。
- **Python runtime boundary**: code under `src/scalim/` MUST remain compatible with Python 3.6 (dev tooling is typically Python 3.10+; see `pyproject.toml`).
- **Formatting**: Python-only; 4-space indent; line length 140; double quotes (ruff formatter). Use ruff as the source of truth for formatting and linting.
- **Imports**: inside `src/scalim/` prefer relative imports; avoid `import scalim` / `from scalim...` (tests/scripts/notebooks may import `scalim` directly).
- **Runtime contracts**:
  - `if TYPE_CHECKING:` is only for type-only imports/aliases; MUST NOT be used to fake class interfaces (conditional methods / ellipsis stubs).
  - When one mixin/class depends on methods provided by another mixin/class, express that dependency as an explicit runtime contract (prefer `ABC` + `@abstractmethod`, Python 3.6 compatible).
- **typing_extensions**: keep runtime compatible with older `typing_extensions`; use `src/scalim/vendor/compact/typing_extensionsx.py` shims when needed.
- **Doc governance**:
  - Any file containing `.gen.` is generated; do not edit by hand. Edit SSOT and run the referenced generator.
  - **禁止**直接手工编辑任何 `*.gen.*` 文件(例如 `src/scalim/dsl/yaml_dsl/schema/*.gen.json`、`agentdev/skills/**/syntax-catalog.gen.md`). 如果需要拆分提交,使用“回滚/暂存 + 重新生成”的方式拆分,不要在生成物里手改。
  - Any `<!-- BEGIN AUTOGEN:<id> -->` / `<!-- END AUTOGEN:<id> -->` block is injected; do not edit inside the block. Edit SSOT and run `just gen-docs`.
- **Dev artifacts**:
  - Rebuildable sample data / reports MUST be generated under `.tmp/` and MUST NOT be committed (e.g. viz examples under `.tmp/artifacts/scalim-viz/`).
  - Known legacy exception (do not rename yet): `src/scalim/_project_constants.py` and `frontend/**/src/generated/project_constants.ts` are generated but not suffixed with `.gen.`.
- **Project directives**: do not remove repository-specific machine-readable directives; they are consumed by governance scripts/generators.
  - `# pragma: scalim-public-api tier1:...` (Tier 1 public API catalog for `docs/doc/getting-started/public-api.gen.md`)
  - `# pragma: allow-c901-file ...` (complexity gate exceptions; see `scripts/check-noqa-c901.py`)
  - `# pragma: allow-cast-file ...` (cast-usage gate exceptions; see `scripts/check-cast-usage.py`)
  - `# pragma: allow-object` / `# pragma: allow-object-file ...` (`object` annotation exceptions; see `scripts/check-object-type.py` and `docs/doc/dev/object-type-governance.md`; default scan skips `tests/`; gated in `quick-check`)
- **Skills extraction markers**: do not remove `# region SCALIM-SKILL:<tag>` / `# endregion` markers (used for automated skill example extraction).
- **Privacy**: do not quote, enumerate, or summarize the contents of `.tmp/known-outer-paths-using-this-package.txt`; only reference the file path.
- **Pre-release**: before bumping versions / tagging, follow `docs/doc/dev/pre-release-checklist.md` (scope last-tag→HEAD, breaking/docs/public-api drift, then `just bump-versions`). `just qa` is a gate, not a substitute for that checklist.
- **Policy SSOT (closed sets)**:
  - For policy-like values that are a closed set and cross boundaries (state/pickle/JSON/YAML/config), the **single source of truth MUST be an Enum (`StrEnum`)**.
  - Do **NOT** maintain duplicated allowed-value definitions (e.g. `StrEnum` **and** `Literal[...]` lists) for the same policy.
  - **Public API (strict in)**: constructors/options exposed to users MUST accept the Enum only (fail-fast on string literals).
  - **Config/state inputs (wide in)**: YAML/JSON/state/pickle MAY provide builtin `str`; code MUST validate/normalize via the Enum SSOT and then store the canonical builtin `str` value.
  - **Outputs (stable out)**: any state/wire representation MUST emit builtin `str` (from `.value`); never serialize Enum instances or `str` subclasses.
  - **Event/Hook identity exception** (二开注册面): 进程内事件身份与订阅以 `EventType` 为唯一 SSOT（`Event.event_type`、`Observer`/`Hook.event_types`、`wants`/`emit`/dispatch 键）。**不适用**上条「进程内也落 builtin `str`」偏好。落盘/JSONL/viz 等边界 MAY 编码 `.value` 为 builtin `str`，读回进程内 `Event` 时 MUST 归一为 `EventType`。Typed payload 数据类从 `scalim.events` 公开导出；MUST NOT 以 `scalim.events._events` 作为用户契约。

## Pointers (keep this file small)
- Project/code reading map: `docs/doc/getting-started/reading-guide.md`
- Docs governance workflow: `docs/doc/dev/doc-governance.md`
- Pre-release calibration (last tag → HEAD, docs/API/breaking): `docs/doc/dev/pre-release-checklist.md`
- Docs site config + content root: `docs/zensical.toml`, `docs/doc/`
- Specs (llmanspec): `llmanspec/specs/` and `docs/doc/specs/index.md`
- Architecture overview: `ARCH.md` and `docs/doc/architecture/arch.md`
- YAML DSL review checklist: `docs/doc/yaml-dsl/review-checklist.md`
