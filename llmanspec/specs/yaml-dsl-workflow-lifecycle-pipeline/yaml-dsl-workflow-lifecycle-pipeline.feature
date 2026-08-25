# language: zh-CN
# capability: yaml-dsl-workflow-lifecycle-pipeline
# purpose: 定义 workflow 生命周期显式阶段管线（phase pipeline）：structural preload 保持 parser-only、overrides 合并、effective outputs/resources 驱动的 preflight diagnostics、确定性的 fail-fast 顺序。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: yaml-dsl-workflow-lifecycle-pipeline

  @req:r131 @human
  场景: workflow runtime MUST implement a lifecycle pipeline with explicit phase results
    - 系统 MUST 将 workflow 的生命周期实现为一组显式阶段（phase pipeline），并为每个阶段提供可被测试消费的阶段结果对象（phase result），以便： - 将阶段顺序变成 SSOT（避免多入口各自拼装导致 drift） - 使边界约束“靠数据结构表达”（早期阶段结果不暴露后期阶段所需信息） - 让单测可以在不启动 engine 的情况下覆盖 boundary 行为

  @req:r373 @human
  场景: structural preload MUST remain parser-only and MUST NOT consume runtime-only dia
    - workflow 对 runs 的结构预加载（preload/compile）MUST 只消费结构信息（outputs/resources/dependency wiring），并且 MUST NOT 运行任何依赖 effective runtime policy 的 diagnostics。

  @req:r492 @human
  场景: structural preload MUST reuse the same demand-YAML parse settings as runtime ent
    - workflow structural preload 会解析 demand YAML，因此系统 MUST 复用与 runtime entrypoints 一致的解析设置（至少包含 template 预编译的 `rendered_yaml_max_len` 与 `allowed_yaml_roots`），避免“preload 与 runtime compile 对同一 demand YAML 得出不同结论”的漂移。

  @req:r571 @human
  场景: effective options/resources merge MUST be the earliest policy-aware boundary for
    - 系统 MUST 将 overrides、workflow resources overlay 与 per-run patch 合并为 per-run effective options/resources，并将该合并结果作为 inferable runtime-only diagnostics 的最早输入边界： - pipeline MUST 在 preflight 前完成 effective merge - preflight MUST 仅基于 effective merge 口径决定是否触发某个 inferable check

  @req:r633 @human
  场景: inferable diagnostics trigger conditions MUST be evaluated using effective outpu
    - 系统 MUST 以 effective outputs/resources 的口径来判断 inferable runtime-only diagnostics 是否触发（不得按原始 YAML 口径抢跑），否则会出现 override 后不再冲突/反之的误报或漏报。

  @req:r679 @human
  场景: preflight MUST be deterministic and fail-fast on the first error
    - 为保证可维护与可调试，系统 MUST 以确定性顺序执行 preflight，并在发现第一个错误时立即中止： - runs MUST 按 workflow 声明顺序（decl_order）执行 - 每个 run 的 checks MUST 按 registry 顺序执行 - 遇到第一个错误 MUST 立即 raise（不得聚合多个 run 的错误）

  @req:r719 @human
  场景: preflight and runtime compile MUST share a SSOT helper for effective outputs/res
    - 为避免 drift，系统 MUST 将 effective outputs/resources 的关键触发判定（例如是否会写 `header_fields_output_by=name` 的 header）收敛为单一 SSOT helper，并由： - workflow preflight 使用 - demand runtime compile（或其 diagnostics runner）使用
  @req:r131 @human
  场景: pipeline-can-be-executed-up-to-preflight-without-starting-th
    - 必须成立：假如 一份合法的 workflow YAML；当 测试仅执行 pipeline 到 preflight 阶段；那么 系统 MUST 能得到包含 per-run effective options 的阶段结果
    假如 一份合法的 workflow YAML
    当 测试仅执行 pipeline 到 preflight 阶段
    那么 系统 MUST 能得到包含 per-run effective options 的阶段结果
  @req:r373 @human
  场景: workflow-structural-preload-accepts-duplicate-display-names-
    - 必须成立：假如 某个 run 引用的 demand fields 存在 duplicate effective field display names；当 系统执行 structural preload（workflow compile/preload 阶段）；那么 preload MUST 成功返回结构信息
    假如 某个 run 引用的 demand fields 存在 duplicate effective field display names
    当 系统执行 structural preload（workflow compile/preload 阶段）
    那么 preload MUST 成功返回结构信息
  @req:r492 @human
  场景: rendered-yaml-max-len-is-enforced-during-structural-preload
    - 必须成立：假如 用户调用 workflow 入口并提供 `template_vars`；当 structural preload 解析某个包含模板渲染的 demand YAML；那么 若渲染后 YAML 文本超过该上限，系统 MUST 在 structural preload 阶段 fail-fast
    假如 用户调用 workflow 入口并提供 `template_vars`
    当 structural preload 解析某个包含模板渲染的 demand YAML
    那么 若渲染后 YAML 文本超过该上限，系统 MUST 在 structural preload 阶段 fail-fast
  @req:r571 @human
  场景: per-run-patches-can-disable-inferable-diagnostics-before-pre
    - 必须成立：假如 workflow run A 的 demand fields 存在 duplicate effective field display names；当 系统执行到 preflight 阶段；那么 系统 MUST 将该 run 的 effective policy 视为关闭
    假如 workflow run A 的 demand fields 存在 duplicate effective field display names
    当 系统执行到 preflight 阶段
    那么 系统 MUST 将该 run 的 effective policy 视为关闭
  @req:r633 @human
  场景: outputs-override-can-disable-the-duplicate-name-trigger
    - 必须成立：假如 某个 demand fields 存在 duplicate effective field display names；当 用户通过 runtime overrides 将 effective outputs 调整为“不写 `header_fields_output_by=name` 的 header”；那么 preflight MUST 认为该检查不触发
    假如 某个 demand fields 存在 duplicate effective field display names
    当 用户通过 runtime overrides 将 effective outputs 调整为“不写 `header_fields_output_by=name` 的 header”
    那么 preflight MUST 认为该检查不触发

  @req:r633 @human
  场景: outputs-override-can-enable-the-duplicate-name-trigger
    - 必须成立：假如 某个 demand fields 存在 duplicate effective field display names；当 用户通过 runtime overrides 将 effective outputs 调整为“会写 `header_fields_output_by=name` 的 header”；那么 preflight MUST 认为该检查触发
    假如 某个 demand fields 存在 duplicate effective field display names
    当 用户通过 runtime overrides 将 effective outputs 调整为“会写 `header_fields_output_by=name` 的 header”
    那么 preflight MUST 认为该检查触发
  @req:r679 @human
  场景: first-failing-run-stops-preflight-immediately
    - 必须成立：假如 workflow 存在两个 runs，且按 decl_order 都会触发同一个 preflight 错误；当 系统执行 preflight；那么 系统 MUST 抛出与第一个 run 对应的错误
    假如 workflow 存在两个 runs，且按 decl_order 都会触发同一个 preflight 错误
    当 系统执行 preflight
    那么 系统 MUST 抛出与第一个 run 对应的错误
  @req:r719 @human
  场景: trigger-semantics-behave-identically-across-preflight-and-ru
    - 必须成立：假如 同一份 demand 结构与同一份 effective outputs/resources；当 系统在 preflight 与 runtime compile 两个边界分别判断是否触发某个 inferable check；那么 两处的触发判定 MUST 一致（不得出现一处触发而另一处不触发的 drift）
    假如 同一份 demand 结构与同一份 effective outputs/resources
    当 系统在 preflight 与 runtime compile 两个边界分别判断是否触发某个 inferable check
    那么 两处的触发判定 MUST 一致（不得出现一处触发而另一处不触发的 drift）
