# language: zh-CN
# capability: governance-readme-examples
# purpose: 定义根 README 受控示例的公开页注入、图表资产与漂移校验；可执行 SSOT 位于 marimo README suite（见 examples-marimo），保证公开页与仓库真相一致（含本地 RSS 增量代理与版本锚定性能证据）。
# scope: README.md, notebooks/marimo

功能: governance-readme-examples

  @req:r980 @human
  场景: README copyable examples are injection-sourced
    - 根 `README.md` 中面向读者定位/复制的受控示例（至少包括最小 Python 示例、最小 YAML 示例、naive-vs-Scalim 对比示例）MUST 由可执行 SSOT 生成并经 `<!-- BEGIN AUTOGEN:<id> -->` / `<!-- END AUTOGEN:<id> -->` 注入；最小 YAML 示例 MUST 在 README 中显示由该 SSOT 派生的 YAML fence，并同时给出完整可运行 SSOT/loader 入口；投影 MAY 将仓内 loader module 替换为清楚标注的用户集成点（例如 `myapp.loaders`），但 MUST NOT 复制独立示例真相；最小 Python 示例 MAY 以源码链接/运行提示呈现；该 SSOT MUST 位于 `notebooks/marimo/example_readme_suite/`（或文档声明的等价路径）；维护者 MUST NOT 在受控注入区块外平行维护同一套可复制完整示例作为第二真相。

  @req:r981 @human
  场景: README example SSOT is runnable in QA
    - 系统 MUST 经由仓库 examples gate（`just examples` 或等价）执行 README suite 的 notebooks 侧章节 SSOT，并在 `just qa`（或等价 `check`）中强制覆盖；CI 固定小 scale 下 MUST 以退出码 0 表示章节跑通；失败时 MUST 非零退出并给出可定位摘要。专用 `readme-examples` 目标若保留，MUST 仅承担 drift/`--check` 或成为 examples 的薄别名，不得维持第二套执行真相。

  @req:r982 @human
  场景: Injection and chart assets have drift checks
    - 系统 MUST 提供 drift/`--check` 能力：当 README 受控注入区块内容或已提交的相对占比图资产与生成器输出不一致、或必需 AUTOGEN markers 缺失/重复时，门禁 MUST fail-fast，并提示运行对应生成入口（优先 `just gen-docs` / `just gen` 或文档声明的专用目标）。

  @req:r983 @human
  场景: Local RSS delta proxy demo with knobs and env notes
    - 系统 MUST 提供全假数据的 naive（内存不友好）与等价 Scalim 路径对比示例（SSOT 在 README marimo suite 章节内），暴露少量全局旋钮（如行数/字段数/批次大小）供本地调整；MUST 提交相对本地 RSS 增量代理图（SVG 或等价，`naive=1.0`）；该代理来自比较路径运行前后 RSS 差值，MUST NOT 称为 sampled peak；README 手工段 MUST 提供环境说明（至少：测量口径为相对增量代理、默认旋钮取值或指向旋钮 SSOT 的明确链接、非跨机绝对 MB / SLA 承诺、如何改旋钮重跑）。

  @req:r984 @human
  场景: Minimal Python and YAML examples are executable
    - 系统 MUST 提供最小可跑 Python 示例与最小可跑 YAML 示例（假数据/假 loader），二者 MUST 被 examples gate 覆盖且产出可断言的成功摘要（例如处理行数或写出成功）；MUST NOT 在 README 注入区保留 `NotImplementedError` 或不可执行占位作为官方示例。

  @req:r985 @human
  场景: CI does not hard-gate memory ratios
    - 运行门禁 MUST 以示例跑通与注入/资产漂移校验为硬失败条件；MUST NOT 仅因绝对内存 MB 或相对内存比值未达某阈值而使 `just qa` 失败。相对比值 MAY 被计算、写入图或本地输出，但不得作为本门禁的硬阈值。

  @req:r986 @human
  场景: Versioned benchmark claims stay bounded
    - 当根 README 展示历史性能数字或图表时，系统 MUST 从版本锚定的 benchmark 数据/发布页生成或链接该证据，并在 README 中同时说明版本、workload、环境/运行次数、正确性对拍与非保证边界；MUST NOT 将单次合成结果表述为通用加速、真实业务基准或跨机器 SLA。

  @req:r980 @human
  场景: 受控示例仅出现在注入区块
    - 必须成立：当 维护者检查根 README 中受控可复制完整示例；那么 这些示例 MUST 位于对应 AUTOGEN 注入区块内，最小 YAML MUST 显示由 SSOT 生成的 fence，且可由生成入口从 notebooks 侧 SSOT 刷新
    当 维护者检查根 README 中受控可复制完整示例
    那么 这些示例 MUST 位于对应 AUTOGEN 注入区块内，最小 YAML MUST 显示由 SSOT 生成的 fence，且可由生成入口从 notebooks 侧 SSOT 刷新

  @req:r980 @human
  场景: 禁止平行手写完整示例
    - 必须成立：当 受控区外出现与 SSOT 平行的完整可复制官方示例；那么 治理检查 MUST 失败或在设计钉死的等价规则下拒绝
    当 受控区外出现与 SSOT 平行的完整可复制官方示例
    那么 治理检查 MUST 失败或在设计钉死的等价规则下拒绝

  @req:r981 @human
  场景: qa经由examples覆盖readme套件
    - 必须成立：当 开发者运行 `just qa`；那么 MUST 经由 examples gate（或等价）执行 README marimo suite 章节，且在当前树默认 scale 下通过时整体不因此失败
    当 开发者运行 `just qa`
    那么 MUST 经由 examples gate（或等价）执行 README marimo suite 章节，且在当前树默认 scale 下通过时整体不因此失败

  @req:r981 @human
  场景: 示例失败非零退出
    - 必须成立：当 某一 README suite 章节抛错或断言失败；那么 examples gate MUST 非零退出并指出失败章节
    当 某一 README suite 章节抛错或断言失败
    那么 examples gate MUST 非零退出并指出失败章节

  @req:r982 @human
  场景: 注入漂移导致检查失败
    - 必须成立：当 开发者手改 AUTOGEN 区块内文且未重新生成；那么 drift/`--check` MUST 失败并提示生成入口
    当 开发者手改 AUTOGEN 区块内文且未重新生成
    那么 drift/`--check` MUST 失败并提示生成入口

  @req:r982 @human
  场景: 图资产漂移导致检查失败
    - 必须成立：当 已提交相对占比图与生成器输出不一致；那么 drift/`--check` MUST 失败
    当 已提交相对占比图与生成器输出不一致
    那么 drift/`--check` MUST 失败

  @req:r983 @human
  场景: 对比示例可改旋钮
    - 必须成立：当 读者修改 SSOT 全局旋钮并本地重跑；那么 对比路径 MUST 仍可执行并刷新相对占比产物（本地或经生成入口）
    当 读者修改 SSOT 全局旋钮并本地重跑
    那么 对比路径 MUST 仍可执行并刷新相对占比产物（本地或经生成入口）

  @req:r983 @human
  场景: 环境说明存在
    - 必须成立：当 读者阅读 README 本地 RSS 增量代理说明；那么 MUST 能看到运行前后相对增量代理的口径，并明确它不是 sampled peak、绝对 MB 或跨机保证
    当 读者阅读 README 本地 RSS 增量代理说明
    那么 MUST 能看到运行前后相对增量代理的口径，并明确它不是 sampled peak、绝对 MB 或跨机保证

  @req:r984 @human
  场景: 最小Python示例可跑
    - 必须成立：当 examples gate 执行最小 Python 章节；那么 MUST 成功完成假数据闭环并给出成功摘要
    当 examples gate 执行最小 Python 章节
    那么 MUST 成功完成假数据闭环并给出成功摘要

  @req:r984 @human
  场景: 最小YAML示例可跑
    - 必须成立：当 examples gate 执行最小 YAML 章节；那么 MUST 成功完成假数据闭环并给出成功摘要
    当 examples gate 执行最小 YAML 章节
    那么 MUST 成功完成假数据闭环并给出成功摘要

  @req:r985 @human
  场景: 相对比不作为硬闸
    - 必须成立：当 CI 上相对增量比因机器波动变化但仍跑通且无漂移；那么 `just qa` MUST NOT 仅因此失败
    当 CI 上相对增量比因机器波动变化但仍跑通且无漂移
    那么 `just qa` MUST NOT 仅因此失败

  @req:r986 @human
  场景: 历史性能数据有边界
    - 必须成立：当 读者阅读 README 的版本锚定性能段；那么 MUST 能定位版本化数据/发布页、workload 与环境边界、正确性对拍和非 SLA 声明
    当 读者阅读 README 的版本锚定性能段
    那么 MUST 能定位版本化数据/发布页、workload 与环境边界、正确性对拍和非 SLA 声明

  @req:r986 @human
  场景: 历史性能不被泛化
    - 必须成立：当 维护者更新 README 的历史 benchmark 摘要；那么 生成/检查结果 MUST 拒绝或测试覆盖任何把单次合成 A/B 写成通用性能保证的文案
    当 维护者更新 README 的历史 benchmark 摘要
    那么 生成/检查结果 MUST 拒绝或测试覆盖任何把单次合成 A/B 写成通用性能保证的文案
