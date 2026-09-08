---
depends_on: []
rules_edit_acked: true
branch: sdd/c53-yaml-dependency-unvendor
base_sha: ddb5e85ee1e6c1845d4f649f894386dc621c85d4
checkpointed: false
---

# 0.20.x Stage B — YAML 去 vendor：切换为 PyPI `ruamel.yaml` 依赖

> ROADMAP（`b31c76ea`）0.20.x 现代化线 · Stage B。前置 Stage A（c52，floor 3.10）已归档；Stage C（`vendor/` 目录退役）由后续 change 承接。本 change **不动** `litejinja2`/`importlibx` 的迁址（仅连带清理 yamlx 相关文档与配置例外）。

## Why

- vendored `yamlx` 树约 5.8MB（含 3.1MB **cp36 ABI 的 `.so` 二进制**——在 floor 3.10 起早已不可加载，纯死重），全部进入发布 wheel。
- floor 3.10 后 vendor 的存在理由（`Python 3.6` + 不可安装第三方依赖的下游同步场景）已随 c52（vendor-legacy-sync 退役）终结。
- **Stage B-0 spike（2026-09-07）已证语义等价**：同一 runner 在三个隔离后端（vendored 0.18.3 / 上游 0.18.17 / 上游 0.19.1）下，对 53 个 corpus 文件 + 10 个合成用例的 **load 结果零差异**（YAML 1.2 标量、重复键 fail-fast/last-wins、merge key、锚点别名、compose 行列号、错误标记）；CLI rt 字节幂等合约（带 authoring 发射器配置）三端全部成立。仅 safe-dump 排版折叠存在版本间漂移（`dump_effective_demand_yaml` 仅用于 review/debug，可接受）。

## What Changes

- **依赖**：runtime 新增 `ruamel.yaml>=0.19.1`（0.19 线；clib 加速改由 `ruamel.yaml.clibz` 提供，随依赖自动解析；spike 证据见 `.tmp/spike-b0/`）；**不加锁上界**。
- **删除 `src/scalim/vendor/yamlx/`** 整树（vendored ruamel 0.18.3 + vendored PyYAML 6.0.1 + 2 个 cp36 `.so` + bootstrap）。
- **运行时 import 切换**（2 处）：`dsl/yaml_dsl/_internal/config_parsing/yaml_load.py`、`effective_yaml.py` 的 `from .....vendor.yamlx.ruamel.yaml import YAML` → `from ruamel.yaml import YAML`。工具包（scalim-cli authoring / scalim-yaml-dsl-lsp）的 `from ruamel.yaml...` import 路径**不变**（vendor 的 sys.modules 别名设计使其天然指向上游）。
- **对拍/脚本切换**：`scripts/sanitize.py`、`scripts/check-staged-sanitize.py`、`tests/yaml_dsl/test_yaml_backend_migration.py` 的 `scalim.vendor.yamlx.yaml`（PyYAML 门面）→ 直接 `import yaml`（PyYAML 移入 dev 依赖组，仅作对拍 oracle）。
- **测试调整**：删 `tests/governance/test_vendor_yamlx.py`（vendored 不变式随之失效）；`test_yaml_backend_migration.py` 保留为语义守卫（corpus 对拍改为上游 ruamel vs dev-PyYAML）。
- **配置清理**：ruff `exclude` 的 `vendor/yamlx/**`、basedpyright `ignore`/`extraPaths` 的 yamlx 条目随删除移除；coverage 的 `vendor` omit 保留（litejinja2 仍在 vendor/ 至 Stage C）。
- **文档**：`src/scalim/vendor/README.md` 删 yamlx 节；`vendor/yamlx/SOURCE.md` 随目录删除（历史描述已在 Stage A polish 历史化）。

**明确不做**：`litejinja2`/`importlibx` 迁址（Stage C）；`dump_effective_demand_yaml` 的排版漂移不视为破坏（review/debug 用途，测试断言 load 语义而非 dump 字节）。

## Capabilities / Specs（Specs landing 范围）

| spec | 处置 |
|---|---|
| `yaml-backend-migration` | **整体改写**：r102「vendored 唯一后端」→「PyPI `ruamel.yaml` 唯一后端（YAML 1.2 语义保留）」；`no-external-install` 可执行场景删除；r551「vendored PyYAML 对拍」→「dev 依赖 PyYAML 对拍」，py36 smoke 条款保持 Stage A 语义（CI matrix 下界） |
| `yaml-dsl-workflow` | r227 可执行场景「YAML 后端随包内置」→「`ruamel.yaml>=0.19.1` 依赖」 |

## Impact

- **SSOT（手工）**：`pyproject.toml`（依赖 + dev 组）、`src/scalim/dsl/yaml_dsl/_internal/config_parsing/{yaml_load,effective_yaml}.py`、`scripts/{sanitize,check-staged-sanitize}.py`、`tests/`（上述调整）、`src/scalim/vendor/README.md`、ruff/basedpyright 配置。
- **生成物**：无 schema/README 示例变化（YAML 语料不变）；如治理检查报 drift 按 `just gen-docs` 刷新。
- **门禁**：`just qa` 全绿（重点：`test_yaml_backend_migration.py` corpus 对拍、`test_upsert_lsp_comment_roundtrip_is_stable_on_canonical_fixture` rt 字节幂等、coverage 100%）。
- **Breaking（并入 0.20.0 汇总）**：安装 scalim 现在会引入 `ruamel.yaml` 依赖；`scalim.vendor.yamlx` 命名空间消失；wheel 体积显著下降（约 -9MB 级）。

## Seam（测试边界口径）

复用既有 harness：`test_yaml_backend_migration.py`（corpus 对拍 oracle：上游 ruamel vs dev-PyYAML）、LSP rt 幂等 contract suite、全量 pytest + `just check-only-py`/`just qa`；spike 证据 `.tmp/spike-b0/`（不入库）。