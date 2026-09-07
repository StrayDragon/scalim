---
depends_on: []
rules_edit_acked: true
branch: sdd/c52-modernize-py310-baseline
base_sha: d1b5cb4565ccc0f5c9c0414c6cd984c00484ef63
checkpointed: false
---

# 0.20.x Stage A — 现代基线：Python floor 3.10，删除 3.6 兼容层

> ROADMAP（`b31c76ea`）0.20.x 现代化线 · Stage A。Stage B（YAML 去 vendor）与 Stage C（vendor/ 目录退役）由后续 change 承接；本 change **不动** `vendor/yamlx`，**不迁** `litejinja2`/`importlibx`。

## Why

- 0.20.x 决策（ROADMAP）：runtime floor 3.6 → **3.10**（企业存量采用面 + 现行 CI 基线即 3.10；同行框架 2026-09 全部支持 3.10）。
- 3.6 兼容层已成为现代化最大阻力：vendor 兼容 shim（`dataclassesx` 1.2k LOC、`typing_extensionsx` 107 LOC、`StrEnum` backport）+ py36 门禁（2 个 docker just 目标 + ~580 LOC scripts）+ ruff `UP` 全禁（ruff 最低 target py37），导致 253 个文件、约 3,700 处旧式 typing 注解无法机械化改写。
- floor 3.10 后：`dataclasses`（3.7+）、`TypeGuard`/`Literal`/`TypedDict`/`Protocol`/`runtime_checkable`（≤3.10）均入 stdlib，仅 `Self`(3.11+)/`override`(3.12+) 仍需 `typing-extensions>=4.4`；`StrEnum`(3.11+) backport 按 ratchet 迁 `_internal/` 暂留。

## What Changes

- **配置面**：`requires-python>=3.10`（root）；basedpyright `pythonVersion=3.10`；ruff `target-version="py310"` + 解禁 `UP` + 删 `FA100` ignore + 删 `typing_extensions` banned-api；删 py<3.7/py<3.8 env-marker 依赖块；`typing-extensions>=4.4`。
- **兼容层迁移**（codemod + 删源）：`vendor/dataclassesx` → stdlib `dataclasses`（132 行/114 文件）；`vendor/compact/typing_extensionsx` → `typing` + `typing_extensions`（78 文件）；`vendor/compact` 的 `StrEnum`/`Self` re-export → `_internal/strenum.py` / `typing_extensions`（14 文件）；`vendor/compact/__init__.py` 清空 re-export（`importlibx.py` 原位保留至 Stage C）；删 9 处 `from __future__ import absolute_import`；收拢 `call_by.py`/`security.py` 的 `_PY38_PLUS` 门。
- **机械化现代语法**：ruff `UP` autofix（`List[`→`list[`、`Optional[`→`X | None` 等，~253 文件）+ `ruff format` + basedpyright 收敛。
- **删 py36 工具链**：`py36-compat-check` / `py36-typingext-check` just 目标、`scripts/check-py36-syntax.py`、`scripts/check-py36-typingext-docker.sh` 及对应 governance tests；`gen-public-api-jump-imports.py` 保留（justfile 注明另有编辑器/LSP 跳转用途）。
- **删 vendor-legacy-sync**：`just sync-project-vendors` + `scripts/vendor-sync.py`（capability 退休；vendors/libs 下游链路终止，0.20.0 release notes 汇总 Breaking）。
- **CI**：matrix `["3.10"]` → `["3.10","3.11","3.12","3.13","3.14"]`；matrix job 跑 py-only 套件，最新版跑全量 `just qa` 兜底。
- **说明面**：根 `AGENTS.md`（Python runtime boundary、typing_extensions 条目）、`llmanspec/AGENTS.md` 项目上下文、`README.md:111/199`、`docs/doc/dev/pre-release-checklist.md:32`、`docs/doc/benchmark/external-baseline.md` §4.4 措辞（历史测量数据不动）。

**明确不做**：`vendor/yamlx` 保留原样（Stage B）；`litejinja2`/`importlibx` 迁址（Stage C）；依赖优选/extras 扩展（Deferred）。

## Capabilities / Specs（Specs landing 范围）

| spec | 处置 |
|---|---|
| `vendor-dataclassesx` | **整体退休**（删 `.feature` 与目录） |
| `vendor-legacy-sync` | **整体退休**（删 `.feature` 与目录） |
| `governance-module-organization` | typing 兼容集中条款改写：3.6 → 3.10；`typing_extensionsx` 条款 → `typing_extensions` 直引（`Self`/`override`）+ `_internal/strenum.py`；lint 禁令对象同步 |
| `governance-package-identity` | 「runtime 主包 MUST 保持 Python 3.6 兼容」→ 3.10 |
| `governance-misc` | 重构文档模板「保持 Python 3.6 兼容」→ 「与当前支持窗口（ROADMAP）一致」 |
| `workflow-execute-organization` / `workflow-ir` / `execution-structure` | 「Python 3.6 兼容」条款 → 项目运行时边界（3.10） |
| `yaml-dsl-workflow` | 最小导入环境场景：`3.6 + typing-extensions==4.1.1` → `3.10 + typing-extensions>=4.4` |

## Impact

- **SSOT（手工）**：`pyproject.toml`、`justfile`、`scripts/*`、`.github/workflows/ci.yaml`、`src/scalim/vendor/**`、`src/scalim/_internal/strenum.py`（新增）、根 `AGENTS.md`、`llmanspec/AGENTS.md`、`README.md`、`docs/doc/dev/pre-release-checklist.md`、`docs/doc/benchmark/external-baseline.md`。
- **生成物**：`docs/doc/getting-started/public-api.gen.md` 等由 `just gen-docs` 再生成（禁止手改）；`docs/doc/assets/**` 基准数据不重测。
- **门禁**：`just check-only-py` + `just qa` 全绿（test-gate 100% 覆盖、type-check、docs-drift、llmanspec-check）。
- **Breaking（并入 0.20.0 汇总）**：3.6–3.9 不再受支持；`scalim.vendor.dataclassesx`/`vendor.compact` re-export 命名空间消失；`vendors/libs` 同步链路移除。

## Seam（测试边界口径）

复用既有 harness，不发明新 seam、不新增 `.feature` 可执行场景（`config.yaml` 无 `bdd:` 段）：pytest 全量（含 `tests/governance/*`）+ `just check-only-py` / `just qa` / `just examples`；语义守卫沿用 `tests/yaml_dsl/test_yaml_backend_migration.py`（YAML 1.2 golden corpus，Stage A 不动 yamlx 故不触及）。