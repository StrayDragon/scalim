## 1. Spec / Doc Governance（SSOT + drift gates）

- [ ] 1.1 更新 `openspec/specs/key-normalization/spec.md`: 将 “EXPERIMENTAL warning MUST be visible by default” 的 hard requirement 与场景补齐/对齐本变更 specs
- [ ] 1.2 更新 `openspec/specs/key-normalization/spec.md`: 调整 relations 构建规范化视图时的 collision 语义——values 全部相等则合并继续,否则 fail-fast(并保持 redacted)
- [ ] 1.3 明确生成物/注入区块边界: 本变更不应直接手改任何 `.gen.` 文件或 `BEGIN/END AUTOGEN:<id>` 区块;若因 spec/doc 变更需要刷新生成物,SSOT 以对应非 `.gen.` 文件为准,入口使用 `just gen-docs`
- [ ] 1.4 验收口径(漂移门禁): 运行 `just openspec-check` 确保 sanitize + `openspec validate` 通过;若执行过 `just gen-docs`,确保生成物与注入区块无漂移(diff clean)

## 2. `key_normalization` EXPERIMENTAL 提示：默认可见 + 一次运行去重

- [ ] 2.1 定位当前 `key_normalization` 的 EXPERIMENTAL 提示发出点与路由方式(是否仅依赖 observer/hook/fallback logger)
- [ ] 2.2 引入项目内 warning 类 `ScalimExperimentalWarning(UserWarning)` 以便调用方精细过滤,同时保持默认可见
- [ ] 2.3 在“运行开始/运行上下文已确定 `key_normalization`”处补齐默认可见通道: 对非 `raw` 模式使用 `warnings.warn(..., category=ScalimExperimentalWarning, stacklevel=...)` 发出包含 `EXPERIMENTAL` + 当前模式值的提示(不得包含明细 key 值)
- [ ] 2.4 实现/复用一次运行去重(优先复用 `sample_once` 语义;否则在运行期上下文引入轻量 flag/set),确保 warnings 与结构化事件(若存在)整体只出现一次
- [ ] 2.5 若已存在 observability hub/事件流,保留结构化告警事件的发出,但以 warnings 作为默认可见兜底

## 3. loader / cached mapping 边界诊断加固（不泄露明细 key 值）

- [ ] 3.1 mapping 规范化 collision: 开箱即用安全处理——values 全部 `==` 则合并继续并发出一次 redacted 告警;values 不一致则 fail-fast;同时增强错误上下文(包含 source/loader 标识、`key_normalization` 模式、collision 计数/比例等;不包含明细 key 值)
- [ ] 3.2 mapping key 口径不一致诊断: 采用“高置信度 fail-fast + 其余告警”的判定策略,并在文案中给出可操作的修复建议(如调整 cast、改用 `force_str`、统一 loader key 口径;均需 redacted)
- [ ] 3.3 提炼一处“redacted diagnostic context”辅助函数/结构,统一保证异常/告警文案不会意外包含 raw key 的 `repr`

## 4. Tests（可验证、可回归）

- [ ] 4.1 新增/更新测试: `key_normalization="auto_str"/"force_str"` 时,即使未注册任何 observer/hook 且未显式开启 fallback logger,也能在一次运行内观测到一次包含 `EXPERIMENTAL` 的提示(并断言一次运行去重)
- [ ] 4.2 新增/更新测试: loader mapping 规范化 collision 在 values 相等时会合并继续并发出 redacted 告警;values 不相等时 fail-fast;两种情况下文案均不包含明细 key 值
- [ ] 4.3 新增/更新测试: cached/preload mapping 规范化 collision 行为同 4.2,并断言文案包含 cached/preload 上下文但不泄露明细 key 值
- [ ] 4.4 新增/更新测试: `auto_str` + 显式 cast 的错配场景——cast 后候选 key 不命中,但字符串规范化后可命中(应 redacted 强告警并提示调整 cast 或改用 `force_str`)
- [ ] 4.5 新增/更新测试: EXPERIMENTAL 提示使用 `ScalimExperimentalWarning` 类别,便于调用方过滤

## 5. Final Gates

- [ ] 5.1 运行目标用例/聚焦 pytest 子集确认行为(提示可见性/去重/diagnostics)通过
- [ ] 5.2 运行 `just qa` 作为最终验收门禁,并确保 `just openspec-check` 通过(防止规范/实现漂移)
