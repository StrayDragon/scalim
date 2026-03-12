# doc-governance Specification

**状态: ✅ 已实现**
## Purpose
定义仓库内文档的分层、生成边界(`*.gen.*` + `AUTOGEN` 注入区块)、统一生成入口与漂移门禁,以降低维护成本并防止“手工修改生成物/区块”导致的不一致.

## Related Code (as implemented)
- `AGENTS.md` (doc governance rules for agents)
- `scripts/gen-docs.py` (`--check` drift gate)
- `scripts/check-doc-governance.py` (consistency checks)
- `justfile` (`gen-docs`, `docs-drift-check`, `doc-governance-check`)
- `docs/doc/**/*.gen.md` (generated reference pages)

## Requirements
### Requirement: Generated doc artifacts are identifiable and non-editable
仓库 MUST 使用可机械识别的规则区分 “手工文档” 与 “生成文档/产物”,以避免漂移与误改:

- 任何**全文件生成物** MUST 在文件名中包含 `.gen.`(例如 `*.gen.md`/`*.gen.json`/`*.gen.yaml`)
- 全文件生成物 MUST 在文件头部包含“自动生成 + 生成入口(脚本或 just 目标)”提示
- 生成器 MUST 只写入其受控输出集合,不得覆盖手工维护文件

#### Scenario: `.gen.*` 文件带生成入口提示
- **WHEN** 仓库生成任意 `*.gen.md` 文档
- **THEN** 文件头部 MUST 包含“自动生成,请勿手动修改”与生成入口(脚本路径或 `just <target>`)

#### Scenario: 生成器不覆盖手工文件
- **WHEN** 开发者运行生成器
- **THEN** 生成器 MUST NOT 覆盖不包含 `.gen.` 且不在受控注入区块内的手工文档内容

### Requirement: Manual docs support deterministic injected blocks
系统 MUST 支持在手工 Markdown 文档内维护少量“必须与 SSOT 同步”的受控注入区块,并保证替换行为确定且可校验.

- 注入区块标记 MUST 使用:
  - `<!-- BEGIN AUTOGEN:<id> -->`
  - `<!-- END AUTOGEN:<id> -->`
- 生成器替换区块时 MUST 要求 begin/end 标记在目标文档中**精确匹配且仅出现一次**

#### Scenario: 标记区块可被精确替换
- **WHEN** 生成器刷新一个带 `BEGIN/END AUTOGEN` 的文档
- **THEN** 它 MUST 只替换该标记区块内部内容,并保持文档其它部分不变

#### Scenario: 标记缺失或重复时 fail-fast
- **WHEN** 目标文档缺失标记,或同一对标记出现多次
- **THEN** 生成器 MUST 失败并提示该标记不可被安全替换

### Requirement: Docs generation workflow is centralized
系统 MUST 为 docs-site 与仓库文档治理提供少量、稳定的生成入口,避免贡献者/agent 记忆多套命令.

#### Scenario: 单一入口覆盖全部受控输出
- **WHEN** 开发者运行文档生成入口(`just gen-docs`)
- **THEN** 所有受控 `*.gen.*` 与 `AUTOGEN` 注入区块 MUST 被一次性刷新到最新

### Requirement: Drift checks gate generated docs in QA
系统 MUST 提供 drift check 并在 `just qa`/CI 中强制执行,保证提交不会遗留过期生成物.

#### Scenario: 生成物漂移会导致 QA 失败
- **WHEN** 开发者修改 SSOT 但未更新对应 `*.gen.*` 或注入区块
- **THEN** drift check MUST 失败并提示运行对应生成入口

### Requirement: Repository guidelines document doc boundaries for agents
仓库 MUST 在 agent 指令文件中明确声明 doc governance 规则,以降低自动化修改时的风险.

#### Scenario: `AGENTS.md` 包含生成边界规则
- **WHEN** 维护者更新仓库级 `AGENTS.md`
- **THEN** 文档 MUST 包含对 `.gen.*` 文件与 `AUTOGEN` 注入区块的规则说明与生成入口提示

### Requirement: OpenSpec config includes doc governance writing rules
系统 MUST 在 `openspec/config.yaml` 中补充文档治理相关上下文与写作规则,确保后续 change 的 proposal/design/tasks 明确声明:
- 哪些文档是手工维护
- 哪些文档/区块是生成的
- 生成入口与漂移门禁是什么

#### Scenario: OpenSpec change 工件包含 doc ownership 信息
- **WHEN** 维护者创建一个涉及文档/规范变更的 OpenSpec change
- **THEN** 工件中的 tasks MUST 指明生成物的 SSOT 与生成入口(脚本或 `just` 目标)
