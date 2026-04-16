## 1. Public Facade (`scalim.shortcuts.resources`)

- [ ] 1.1 创建稳定入口 package `src/scalim/shortcuts/resources/`（Python 3.6 兼容）,包含 `__init__.py` 与 v1 子域模块 `outputs.py`
- [ ] 1.2 在 `scalim.shortcuts.resources.outputs` 提供 v1 的 outputs discovery：`load_latest_outputs/try_load_latest_outputs` 与 `latest_book_path/latest_file_path`（或等价命名）
- [ ] 1.3 定义稳定数据结构（例如 `LatestOutputs` dataclass;字段包含 `run_id/books/files`）并用 `__all__` 固定导出面（避免泄露内部实现）
- [ ] 1.4 实现 facade: 输入 output root,输出 books/files 的 `Path` 映射；调用方不需要读 `latest.json` 或拼接 `versions/<id>` 路径
- [ ] 1.5 明确缺失语义：fail-fast API 提供可诊断错误；`try_*` API 缺失时返回 `None`

## 2. Tests

- [ ] 2.1 为 `scalim.shortcuts.resources.outputs` 增加单测覆盖：happy path（books+files）、仅 books、仅 files、缺失 latest、latest/manifest 解析失败
- [ ] 2.2 增加回归用例确保 facade 不要求调用方了解内部目录结构（测试中禁止手写 `versions/` 拼接作为 oracle）

## 3. Public API Governance

- [ ] 3.1 将 `scalim.shortcuts.resources` 纳入 curated public entrypoints（SSOT: `openspec/specs/public-api-surface-governance/spec.md`; 变更按 delta spec 落地）
- [ ] 3.2 更新 public API 文档页以展示新入口（SSOT: public API catalog/`__all__`; 若页面为生成物则运行 `just gen-docs` 刷新,禁止手改任何 `*.gen.*` 或 injected block 内部）
- [ ] 3.3 运行 public surface gates：`python3 scripts/check-api-surface-governance.py --check` 与 `python3 scripts/check-user-material-import-boundaries.py --check`

## 4. Marimo Public API Suite

- [ ] 4.1 新增 public API suite 章节（例如 `notebooks/marimo/example_public_api_suite/chapters/ch165_public_api_resources.py`）覆盖 `scalim.shortcuts.resources` 与 `scalim.shortcuts.resources.outputs` 的稳定导入与最小行为示例
- [ ] 4.2 将新章节加入 `tests/public_api/test_example_public_api_suite.py` 的 `chapter_ids` 列表,确保 pytest gate 覆盖
- [ ] 4.3 更新 suite 规范覆盖（SSOT: `openspec/specs/marimo-example-public-api-suite/spec.md`; 变更按 delta spec 落地）
- [ ] 4.4 验收: `just examples` 通过并输出可定位 summary

## 5. Skills / Docs Example Updates

- [ ] 5.1 更新版本化输出参考文档示例为 facade 写法（SSOT: `agentdev/skills/scalim-yaml-dsl/references/task-workflow-versioned-outputs.md`；手工维护,非生成物）
- [ ] 5.2 确保 docs/skills/notebooks 不再出现“手写读取 `<root>/manifest/latest.json` + 拼路径”作为官方推荐写法（验收: `scripts/check-user-material-import-boundaries.py --check` + 人工 review）

## 6. Change QA

- [ ] 6.1 运行 `just openspec-check` 确保 sanitize + specs 校验通过
- [ ] 6.2 运行 `just qa` 确保 lint/tests/drift gates 全通过
