# Tasks: Stage C vendor/ 目录退役

## 0. Specs landing（propose / 绑定分支，apply 前）

- [x] 0.1 `governance-module-organization`：r201 两个场景重写（vendor README 审计 → 第一方迷你库 docstring provenance + 禁止重建 vendor 托管概念）；r(none)「主包（排除 vendor）」措辞更新；对应可执行场景同步
- [x] 0.2 commit specs（Specs landing）。DoD: `llman sdd show c54-vendor-directory-retirement --output json --type change` → `readyToImplement=true`

## 1. 迁址与删除 — commit `refactor: retire vendor/ directory (litejinja2 and importlibx relocate in-tree)`

- [ ] 1.1 `git mv src/scalim/vendor/litejinja2 src/scalim/dsl/yaml_dsl/_internal/litejinja2`；`git mv src/scalim/vendor/compact/importlibx.py src/scalim/_internal/utils/importlibx.py`
- [ ] 1.2 import 点改写：importlibx 9 处运行时相对导入（深度逐文件核对）+ `tests/support/testing_utils.py`；litejinja2 1 处（`template_precompile.py` → `from ..litejinja2 import ...`）
- [ ] 1.3 删 `src/scalim/vendor/`（README/`__init__`/`compact/__init__` 标记）；`tests/governance/test_vendor_litejinja2.py` → `tests/governance/test_litejinja2.py`（import 路径随迁）
- [ ] 1.4 治理脚本清理：check-import-graph `_is_vendor_file`、check-complexity / check-cast-usage / check-no-branch / check-no-cover 的 vendor 排除项、gen-docs `exclude_dirs` 与文案
- [ ] 1.5 pyproject coverage `omit` 删两行 `src/scalim/vendor/*`；grep `vendor` 在 src/packages/scripts 应仅剩 AGENTS 政策性表述。DoD: `just check-only-py` 全绿

## 2. 文档与收尾

- [ ] 2.1 根 `AGENTS.md:45` 死路径措辞微调；`llmanspec/AGENTS.md` spec 前缀表删 `vendor-*`；`just gen-docs` 刷新 public-api.gen.md 文案
- [ ] 2.2 `just qa` 全绿；`llman sdd validate --all --strict --no-interactive`
- [ ] 2.3 Breaking 清单追加（`scalim.vendor.*` 命名空间整体消失）；进入 `llman-sdd-verify`
