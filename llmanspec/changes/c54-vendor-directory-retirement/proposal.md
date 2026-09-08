---
depends_on: []
rules_edit_acked: true
branch: sdd/c54-vendor-directory-retirement
base_sha: ddb5e85ee1e6c1845d4f649f894386dc621c85d4
checkpointed: false
---

# 0.20.x Stage C — `vendor/` 目录退役：第一方迷你库迁址

> ROADMAP（`b31c76ea`）0.20.x 现代化线 · Stage C（收尾）。前置 c52（Stage A）/c53（Stage B）已归档。完成后 `src/scalim/vendor/` 整体消失，ROADMAP 0.20.x 的清理目标全部达成。

## Why

- Stage A/B 之后 `vendor/` 仅剩三件东西：`litejinja2/`（第一方 Jinja2 兼容子集，约 1.1k LOC）、`compact/importlibx.py`（56 LOC，测试 seam + 可选依赖守卫）、README/`__init__` 标记文件——`vendor` 作为「上游拷贝托管地」的概念已无存在意义。
- 名实不符：`litejinja2`/`importlibx` 是第一方实现，放在 `vendor/` 下误导审计（vendor README 的 provenance 约定是给上游拷贝用的）。
- 治理脚本（check-import-graph/complexity/cast/no-branch/no-cover/gen-docs）仍为 vendor 保留特例分支/排除项——目录消失后全部可删。

## What Changes

- **迁址（保名）**：
  - `vendor/litejinja2/` → `dsl/yaml_dsl/_internal/litejinja2/`（唯一运行时消费方 `config_parsing/template_precompile.py` 就在旁边；保留名称作为 Jinja2 兼容子集的语义锚点，模块 docstring 继续承载 provenance）。
  - `vendor/compact/importlibx.py` → `_internal/utils/importlibx.py`（跨切面共享，沿用 `loggingx` 等 x 后缀惯例）。
- **删除 `src/scalim/vendor/` 整目录**（README、`__init__.py`、`compact/__init__.py` 标记；root 属主的残留 `__pycache__` 需用户 sudo 清理）。
- **import 点改写**：importlibx 9 处运行时相对导入 + `tests/support/testing_utils.py`（绝对导入）；litejinja2 1 处运行时导入。
- **治理脚本清理**：check-import-graph（`_is_vendor_file` 特例）、check-complexity/check-cast-usage/check-no-branch/check-no-cover 的 `vendor` 排除项、gen-docs 的 `exclude_dirs` vendor 与文案。
- **配置清理**：pyproject coverage `omit` 的 `src/scalim/vendor/*` 两行。
- **文档**：根 `AGENTS.md:45` 的死路径措辞微调；`llmanspec/AGENTS.md` spec 前缀表删 `vendor-*`。

**明确不做**：litejinja2 的功能/语义任何变化（纯迁址）；`unknown_fields.py` 的 jsonschema 化（Deferred）。

## Capabilities / Specs（Specs landing 范围）

| spec | 处置 |
|---|---|
| `governance-module-organization` | r201「vendor README 可审计」→「第一方兼容/模板迷你库（`_internal/strenum`、`_internal/utils/importlibx`、`dsl/yaml_dsl/_internal/litejinja2`）MUST 在模块 docstring 维护 provenance 与移除策略；禁止重建 `vendor/` 托管概念」；r(noenvironment)「主包（排除 vendor）」措辞随目录消失更新；对应可执行场景同步 |

## Impact

- **SSOT（手工）**：上述迁址文件、import 点、治理脚本、pyproject coverage、两份 AGENTS.md。
- **生成物**：`docs/doc/getting-started/public-api.gen.md`（vendor 排除文案变化）→ `just gen-docs` 刷新；其余无。
- **门禁**：`just qa` 全绿（治理检查族在此 change 是重点覆盖对象——它们本身被修改）。
- **Breaking（并入 0.20.0 汇总）**：`scalim.vendor.*` 命名空间整体消失（litejinja2/importlibx 本就是内部模块，公共 API 面无变化）。

## Seam（测试边界口径）

复用既有 harness：`tests/governance/test_litejinja2.py`（自 `test_vendor_litejinja2.py` 迁移改名）、`tests/support/testing_utils.py` 的 importlibx seam 消费方（sinks/ob 可选依赖测试族）、全量 pytest + `just check-only-py`/`just qa`。