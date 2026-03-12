## 1. 治理基线(规范 + 约束入口)

- [x] 1.1 将 `openspec/changes/doc-system-workflow/specs/doc-governance/spec.md` 同步为主规范: 新增 `openspec/specs/doc-governance/spec.md`
- [x] 1.2 按 delta 更新 `openspec/specs/docs-site/spec.md`(纠正 mkdocs.yml 叙述,允许受控 `*.gen.md`,并保持排除 specs/reports)
- [x] 1.3 更新 `openspec/config.yaml`: 增补 doc governance 上下文 + per-artifact rules(要求 proposal/design/tasks 写明 SSOT/生成入口/漂移门禁)
- [x] 1.4 精简并更新 `AGENTS.md`(SSOT): 只保留“硬规则 + 最小入口”,其余改为链接引用:
  - MUST 保留的硬规则: `src/scalim/` 的 Python 3.6 运行时边界、相对导入约定、runtime contract 规则、doc governance 边界(`*.gen.*` + `AUTOGEN:*`)、隐私规则
  - MUST 保留的最小入口: `just --list`、`just qa`、`just gen-docs`、`just openspec-check`
  - MUST 下沉并以链接替代的介绍性内容: “项目结构/目录索引/代码阅读地图”(迁移到 `docs/doc/getting-started/reading-guide.md`)
  - 所有与 `pyproject.toml`/`justfile` 等 SSOT 冲突的事实描述 MUST 删除或改为指向 SSOT 文件的链接
- [x] 1.5 落 `CLAUDE.md` 单源策略: `CLAUDE.md` MUST 为 `AGENTS.md` 的 symlink,并在 `quick-check-only-py`(因此也进入 `just qa`/CI) 中 gate
- [x] 1.6 将 `docs/doc/dev/repo-guide.md` 收敛为单链接页: 不再承载约定细节,只提供一个指向 `AGENTS.md` 的链接(避免与 SSOT 漂移)
- [x] 1.7 将项目结构/代码阅读地图从 `AGENTS.md` 下沉到站内文档: 更新 `docs/doc/getting-started/reading-guide.md` 承载“目录索引 + 入口”,并把 `AGENTS.md` 的结构介绍替换为指向该页的链接
- [x] 1.8 新增一致性检查(通过 `scripts/check-doc-governance.py` + `just doc-governance-check`):
  - `docs/doc/dev/repo-guide.md` 必须保持为“单链接页”(防止回退为重复维护)
  - `CLAUDE.md` MUST 为 `AGENTS.md` 的 symlink
  - 并纳入 `quick-check-only-py`

## 2. 生成入口收敛与漂移门禁

- [x] 2.1 定义 docs 生成入口: 新增 `scripts/gen-docs.py` 并提供 `just gen-docs`(由 `just gen` 调用);覆盖 `docs/doc/**/*.gen.md` + `AUTOGEN:*` 注入区块
- [x] 2.2 实现 docs drift check: 通过 `scripts/gen-docs.py --check` 对 `docs/doc/**/*.gen.md` 与受控注入区块提供失败机制与 diff,并给出明确修复提示(运行 `just gen-docs`)
- [x] 2.3 将 docs drift check 纳入 `quick-check-only-py`(因此也进入 `just qa`)并在 CI 强制执行
- [x] 2.4 为生成输出引入确定性约束(排序/末尾换行/格式化),避免无意义 diff

## 3. docs-site: 引入受控 generated reference(方案 B 的最小集)

- [x] 3.1 约定 generated reference 放置方式: “就地生成 + `.gen.md` 后缀”,并将以下页面显式加入 `docs/zensical.toml` 的 nav:
  - `yaml-dsl/schema-reference.gen.md`(标题: `YAML Schema 参考(生成)`)
  - `yaml-dsl/cli-reference.gen.md`(标题: `YAML CLI 参考(生成)`)
  - `specs/openspec-index.gen.md`(标题: `OpenSpec 索引(生成)`)
- [x] 3.2 从 YAML DSL schema 自动生成 reference 页面,输出为 `docs/doc/yaml-dsl/schema-reference.gen.md`
- [x] 3.3 从 CLI 实现自动生成 reference 页面,输出为 `docs/doc/yaml-dsl/cli-reference.gen.md`
- [x] 3.4 为 OpenSpec specs 生成“索引页”(仅索引/链接,不把 specs 当站点页面),输出为 `docs/doc/specs/openspec-index.gen.md`
- [x] 3.5 将 `docs/doc/yaml-dsl/syntax.md`、`docs/doc/yaml-dsl/user-guide.md` 等高漂移章节中的“纯 reference 段落”迁移到 generated reference 或注入区块,手工页面改为“叙事 + 一层直达链接”

## 4. 复用已有生成器能力(降低实现成本)

- [x] 4.1 复用策略: 不复制 skill 产物;抽取/复用渲染逻辑(共享 renderers),从同一 SSOT 分别生成 skill references 与 docs-site references(避免双份逻辑漂移)
- [x] 4.2 把 `src/scalim/dsl/by_yaml/schema_dsl/doc_texts.py` 的模式推广为通用约定(例如 `doc_texts.py`/`DOC_TEXTS`),并补齐文档片段如何进入站点/生成物的流程说明
- [x] 4.3 为注入区块替换逻辑提供统一 helper(避免多脚本各自实现正则替换导致边界不一致)

## 5. 验收

- [x] 5.1 运行并通过: `just gen-docs` + `just qa`
- [x] 5.2 运行并通过: `just docs-build`(站点可构建) + `just docs-serve`(本地可预览)
- [x] 5.3 运行并通过: `just openspec-check`
