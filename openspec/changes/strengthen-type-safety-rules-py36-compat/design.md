## Context

当前仓库的类型安全基础已经存在,但治理方式还不够系统:
- `basedpyright` 运行在 `pythonVersion = "3.6"` 前提下,这是非常重要的硬约束.
- `src/IMPL_ROOT/` 目前只强制 `reportArgumentType`、`reportReturnType`、`reportUnknownMemberType` 三项核心规则.
- `notebooks` 与 `src/IMPL_ROOT/cli` 由于动态边界较强,仍有大范围规则放宽.
- 现状中仍存在一批 `# type: ignore` 与广义关闭项;如果不先建立边界,每次“加强类型”都容易退化为局部修修补补.
- `just qa` 已经覆盖 lint、测试、`py36-compat-check`、`py36-typingext-check` 与 frontend 检查,因此 CI 里单独再跑一个 `py36` job 的收益很低,反而增加门禁重复与维护成本.

本 change 的目标不是立即把整个仓库推到 strict,而是先把“如何安全地继续收紧类型规则”定义清楚,让后续 implementation 可以按 phase 落地.

## Goals / Non-Goals

**Goals:**
- 在保持 Python 3.6 运行时兼容的前提下,定义一套可渐进收紧的静态类型治理方案.
- 明确哪些目录/模块默认进入更严格的类型策略,哪些动态边界可以继续采用受控放宽.
- 把类型债务(`Any` / `# type: ignore` / 全局 false 规则)从“隐式存在”变成“显式可审计”.
- 让 CI 的 QA 入口与本地开发入口对齐,减少重复的 `py3.6` 检查链路.

**Non-Goals:**
- 不把整个仓库一次性切到 strict.
- 不将 runtime 迁移到 Python 3.7+ 语法,不引入 `from __future__ import annotations`、PEP 604 union、内建泛型 `list[str]` 等对 `py3.6` 不友好的写法.
- 不要求 `notebooks`、`cli`、外部集成脚本在本 change 中立刻达到与核心库同等的严格度.
- 不改变用户侧公开 API 或 YAML DSL 语义.

## Decisions

### Decision: 采用“分层分区 + 逐批 ratchet”而不是一刀切 strict
- 方案 A: 直接对 `src/IMPL_ROOT/` 全量打开严格规则,把现有报错一次清空.
- 方案 B: 先定义 `strict-core` / `compatible-dynamic` / `tooling-boundary` 三类策略,对核心稳定模块先收紧,对动态边界保留受控放宽,后续再逐批推进.
- 方案 C: 暂不改规则,只记录类型债务清单与建议.
- 结论: 选择方案 B.
- 理由: 方案 A 风险最高,会把类型治理和运行时重构绑在一起;方案 C 几乎没有实际收口能力.分层 ratchet 既能继续前进,也能尊重 `py3.6` 与动态边界现实.

### Decision: 先把“新增核心模块默认更严格”定成规则,而不是只治理老文件
- 方案 A: 只清理存量热点文件,不约束新增模块.
- 方案 B: 为 `src/IMPL_ROOT/` 的稳定核心区设置更严格默认策略,新增模块默认落入该策略;只有明确的边界目录/文件才允许放宽.
- 结论: 选择方案 B.
- 理由: 如果没有默认策略,每次新增文件都会把类型债务重新引入,治理无法形成单向收口.

### Decision: 首批解除的规则以“缺失/未知类型”类为主
- Phase 1 首批优先考虑: `reportMissingParameterType`、`reportUnknownParameterType`、`reportUnknownArgumentType`、`reportUnknownVariableType`、`reportMissingTypeArgument`.
- 保持现有已开启规则: `reportArgumentType`、`reportReturnType`、`reportUnknownMemberType`.
- Phase 2 再评估: `reportIncompatibleMethodOverride`、`reportIncompatibleVariableOverride`、`reportUnnecessaryTypeIgnoreComment`.
- 理由: 第一批规则最有助于阻止“无声扩散的 Any/unknown”,同时不必立刻触碰所有 override 与清理性规则.

### Decision: suppression 必须尽量本地化、带原因、避免继续扩大 executionEnvironment 级别放宽
- 方案 A: 继续通过 executionEnvironment 大范围 `reportX = false` 消化噪声.
- 方案 B: 对动态边界保留少量目录级放宽,但 `src/IMPL_ROOT/` 内新增 suppression 优先使用带规则代码的 `# type: ignore[...]`、窄 helper seam、显式类型别名/Protocol/TypedDict/compat shim.
- 结论: 选择方案 B.
- 理由: 目录级大开关对收口最不友好,且难以审计真实问题;本地化 suppression 更便于后续继续削减.

### Decision: CI 以 `just qa` 为单一权威入口
- 方案 A: 继续保留主 QA job + 独立 `py36` job.
- 方案 B: 主 job 直接执行 `just qa`,删除重复的独立 `py36` job.
- 结论: 选择方案 B.
- 理由: `just qa` 已包含 `py36-compat-check` 与 `py36-typingext-check`;继续双跑不会提升覆盖面,只会增加维护成本与门禁漂移风险.

## Risks / Trade-offs

- [动态边界模块误报变多] → 通过分层策略与显式边界目录缓解,避免把 notebooks/cli 与核心库混为一谈.
- [首批规则开启后需要补较多注解] → 通过 phase 化推进,优先收紧稳定模块与低动态目录,不要一次覆盖全部热点.
- [为兼容 `py3.6` 而牺牲部分现代 typing 写法] → 接受该约束,统一继续使用 `typing` 旧语法与 `typing_extensionsx` shim.
- [CI 精简后担心漏掉单独 `py36` 检查] → 由 `just qa` 统一承载,并在 spec 中把这一点写成明确要求.

## Migration Plan

1. 盘点当前 `basedpyright` 关闭项、`src/IMPL_ROOT/` 中的 `# type: ignore` 与明显的 unknown/Any 热点.
2. 按目录划分 `strict-core`、`compatible-dynamic`、`tooling-boundary` 三类类型策略.
3. 在 `strict-core` 中开启 Phase 1 规则束,并通过局部注解、兼容 shim、窄 suppression 收口首批错误.
4. 保持 `just qa` 为唯一 CI QA 入口,删除重复 `py36` job,避免门禁定义分叉.
5. 在第一轮收口稳定后,再评估 Phase 2 规则是否可以继续解除.

## Open Questions

- `strict-core` 的首批目录边界是否直接覆盖 `spec/`、`planning/`、`utils/`、部分 `dsl` helper,还是先只覆盖最稳定的一小组模块?
- 是否需要增加一份机器可读的类型债务清单(例如统计 `# type: ignore` 或按规则分类的基线文件),帮助后续做 ratchet?
- tests 是否应该在后续独立 phase 中也引入最小类型约束,还是继续只把核心库作为强约束对象?
