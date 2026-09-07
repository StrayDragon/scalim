# Design: Stage A 现代基线

## 关键设计决策

| 决策点 | 结论 | 理由 |
|---|---|---|
| 切换方式 | **一次切换，无双运行期**（0.20.0 单版本 breaking，ROADMAP） | 兼容层无共存价值；`vendor/compact` re-export 与 stdlib/`typing_extensions` 直引不双写 |
| codemod 载体 | 一次性确定性脚本（逐行解析 imported names 后映射），置于 `.tmp/` **不提交** | 可重复执行、可审 diff；产物（改写后的 import）才是 SSOT |
| `StrEnum` 落点 | `src/scalim/_internal/strenum.py`（CPython 3.11 backport 原样迁移 + ratchet 注释） | floor 3.10 仍需；`_internal` 与 Stage C 迁址后的 `importlibx` 同层 |
| `Self`/`override` 落点 | 直接 `from typing_extensions import Self, override`（pin `>=4.4`），删 banned-api 禁令 | typing_extensions 成为正常依赖而非「需集中转发」的兼容层；r183 已按此改写 |
| ruff UP autofix 策略 | `--fix --select UP`（不用 `--unsafe-fixes`），src → packages → tests 分批；**禁止引入** `from __future__ import annotations` | floor 3.10 下 modern eager 语法（`list[]`/`X \| None`）运行时安全；future-annotations 会改变注解求值时机，侵入面不可控 |
| `_PY38_PLUS` 收拢 | 删 `ast.Str`/`ast.Num`/`ast.Bytes` 分支，仅保留 `ast.Constant` | 3.10 下旧 AST 节点已废弃且 deprecated 警告；行为面等价（这两种字面量解析结果相同） |
| py36 工具链删除边界 | 删 `py36-compat-check`/`py36-typingext-check`/`gen-public-api-jump-imports.py`；**保留** `check-staged-sanitize.py`（依赖 `vendor.yamlx.yaml`，Stage B 处理） | 最小爆炸半径；YAML 面本 change 不动 |
| CI 分层 | matrix（3.10–3.14）各跑 `just check-only-py`；latest 追加全量 `just qa` | 用户拍板（D1）：matrix 只跑 py 检查 + qa 兜底，控制总耗时 |

## 文档/生成边界（Artifact 规则）

- **手工 SSOT**：`pyproject.toml`、`justfile`、`scripts/*`、`.github/workflows/ci.yaml`、根 `AGENTS.md`、`llmanspec/AGENTS.md`、`README.md`、`docs/doc/dev/pre-release-checklist.md`、`docs/doc/benchmark/external-baseline.md`（§4.4 仅措辞）。
- **生成物（禁手改）**：`docs/doc/getting-started/public-api.gen.md`、`docs/doc/specs/llmanspec-index.gen.md` 等 `.gen.` 文件——入口 `just gen-docs`；`frontend/**/src/generated/project_constants.ts` 本 change 不触及（版本号不变）。
- **injected blocks**：本 change 不触碰任何 `AUTOGEN` 区块。

## Drift gate

- specs：`llman sdd validate --all --strict --no-interactive`（每次工件改动后）+ `just llmanspec-check`。
- docs：`just gen-docs` 后由 `docs-drift-check`（`just qa` 内）兜底。
- 行为：`just check-only-py` → `just qa`（100% 覆盖 test-gate + examples + frontend）；YAML 语义由 `test_yaml_backend_migration.py` golden corpus 守护（本 change 不触及 yamlx）。

## 风险与回滚

- 单分支线性提交（`sdd/c52-modernize-py310-baseline`），每个 task 一个 commit，可逐 commit revert。
- 最大风险点：ruff UP autofix 后 basedpyright strict 集合波动 → task 3 独立成 commit，失败即单独回滚该 commit，不影响配置面/codemod。
- `StrEnum` 行为等价性：backport 即 CPython 3.11 实现，`StrEnum` 成员语义（`str` 子类 + `auto()` 小写）不变；既有 Policy SSOT 测试覆盖。
