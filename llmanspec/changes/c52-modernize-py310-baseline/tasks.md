# Tasks: Stage A 现代基线（floor 3.10，删 3.6 兼容层）

> 提交合并备注:task 1.x(配置面)与 3.x(UP autofix)合并为一个 commit——
> ruff target 提到 py310 才会激活 UP 规则,单独提交配置面会出现 lint 红灯;基于
> basedpyright pythonVersion=3.6 与 stdlib 导入天然冲突,两者必须同 commit 才能保持每 commit 门禁全绿。

机械面横扫全库，按「先配置 → 再 codemod → 再 autofix → 再删工具链」的 expand-contract 排序，不强拆垂直切片。每个编号段 ≈ 一个 commit。

Seam（已确认）：pytest 全量 + `just check-only-py` / `just qa` / `just examples`；无新增 `.feature`、无 `bdd:` runner。语义守卫 `test_yaml_backend_migration.py` 本 change 不触及。

## 0. Specs landing（propose / 绑定分支，apply 前）

- [x] 0.1 `governance-module-organization`：typing 集中条款改写（3.6→3.10；`typing_extensionsx` → `typing_extensions` 直引 `Self`/`override` + `_internal/strenum.py`；lint 禁令同步）；purpose 行 3.6 → 3.10
- [x] 0.2 删除 `vendor-dataclassesx` / `vendor-legacy-sync` 两个 capability（整目录），`valid_scope` 随之消失
- [x] 0.3 `governance-package-identity` / `governance-misc` / `workflow-execute-organization` / `workflow-ir` / `execution-structure` / `yaml-dsl-workflow` / `yaml-backend-migration` 的 3.6 条款 → 3.10 / 「项目运行时边界（ROADMAP）」；`yaml-dsl-workflow` 最小环境 → `3.10 + typing-extensions>=4.4`
- [x] 0.4 commit specs（Specs landing）。DoD: `llman sdd show c52-modernize-py310-baseline --json` → `readyToImplement=true`

## 1. 配置面 floor bump — commit `chore: raise runtime floor to python>=3.10 (toolchain config)`

- [x] 1.1 `pyproject.toml`：`requires-python>=3.10`；classifiers 3.6 → 3.10–3.13；删 `python_version<'3.7'` / `<'3.8'` env-marker 依赖块；`typing-extensions>=4.4`（单一无 marker）
- [x] 1.2 ruff：`target-version="py310"`；`unfixable` 删 `UP`；ignore 删 `FA100`；删 `flake8-tidy-imports.banned-api` 的 `typing_extensions` 禁令；per-file-ignores 删 `typing_extensionsx` 行；exclude 中 `dataclassesx/_backport.py` 行随 2.x 删除
- [x] 1.3 basedpyright：`pythonVersion="3.10"`；`ignore`/`extraPaths` 中 dataclassesx 行随 2.x 删除
- [x] 1.4 uv lock 刷新。DoD: `uv sync` 成功；`ruff check` / `basedpyright` 以新 target 运行并输出「旧写法」红灯清单（task 2/3 的输入）

## 2. codemod 兼容层迁移 + 删源 — commit `refactor: migrate py36 vendor shims to stdlib and typing_extensions`

- [x] 2.1 新增 `src/scalim/_internal/strenum.py`：迁移 `vendor/compact/__init__.py` 的 StrEnum backport，docstring 注明「floor≥3.11 时删除（ROADMAP ratchet）」
- [x] 2.2 一次性 codemod（脚本入 `.tmp/`，不提交）：`vendor.dataclassesx` → `dataclasses`；`vendor.compact.typing_extensionsx` → `typing`（TypeGuard/Literal/TypedDict/Protocol/runtime_checkable）+ `typing_extensions`（Self/override）；`vendor.compact import StrEnum` → `_internal.strenum`；`vendor.compact import Self` → `typing_extensions`（相对导入深度逐文件正确）
- [x] 2.3 删 9 处 `from __future__ import absolute_import`；`call_by.py`/`security.py` 收拢 `_PY38_PLUS` 为无条件 `ast.Constant` 分支（删 `ast.Str`/`ast.Num`/`ast.Bytes` 旧节点路径）
- [x] 2.4 删 `src/scalim/vendor/dataclassesx/` 整目录；`vendor/compact/__init__.py` 清空 re-export（`importlibx.py` 原位保留）
- [x] 2.5 更新涉及 shim 的 tests（`test_execution_run_ir.py` 等 6 文件的导入行）；保留 `test_vendor_yamlx.py` / `test_vendor_litejinja2.py`（对象仍在）。DoD: `just check-only-py` 的 lint/type 项绿

## 3. ruff UP autofix + 类型收敛 — commit `refactor: apply ruff UP modernization (builtin generics, PEP 604)`

- [x] 3.1 `ruff check --fix --select UP`（src/ → packages/ → tests/ 顺序）+ `ruff format`；确认未引入 `from __future__ import annotations`
- [x] 3.2 basedpyright 收敛（strict 列表 14 目录重点过目）；`# type: ignore` 增量仅限类型系统差异
- [x] 3.3 抽查语义等价：`X | None` 热路径（dataclass 字段、运行时反射无 `get_type_hints` 依赖破坏）。DoD: `just type-check` / `just type-check-core-tight` 绿

## 4. 删 py36 工具链与 vendor-legacy-sync — commit `chore: remove py36 gates and vendor-legacy-sync tooling`

- [x] 4.1 justfile：删 `py36-compat-check` / `py36-typingext-check` / `sync-project-vendors` 目标；`check-only-py` 链摘除两个 py36 项
- [x] 4.2 scripts：删 `check-py36-syntax.py`、`check-py36-typingext-docker.sh`、`vendor-sync.py`；`gen-public-api-jump-imports.py` **保留**（justfile 注明另有编辑器/LSP 跳转用途）；`check-staged-sanitize.py` 保留（Stage B 处理）
- [x] 4.3 tests：删 `tests/governance/test_justfile_py36_checks_require_docker.py`；grep 清理其余 py36/vendor-sync 断言。DoD: `just check-only-py` 全绿且不再引用 docker py36

## 5. CI matrix — commit `ci: expand python matrix to 3.10-3.14 with layered checks`

- [x] 5.1 `ci.yaml`：matrix `["3.10","3.11","3.12","3.13","3.14"]`；matrix job 跑 `just check-only-py`；新增/改造一个 latest job 跑全量 `just qa` 兜底
- [x] 5.2 `publish-pypi.yaml`：确认 `just check-only-py` 步骤随 4.x 生效后无需 docker。DoD: workflow YAML 语法/动作版本检查通过

## 6. 说明面与生成物 — commit `docs: update python support policy to 3.10+ (README/AGENTS/checklist/benchmark wording)`

- [x] 6.1 根 `AGENTS.md`：Python runtime boundary 3.6 → 3.10；typing_extensions 条目改为「`Self`/`override` 直引，`typing-extensions>=4.4`」；Hard Rules 中 vendor 指针随 dataclassesx 退休修剪
- [x] 6.2 `llmanspec/AGENTS.md` 项目上下文：3.6 → 3.10；「主要依赖」行更新
- [x] 6.3 `README.md:111/199` 支持声明；`:170` 性能锚不动
- [x] 6.4 `docs/doc/dev/pre-release-checklist.md:32`；`docs/doc/benchmark/external-baseline.md` §4.4 措辞（历史数据/JSON 不动）
- [x] 6.5 `just gen-docs` 再生成；验收 = `just check-docs`（docs-drift-check）绿。生成物 SSOT/入口：`scripts/gen-docs.py`、`scripts/gen-readme-examples*`（经 `just gen-docs`）

## 7. 全量门禁收尾 — commit（如需）`qa: stage-a final gate fixes`

- [ ] 7.1 `just check-only-py` → `just qa`（含 examples / notebooks coverage / frontend-check）
- [ ] 7.2 `llman sdd validate --all --strict --no-interactive`
- [ ] 7.3 0.20.0 Breaking 清单初稿追加到 change 目录（release notes 汇总用）。DoD: qa 全绿，进入 `llman-sdd-verify`
