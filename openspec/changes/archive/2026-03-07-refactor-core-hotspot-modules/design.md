## Context

本次重构针对的是一组已经被明确识别的“职责聚合型热点模块”,而不是单点功能缺陷.这些模块分布在 3 条主线:

1. DSL runtime / validator
   - `config_parsing/validators/fields.py`
   - `runtime/conversion.py`
2. hooks / observability / visualization
   - `hooks/base.py`
   - `ob/manager.py`
   - `ob/presets/viz.py`
3. adaptive execution
   - `execution/adaptive/loadref_scheduler.py`

现有实现的共通优点是测试较强、行为稳定;现有实现的共通问题是单文件长期承载多种职责.因此本次 change 的核心设计不是改行为,而是为“一次性完成结构治理”建立统一边界.

## Goals / Non-Goals

**Goals:**
- 用单个 change 覆盖所有已确认热点模块的结构重构 phase,形成统一评审基线.
- 对每个热点明确职责拆分方向,但保持现有稳定入口与外部行为语义不变.
- 在实施阶段优先依赖测试保护:导入稳定性、pickle/lock 恢复、线程安全、事件顺序、viz 输出与 adaptive 提交顺序必须可回归验证.
- 保持 Python 3.6 兼容与现有 typing compat 入口约束.

**Non-Goals:**
- 不新增新的终端用户功能或新的 DSL 字段.
- 不改变公共运行入口的推荐路径.
- 不借本次重构顺手改变事件语义、输出语义或并行默认值.
- 不把这次 change 扩展到所有热点之外的普通模块清理.

## Decisions

### Decision: 使用“单 change + 多实施 phase”而不是“多个独立 change”
- 备选 A: 为每个热点单独建 change.
- 备选 B: 用一个 change 聚合所有热点,在任务层做 phase 划分.
- 结论: 选择 B.
- 理由: 团队已经明确希望“一次重构”;多个 change 会增加 review 与范围对齐成本.

### Decision: 每个热点都采用“稳定 facade + 内部职责子模块”模式
- 对外保持现有稳定入口和导入路径.
- 对内按职责拆分子模块,不要求所有热点都转换成 package,但必须能清楚地区分职责边界.
- 理由: 最小化用户侧迁移成本,同时避免继续把复杂逻辑堆在单文件里.

### Decision: DSL runtime / validator 的拆分边界
- `validators/fields.py` 优先按字段规则类别拆分,例如字段通用校验、output 字段规则、relations 关联字段约束、issue 收集/格式化辅助.
- `runtime/conversion.py` 优先按 registry/lookup cast、source/field/relation 转换、运行请求映射拆分.
- 稳定入口仍保留在 `config_parsing.validator`、`config_parsing.loader`、`runtime.*` 既有路径.

### Decision: hooks / observer / viz 的拆分边界
- `hooks/base.py` 拆为 hook 协议/基类、订阅注册管理、dispatch 缓存策略.
- `ob/manager.py` 拆为 observer 注册管理、wants / handler cache、capture / replay 状态辅助.
- `ob/presets/viz.py` 拆为配置与路径解析、事件映射/建模、快照元数据增强、文件写入.
- 稳定入口保持不变,避免调用方改导入路径.

### Decision: adaptive scheduler 的拆分边界
- `loadref_scheduler.py` 拆分为策略/worker 数解析、layer planning、任务提交、结果聚合/提交顺序维护.
- 必须继续保持相同输入下的输出顺序、事件回放顺序与错误语义.
- 优先复用已存在的 `execution/adaptive/*_unit.py` 方向,而不是重新发明新的杂合入口.

### Decision: 结构重构必须由测试先行保护
- 每个子线都必须先补或整理保护性测试,再做内部迁移.
- 重点保护: 稳定导入路径、pickle roundtrip、线程安全、viz 产物一致性、adaptive 提交顺序.

## Risks / Trade-offs

- [范围过大] → 通过在 tasks 中按三条主线拆 phase,并要求每 phase 独立可验证来控制风险.
- [单 change review 面较大] → 在 design 与 tasks 中明确每条子线边界,减少实现阶段范围漂移.
- [保持稳定入口导致短期 facade 与内部模块并存] → 接受该成本,换取更低的迁移风险.
- [重构引发隐藏行为回归] → 对线程安全、pickle、事件顺序、viz 产物与 adaptive 顺序补强测试.
- [Python 3.6 兼容被现代化改动破坏] → 在实现阶段继续跑现有 `py36` 兼容检查与 `typing-extensions==4.1.1` 隔离验证.

## Migration Plan

1. 建立或整理所有热点对应的保护性测试.
2. 先完成 DSL runtime / validator 拆分.
3. 再完成 hooks / observer / viz 拆分.
4. 最后完成 adaptive scheduler 拆分.
5. 每一条主线完成后都运行对应测试;最终统一运行 `openspec validate --all --strict --no-interactive` 与仓库质量门禁.

## Open Questions

- `ob/presets/viz.py` 是否需要直接转为 package,还是先保留模块入口并抽内部 helper 即可?
- `validators/fields.py` 的最佳拆分粒度是按规则类别还是按 output / non-output 责任域?
- `loadref_scheduler.py` 拆分时,是否需要把现有 `_unit.py` 进一步收束为更清晰的 facade?
- 是否需要在本次 change 中额外增加新的模块布局测试,覆盖更多热点模块的稳定入口承诺?
