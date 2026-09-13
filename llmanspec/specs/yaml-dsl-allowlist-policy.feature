# language: zh-CN
# capability: yaml-dsl-allowlist-policy
# purpose: 防止allowlist配置误用导致的安全风险，包括通配符滥用、隐式逃逸口和不受信的trusted-mode启用。 [rev:c25]
# scope: src/scalim/
功能: yaml-dsl-allowlist-policy

  @req:r104 @human
  场景: wildcard restrictions
    - System MUST 系统MUST拒绝allowlist中的通配符配置，除非显式启用trusted-mode。`allowed_modules`和`allowed_functions`的通配符处理规则不同。
    假如 调用方未启用trusted-mode
    当 运行入口收到`allowed_modules={"*"}`
    那么 系统MUST fail-fast
    当 运行入口收到`allowed_functions={"*"}`（无论trusted-mode状态）
    那么 系统MUST fail-fast
    假如 调用方显式启用trusted-mode
    当 运行入口收到`allowed_modules={"*"}`（或等价全放开配置）
    那么 系统MUST允许继续执行
  @req:r346 @human
  场景: trusted-mode gating and warnings
    - System MUST 系统MUST通过多层门控防止trusted-mode误启用，包括显式参数、环境变量和强风险告警。
    当 调用方未显式启用trusted-mode相关参数
    那么 系统MUST不允许放宽allowlist约束
    当 调用方启用`resolver_trusted_mode=trusted_allow_all_modules`
    那么 系统MUST fail-fast
    假如 调用方启用`resolver_trusted_mode=trusted_allow_all_modules`
    当 该条件成立
    那么 系统MAY继续执行
  @req:r468 @human
  场景: denylist-only escape hatches
    - System MUST 系统MUST NOT提供隐式逃逸口子绕过allowlist要求。allowlist缺失时MUST fail-fast并提供修复示例。
    当 调用方未提供`allowed_modules`且未提供`allowed_functions`
    那么 系统MUST fail-fast
    假如 系统提供denylist-only（不安全）模式支持内部测试
    当 调用方尝试启用denylist-only模式
    那么 系统MUST要求显式unsafe参数（命名包含`unsafe`或等价标识）
  @req:r553 @human
  场景: resolver MUST enforce denylist during attribute traversal (including trusted ules
    - 即使在 `resolver_trusted_mode=trusted_allow_all_modules` 放宽模块 allowlist 的情况下,Python 引用解析器也 MUST 对危险模式保持 denylist 防御深度。 系统 MUST 在解析 class-style 引用的属性链遍历过程中逐级执行 denylist 校验: - 属性名命中危险函数列表(例如 `getattr/open/eval/...`) MUST fail-fast - 属性名包含 `__` 或等价自省危险模式 MUST fail-fast - 属性名为 `lambda` MUST fail-fast 该要求的目的是 defense-in-depth: 即使未来上游对“引用字符串”的校验逻辑调整,遍历实现本身也不应变成可被利用的空窗。
    当 引用包含属性链片段命中 denylist(例如 `pkg.mod:Obj.getattr`)
    那么 resolver MUST fail-fast
    当 引用包含 `__` 相关属性(例如 `pkg.mod:Obj.__class__`)
    那么 resolver MUST fail-fast
