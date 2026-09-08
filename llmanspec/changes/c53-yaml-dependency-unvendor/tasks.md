# Tasks: Stage B YAML 去 vendor

## 0. Specs landing（propose / 绑定分支，apply 前）

- [x] 0.1 `yaml-backend-migration` 整体改写：r102 vendored → PyPI `ruamel.yaml>=0.19.1` 唯一后端（YAML 1.2 MUST 保留）；删 `runtime-does-not-rely-on-external-yaml-installations` 可执行场景；r551 对拍 oracle → dev-PyYAML、floor smoke 语义保持（CI matrix 下界）；purpose 行同步
- [x] 0.2 `yaml-dsl-workflow` r227 可执行场景「YAML 后端随包内置」→「`ruamel.yaml>=0.19.1`」
- [x] 0.3 commit specs（Specs landing）。DoD: `llman sdd show c53-yaml-dependency-unvendor --output json --type change` → `readyToImplement=true`

## 1. 依赖与 import 切换 — commit `refactor: switch YAML backend to PyPI ruamel.yaml (drop vendored yamlx)`

- [ ] 1.1 pyproject：runtime dependencies + `ruamel.yaml>=0.19.1`；dev 组 + `pyyaml`（对拍 oracle）；ruff `exclude` 删 `src/scalim/vendor/yamlx/**`；basedpyright `ignore`/`extraPaths` 删 yamlx 条目
- [ ] 1.2 `yaml_load.py` / `effective_yaml.py`：`from .....vendor.yamlx.ruamel.yaml import YAML` → `from ruamel.yaml import YAML`
- [ ] 1.3 `scripts/sanitize.py`、`scripts/check-staged-sanitize.py`、`tests/yaml_dsl/test_yaml_backend_migration.py`：`scalim.vendor.yamlx.yaml` → `yaml`（PyYAML）
- [ ] 1.4 删 `src/scalim/vendor/yamlx/` 整树；`src/scalim/vendor/README.md` 删 yamlx 节并更新顶部说明；删 `tests/governance/test_vendor_yamlx.py`
- [ ] 1.5 grep 残留：`vendor.yamlx|vendor/yamlx|_ruamel_yaml` 在 src/tests/scripts/packages 应为零命中。DoD: `just check-only-py` 全绿

## 2. 全量门禁收尾 — commit（如需）`qa: stage-b final gate fixes`

- [ ] 2.1 `just check-only-py` → `just qa`；`llman sdd validate --all --strict --no-interactive`
- [ ] 2.2 Breaking 清单追加到 `breaking-0.20.0.md`（ruamel 依赖引入 / vendor.yamlx 消失 / wheel 体积）
- [ ] 2.3 进入 `llman-sdd-verify`
