## Context

`notebooks/marimo/demo_big_data_report/` 是仓库的唯一主线教程与 examples gate 的确定性回归入口，但当前存在三类结构性问题：

1) **教学视角不收敛**：主线章节混入 IR/Plan 等底层视角，读者需要先理解内部实现才能写 YAML；维护者也更容易把章节写成“内部实现导读”，而不是“工程使用方的真实路径”。
2) **YAML 能力覆盖不可审计**：YAML DSL 的 schema/validator 在持续演进，但 demo 缺少一份以最新 schema 为准的覆盖矩阵（schema → 场景/YAML/断言）。这会导致“功能存在但示例不覆盖/不对拍”的 drift。
3) **回归覆盖与主线叙事耦合**：public API `__all__` 覆盖章节被塞进 `demo_big_data_report` 主线，导致主线章节必须承担 coverage 义务，叙事被破坏且长期维护成本上升。

关键约束：

- **不改变** canonical YAML SSOT 路径（至少 `by_yaml_dsl/ecommerce_report.yaml` 与 fragments 路径不变）。
- 本变更不引入新的 YAML DSL runtime/schema 能力；只做示例组织/场景/对拍/治理的收敛。
- YAML `imports/$import` 仍处于 V1 约束（同目录 fragments）；场景拆分需要按目录隔离复用片段。
- 所有纳入 `just examples` 的章节必须 deterministic，并提供 oracle（纯 Python 真值优先；必要时固定 fixtures）。

## Goals / Non-Goals

**Goals:**

- 将 `demo_big_data_report` 主线收敛为 **YAML DSL 场景化教程**：每章必须有背景/需求方需求/方案取舍/对拍断言。
- 建立 `by_yaml_dsl/` 下的“互联网常见数据场景库”第一版：电商（扩展现有）、广告、客服，并纳入 examples gate。
- 引入 **capability coverage matrix**（以 `demand.gen.json` / `workflow.gen.json` 为基准）作为示例治理入口。
- 将 public API `__all__` 覆盖与扩展点演示迁移到独立 suite，但继续纳入 `just examples` 门禁。

**Non-Goals:**

- 不新增/修改 YAML DSL schema、validator、runtime 行为（除非为保持示例可运行必须修复明显 bug；该类修复需单独提 change）。
- 不构建面向数据分析同学的生产管线/数据平台集成。
- 不引入新的重型依赖（示例仍以合成确定性数据为主）。

## Decisions

### 1) Suite 拆分：主线教学 vs public API 覆盖

- 保留 `notebooks/marimo/demo_big_data_report/` 作为唯一主线教学套件（YAML-first）。
- 新增独立 suite（暂定 `notebooks/marimo/example_public_api_suite/`），承载：
  - `scalim.*` 稳定公开入口模块 `__all__` 的 100% 覆盖断言
  - hooks/observer/events/components 注入等扩展点演示
- `notebooks/marimo/run_examples.py` 升级为多 suite runner：默认运行两套 suite，并支持 `--suite/--chapter/--list` 等能力保持可定位性。

动机：
- 主线章节不再被 coverage 任务绑架；public API 覆盖可独立演进且仍保持门禁强度。

### 2) YAML 场景库组织：按 domain 目录隔离 + 同目录 fragments

为满足 imports V1 “同目录 fragments” 约束，场景库按 domain 建目录：

- `by_yaml_dsl/ecommerce_*.yaml`（保留现有 ecommerce SSOT 文件在根目录；扩展时新增同目录文件）
- `by_yaml_dsl/ads/`：ads demand/workflow/fragments 均放同目录
- `by_yaml_dsl/support/`：support demand/workflow/fragments 均放同目录

workflow 如需跨目录引用 demand，统一通过 `path_aliases`（如已有 `@` → repo_root）引用绝对 repo 路径，避免相对路径脆弱。

### 3) “每章像人类一样”的叙事模板

每个纳入 gate 的章节 notebook 顶部必须包含以下结构（markdown + 少量 UI 展示即可）：

- **背景**：业务系统/数据源/痛点（1–2 段）
- **需求方提问**：用自然语言描述需求（例如 PM/运营/风控提出）
- **方案选择**：为什么用 YAML DSL；本章覆盖哪些 DSL 能力；为什么不选其它方案
- **对拍点**：本章 oracle 是什么（纯 Python / fixtures）；失败如何定位

该模板是治理要求：避免章节变成“实现导读/概念堆砌”。

### 4) 对拍策略：纯 Python 真值优先，fixtures 为补充

- 行级明细：优先复用 `scalim_misc` 的纯 Python 对照组生成逻辑。
- 聚合/多输出/失败策略（`failure_policy` 等）：通过构造“可控的错误”场景做断言（例如非主 output 的 aggregate guardrail 触发 error）。
- workflow 产物：以输出文件路径为主契约，必要时对 CSV 进行稳定字段/行数/内容校验；大型二进制（xlsx）只做结构性断言（存在/工作表名/可读性），避免 flaky。

### 5) coverage matrix：以 schema 为准的可维护 SSOT

新增一个可检查的矩阵文件（位置 TBD，建议 `notebooks/marimo/demo_big_data_report/by_yaml_dsl/coverage_matrix.md`）：

- 以 `src/scalim/dsl/by_yaml/schema/demand.gen.json` 与 `workflow.gen.json` 为准
- 每个关键域/definition 至少映射到一个“覆盖 YAML + 覆盖章节 + 对拍断言”
- 后续可增量引入 drift check（例如脚本抽取 schema keys 与矩阵比对），但第一版先手工维护以降低引入成本

## Risks / Trade-offs

- **示例数量增加导致 gate 变慢** → 通过小规模 deterministic 合成数据（small config）与分层（主线必跑/重场景可选）控制时长。
- **imports V1 限制导致 fragments 重复** → 通过按 domain 目录隔离，并在每个 domain 内用 `$import`/anchors 复用，避免跨目录复用依赖新能力。
- **public API suite 迁出会触发 spec/测试/coverage 漂移** → 通过同步修改 OpenSpec specs + 更新 `scripts/gen-marimo-coverage.py` + 更新 pytest gate 约束，确保单一事实来源。

## Migration Plan

1) **创建新 suite**：落地 `example_public_api_suite/` 并迁移现有 public_api_* 章节；更新 runner 与 pytest gate。
2) **更新 OpenSpec specs**：修改 `testing-quality` 与 `marimo-demo-big-data-report-chapters` 的要求，使其匹配新的 suite 边界。
3) **重排主线章节**：移除 IR/Plan 章节；将保留章节改为场景化 YAML-first 叙事；新增 ads/support 章节。
4) **补齐场景库 YAML**：新增 ads/support 的 demand/workflow/fragments 与 loader/oracle；补齐 demand 顶层能力与 observability 子域覆盖缺口。
5) **新增 coverage matrix** 并把维护入口写入主线与 docs。
6) 跑 `just examples` / `just qa`，并执行 `just openspec-check` 确保工件与规范通过。

## Open Questions

- ads/support 场景第一版的复杂度上限：每个 domain 是“一份大 YAML”还是“多份小 YAML + workflow 编排”更利于学习与维护？
- 对拍 fixtures 的边界：哪些产物（例如 xlsx）只做结构性断言，哪些必须做内容级对拍？

