# language: zh-CN
# capability: governance-docs
# purpose: 定义仓库内文档的分层、生成边界(`*.gen.*` + `AUTOGEN` 注入区块)、统一生成入口与漂移门禁,以降低维护成本并防止”手工修改生成物/区块”导致的不一致. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: governance-docs

  @req:r47 @human
  场景: Generated doc artifacts are identifiable and non-editable
    - 仓库 MUST 使用可机械识别的规则区分 “手工文档” 与 “生成文档/产物”,以避免漂移与误改: - 任何**全文件生成物** MUST 在文件名中包含 `.gen.`(例如 `*.gen.md`/`*.gen.json`/`*.gen.yaml`) - 全文件生成物 MUST 在文件头部包含”自动生成 + 生成入口(脚本或 just 目标)”提示 - 手工页中的受控注入区块 MUST 使用 `<!-- BEGIN AUTOGEN:<id> -->` / `<!-- END AUTOGEN:<id> -->` markers - 生成器 MUST 只写入其受控输出集合,不得覆盖手工维护文件

  @req:r291 @human
  场景: Manual docs support deterministic injected blocks
    - 系统 MUST 支持在手工 Markdown 文档内维护少量“必须与 SSOT 同步”的受控注入区块,并保证替换行为确定且可校验. - 注入区块标记 MUST 使用: - `<!-- BEGIN AUTOGEN:<id> -->` - `<!-- END AUTOGEN:<id> -->` - 生成器替换区块时 MUST 要求 begin/end 标记在目标文档中**精确匹配且仅出现一次**

  @req:r415 @human
  场景: Docs generation workflow is centralized
    - 系统 MUST 为 docs-site 与仓库文档治理提供少量、稳定的生成入口,避免贡献者/agent 记忆多套命令.

  @req:r510 @human
  场景: Drift checks gate generated docs in QA
    - 系统 MUST 提供 drift check 并在 `just qa`/CI 中强制执行,保证提交不会遗留过期生成物.

  @req:r587 @human
  场景: Repository guidelines document doc boundaries for agents
    - 仓库 MUST 在 agent 指令文件中明确声明 doc governance 规则,以降低自动化修改时的风险.

  @req:r644 @human
  场景: OpenSpec config includes doc governance writing rules
    - 系统 MUST 在 `llmanspec/config.yaml` 中补充文档治理相关上下文与写作规则,确保后续 change 的 proposal/design/tasks 明确声明: - 哪些文档是手工维护 - 哪些文档/区块是生成的 - 生成入口与漂移门禁是什么

  @req:r987 @human
  场景: README validated examples cross-reference
    - 根 `README.md` 受控可复制示例与相对占比图的注入/漂移规则 MUST 以 `governance-readme-examples` 为公开页合约 SSOT；可执行章节 SSOT 与 examples gate 覆盖 MUST 交叉引用 `examples-marimo`（README marimo suite）。本 capability 仅要求：其注入区块与生成入口遵守本文件的 AUTOGEN/`.gen.`/集中生成与 drift 通例，并在文档/agent 指引中可被发现，不得在本文件重复定义第二套 README 示例语义。
  @req:r47 @human
  场景: gen-文件带生成入口提示
    - 必须成立：当 仓库生成任意 `*.gen.md` 文档；那么 文件头部 MUST 包含“自动生成,请勿手动修改”与生成入口(脚本路径或 `just <target>`)
    当 仓库生成任意 `*.gen.md` 文档
    那么 文件头部 MUST 包含“自动生成,请勿手动修改”与生成入口(脚本路径或 `just <target>`)

  @req:r47 @human
  场景: 生成器不覆盖手工文件
    - 必须成立：当 开发者运行生成器；那么 生成器 MUST NOT 覆盖不包含 `.gen.` 且不在受控注入区块内的手工文档内容
    当 开发者运行生成器
    那么 生成器 MUST NOT 覆盖不包含 `.gen.` 且不在受控注入区块内的手工文档内容
  @req:r291 @human
  场景: 标记区块可被精确替换
    - 必须成立：当 生成器刷新一个带 `BEGIN/END AUTOGEN` 的文档；那么 它 MUST 只替换该标记区块内部内容,并保持文档其它部分不变
    当 生成器刷新一个带 `BEGIN/END AUTOGEN` 的文档
    那么 它 MUST 只替换该标记区块内部内容,并保持文档其它部分不变

  @req:r291 @human
  场景: 标记缺失或重复时-fail-fast
    - 必须成立：当 目标文档缺失标记,或同一对标记出现多次；那么 生成器 MUST 失败并提示该标记不可被安全替换
    当 目标文档缺失标记,或同一对标记出现多次
    那么 生成器 MUST 失败并提示该标记不可被安全替换
  @req:r415 @human
  场景: 单一入口覆盖全部受控输出
    - 必须成立：当 开发者运行文档生成入口(`just gen-docs`)；那么 所有受控 `*.gen.*` 与 `AUTOGEN` 注入区块 MUST 被一次性刷新到最新
    当 开发者运行文档生成入口(`just gen-docs`)
    那么 所有受控 `*.gen.*` 与 `AUTOGEN` 注入区块 MUST 被一次性刷新到最新
  @req:r510 @human
  场景: 生成物漂移会导致-qa-失败
    - 必须成立：当 开发者修改 SSOT 但未更新对应 `*.gen.*` 或注入区块；那么 drift check MUST 失败并提示运行对应生成入口
    当 开发者修改 SSOT 但未更新对应 `*.gen.*` 或注入区块
    那么 drift check MUST 失败并提示运行对应生成入口
  @req:r587 @human
  场景: 仓库级-agent-指令包含生成边界规则
    - 必须成立：当 维护者更新仓库级 agent 指令；那么 文档 MUST 包含对 `.gen.*` 文件与 `AUTOGEN` 注入区块的规则说明与生成入口提示
    当 维护者更新仓库级 agent 指令
    那么 文档 MUST 包含对 `.gen.*` 文件与 `AUTOGEN` 注入区块的规则说明与生成入口提示
  @req:r644 @human
  场景: llmanspec-change-工件包含-doc-ownership-信息
    - 必须成立：当 维护者创建一个涉及文档/规范变更的 llmanspec change；那么 工件中的 tasks MUST 指明生成物的 SSOT 与生成入口(脚本或 `just` 目标)
    当 维护者创建一个涉及文档/规范变更的 llmanspec change
    那么 工件中的 tasks MUST 指明生成物的 SSOT 与生成入口(脚本或 `just` 目标)

  @req:r644 @human
  场景: 新增生成物必须满足约定
    - 必须成立：当 新增一个生成物文件；那么 必须满足上述命名/marker 约定,否则 gate MUST fail-fast
    当 新增一个生成物文件
    那么 必须满足上述命名/marker 约定,否则 gate MUST fail-fast
  @req:r987 @human
  场景: README示例合约可发现
    - 必须成立：当 维护者查找 README 受控示例的行为合约；那么 MUST 能定位到 `governance-readme-examples`（注入/图）与 `examples-marimo`（套件/gate），且本 capability 不重复定义其示例语义
    当 维护者查找 README 受控示例的行为合约
    那么 MUST 能定位到 `governance-readme-examples`（注入/图）与 `examples-marimo`（套件/gate），且本 capability 不重复定义其示例语义
