## Context

仓库已经具备若干“可长期维护”的文档最佳实践,但它们目前是**点状存在**,缺少统一的治理规范与工作流收敛:

- **全文件生成物**:
  - `src/scalim/dsl/by_yaml/schema/demand.gen.json` 由 `scripts/gen-yaml-dsl-schema.py` 生成并有 drift check。
  - `artifacts/skills/scalim-yaml-dsl/references/**/*.gen.*` 由 `scripts/gen-agent-skill.py` 生成并有 validate/drift 机制与 manifest。
- **手工文档的受控注入区块**:
  - `scripts/gen-yaml-dsl-schema.py` 会把 `src/.../schema_dsl/doc_texts.py` 中的片段同步注入 `docs/doc/yaml-dsl/user-guide.md` 的 `SCALIM-GEN` 区块。
  - `scripts/gen-agent-skill.py` 会向 `artifacts/skills/.../references/task-upgrade-legacy.md` 注入升级索引区块。
- **文档站点**:
  - 当前以 `docs/zensical.toml` 配置 Zensical 构建,内容根目录为 `docs/doc/`。
  - 站点中存在大量与 schema/CLI/规范强耦合的 reference 内容,需要多点同步,维护成本高。
- **说明/指令漂移风险**:
  - `AGENTS.md` / `CLAUDE.md` / `docs/doc/dev/repo-guide.md` 等存在同一事实的多处重复(例如 Python 版本边界),容易产生“文档说法 vs 仓库真实配置”不一致。

这次 change 的设计目标是把上述“局部最佳实践”升级为仓库级的**通用文档体系**,让贡献者与 agent 都能稳定判断:

1) 哪些内容必须手工维护,哪些必须生成;  
2) 该改哪里作为 SSOT;  
3) 改完后要跑什么生成/校验;  
4) CI 如何兜底防漂移。

## Goals / Non-Goals

**Goals:**
- 建立清晰的文档分层与责任边界(SSOT / generated / manual / injected-block)。
- 统一生成物命名与区块标记,让 agent “可机械判断”哪些文件/区块不可直接改。
- 让 docs-site 的 reference 类内容尽量可生成/可校验,把手工维护聚焦到 guide/叙事与排错决策。
- 把工作流收敛到少数入口命令(优先 `just gen` + 若干 check),并纳入 `just qa` 漂移门禁。
- 为后续 skill/prompt 的持续评测与调优(promptfoo 等)提供稳定的文档/产物边界。

**Non-Goals:**
- 不改动运行时行为;不引入新的 runtime 依赖。
- 不在本 change 内一次性重写/重排全部 `docs/doc/**`(只定义规则与迁移路径,具体迁移按 tasks 分期推进)。
- 不把 `openspec/specs/**` 原样纳入 docs-site(仍保持“规范与教程”的边界;只允许受控索引/引用)。
- 不承诺把所有手工文档都自动生成(目标是“成本可控的关键 reference 自动化”)。

## Decisions

### Decision 1: Doc Taxonomy + Ownership(分层与责任边界)

定义四类文档/产物,并强制每类只有一种推荐维护方式:

1) **SSOT(事实来源)**: 代码/配置/规范本体,例如:
   - `pyproject.toml`(版本/依赖/分发元数据)
   - `src/scalim/**`(schema meta、CLI help 文案、错误提示)
   - `openspec/specs/**/spec.md`(规范约束)
2) **Generated(全文件生成)**: 由脚本稳定重建且不允许手工改的产物:
   - 命名必须包含 `.gen.`(例如 `*.gen.json/*.gen.md/*.gen.yaml/*.gen.html`)
   - 文件开头必须包含生成提示(“自动生成,请勿手动修改 + 生成入口”)
3) **Manual(手工维护)**: 面向读者/贡献者的教程、决策指引、路由入口:
   - 允许引用 SSOT 与 generated,但不重复完整 reference(避免漂移)
4) **Manual + Injected Blocks(手工 + 受控注入区块)**:
   - 手工文档内允许存在少量“必须保持与 SSOT 同步”的区块,由脚本按标记替换
   - 统一使用 `<!-- BEGIN SCALIM-GEN:<id> -->` / `<!-- END SCALIM-GEN:<id> -->`

备选方案: 继续允许“任意文档都手工维护 + 口头约定同步”。  
拒绝原因: 已被历史证明会产生漂移,且 agent 很难稳定遵守。

### Decision 2: 统一生成边界的识别规则(让 agent 可遵守)

仓库级硬规则:

- **文件级**: 路径或文件名包含 `.gen.` 的文件视为 generated,agent MUST NOT 直接修改(除非用户明确要求),应改 SSOT 并运行生成器。
- **区块级**: 任何包含 `BEGIN/END SCALIM-GEN` 的区块视为 injected,agent MUST NOT 修改区块内部内容,应改 SSOT 并运行对应脚本刷新。
- **生成入口提示**必须可追溯(脚本路径或 `just` 目标),并尽量单一入口(避免多脚本互相覆盖)。

### Decision 3: docs-site 引入“受控 generated reference”

在不牺牲“站点 curated”的前提下,允许 `docs/doc/` 内存在受控 `*.gen.md` reference 页面,并要求:

- 这些页面必须由仓库脚本生成且纳入 drift check
- nav 中显式收录,避免“生成了一堆但没人知道/没被阅读”的无效成本
- 手工 guide 页面只做高层叙事/排错路径,引用 generated reference(一层直达),必要时用 injected blocks 注入小片段(例如字段列表、默认值表)

这意味着需要调整 `openspec/specs/docs-site/spec.md` 中“站点不包含 auto-generated 内容”的表述,把它收敛为:
> 不包含第三方/不受控生成物;允许并约束仓库脚本生成且受控校验的 reference 页面。

### Decision 4: 生成与校验工作流收敛(成本可控)

推荐把文档相关生成/注入收敛为两层入口:

- **生成入口**:
  - 继续复用现有 `just gen`(或新增 `just gen-docs` 并由 `just gen` 调用)
  - 任何新增 generated/reference 都必须接入该入口
- **漂移门禁**:
  - 引入 `docs-drift-check`(或把 docs 检查纳入现有 drift 框架),在 CI/`just qa` 中确保 generated/reference 不漂移

备选方案:
- 每个生成器各自独立,贡献者按经验记忆要跑哪些命令

拒绝原因:
- 经验式流程对 agent/新贡献者不友好,且极易漏跑导致 CI 反复失败。

### Decision 5: 维护方案对比(多方案)

为保证“可长期维护且成本可控”,给出三档方案,允许按阶段推进:

**方案 A: 规则化但不大规模生成(最低成本)**
- 仅补齐治理规范(AGENTS/openspec config/spec),统一 `.gen.` 与 `SCALIM-GEN` 规则
- 只做少量高漂移区块注入(例如 Python 版本边界/核心命令清单)

适合: 先把漂移风险降下来,不动 docs 结构。  
代价: docs-site 的 reference 仍偏手工,长期成本仍较高。

**方案 B: reference 自动生成 + guide 手工(推荐)**
- 在 `docs/doc/` 增加少量 `*.gen.md` reference 页面(从 schema/CLI/spec 索引生成)
- guide 页面改为“少量解释 + 一层直达链接 + 必要注入区块”
- 增加 drift check,把“reference 一致性”交给脚本与 CI

适合: 成本与收益平衡,能显著减少文档漂移与维护点。  
代价: 需要维护一个 docs 生成入口脚本与 nav/索引策略。

**方案 C: docs-as-code 大规模编译(最高一致性)**
- 将更多 doc 片段内置到代码/规范,站点大量由编译器组装
- 自动生成 nav/索引/交叉引用

适合: 组织规模大、变更频繁且必须极低漂移。  
代价: 工具链复杂,前期投入与后续维护都更高。

本 change 默认按 **方案 B** 设计 tasks,并保留 A/C 作为可选分支。

### Decision 6: prompt 评测/调优的落点(可选)

将 prompt 评测作为“文档体系”的旁路能力,不与运行时耦合:

- 评测对象优先覆盖:
  - 关键 skill 的触发与路由正确性
  - “generated vs manual 边界”相关的 agent 行为(不修改 `*.gen.*`,不篡改注入区块)
- 以 `just` 目标挂载,在 CI 中可作为可选 job(允许先手工跑,逐步升级为门禁)。

## Risks / Trade-offs

- [生成器增多导致维护复杂] → 收敛入口(`just gen[/gen-docs]`) + 约束输出边界(`.gen.`/marker) + drift check。
- [generated reference 与 guide 重复/冲突] → guide 只保留叙事与排错路径,reference 全部指向 generated。
- [docs-site 索引与 nav 维护负担] → 优先生成“少量关键 reference”,并把 spec/目录索引自动化(而不是自动生成全部页面)。
- [AGENTS/CLAUDE 等指令文件仍会漂移] → 引入 injected blocks 或单源生成策略,并加 check(至少对关键事实做一致性校验)。
- [把 generated 引入站点会放大 diff 噪音] → 强制确定性输出(排序/末尾换行/格式),必要时输出 manifest。

## Migration Plan

建议分 3 个阶段推进(每阶段都可独立合入并在 CI 中形成门禁):

1) **治理基线**: 落 `doc-governance` spec + 更新 `docs-site` spec + 更新 `AGENTS.md`/`openspec/config.yaml` 规则。
2) **生成入口与漂移门禁**: 新增 `gen-docs`/`docs-drift-check`(或并入现有流程),先覆盖最容易漂移的 reference(版本边界/核心命令/索引)。
3) **逐步搬迁 reference**: 从 YAML DSL/skill/docs-site 的高漂移章节开始,把“字段/枚举/默认值/CLI 清单/规范索引”迁移到 generated reference 或注入区块。

回滚策略:
- 任何生成器引入的输出均以 `.gen.*` 或 marker 区块为边界,可按文件/区块回滚,不影响运行时。
- 若 docs-site 引入 generated reference 产生阅读负担,可先从 nav 移除并保留文件用于内部 reference,不阻塞治理基线落地。

## Open Questions

- `AGENTS.md` 与 `CLAUDE.md` 的关系: 选“单源生成”还是“保留两份但注入关键事实区块 + check”?
- docs-site 中 generated reference 的目录布局: `docs/doc/_generated/` vs `docs/doc/generated/` vs 就地生成(与手工页面同级)?
- generated reference 的来源是否允许复用 `artifacts/skills/**/references/*.gen.md`(复制/二次生成),还是必须直接从 SSOT 生成两份输出?

