## Meta

- Type: `qa-0`
- Topic: 派生输出 fingerprint 使用 `sha1`（`# noqa: S324`）的治理：是否切换到 `sha256`
- Related code:
  - `src/scalim/execution/output_composition.py:397`~`:401` (`_fingerprint_for_derived_target`)
  - Fingerprint 写入 meta/audit：
    - `src/scalim/execution/output_composition.py:764`（`derived.<id>.fingerprint`）
    - `src/scalim/execution/output_composition.py:835`（audit rows 的 `fingerprint`）

## 背景

`OutputComposition` 支持派生输出（`DerivedOutputTargetSpec`），在 meta/audit 中写入一个“派生聚合指纹”（fingerprint），用于：

- 对拍/复现：同一派生定义在不同运行中应得到相同 fingerprint；
- 诊断归因：将派生输出相关错误按 fingerprint 聚合（audit sheet、日志、外部消费）。

当前实现用 `hashlib.sha1()` 计算 fingerprint，并用 `# noqa: S324` 压掉安全 lint 警告（S324 通常认为 SHA1 不适合安全用途）。

该点的核心是：这里的 hash **不是加密/签名用途**，而是“稳定标识符”。但工程上仍会面临两个现实问题：

1) 安全审计会持续关注并质疑 `sha1` 的存在；  
2) 某些环境（例如 FIPS 约束）可能对 SHA1 的可用性/使用方式有额外限制。  

## 现状

```py
def _fingerprint_for_derived_target(...):
    h = hashlib.sha1()  # noqa: S324
    payload = "\\n".join([...]).encode("utf-8", errors="replace")
    h.update(payload)
    return h.hexdigest()
```

此 fingerprint 会进入：

- `meta` sheet：`derived.<target_id>.fingerprint`
- `audit` sheet：派生输出错误行的 `fingerprint` 字段

因此它在一定程度上属于“对外可见的稳定输出”（至少对用户可见、对下游可消费）。

## 兼容性问题（用户问题：兼容 py3.6/py3.10 吗？）

- `hashlib.sha1()` 与 `hashlib.sha256()` 在 Python 3.6 与 Python 3.10 中都存在，因此 **从 Python 版本兼容性角度，切换到 `sha256` 没问题**。
- 真正的兼容性风险不在 Python 版本，而在 **fingerprint 值的稳定性**：
  - 切换算法会导致所有 fingerprint 值变化，从而影响对拍、报表 diff、以及下游按 fingerprint 聚合的逻辑。

## 例子（指纹变化的影响）

如果某派生输出 `target_id="t1"`，聚合定义不变：

- 当前版本：`derived.t1.fingerprint = <sha1(payload)>`
- 切换算法后：`derived.t1.fingerprint = <sha256(payload)>`（不同值、不同长度）

下游如果做了：

- “按 fingerprint 聚合 error 统计”
- “对比两个运行的 derived fingerprint 是否一致来判断定义漂移”

则会在升级后出现“全部不一致”的假阳性。

## 方案候选

### 方案 A：保留 `sha1`，增加显式注释与治理说明（最保守）

做法：

- 保留 `sha1` 与现有 fingerprint 值不变；
- 在函数上方补充明确注释：
  - 该 hash 仅用于稳定 fingerprint/非安全用途；
  - 不用于签名/认证/加密；
  - 之所以保留 sha1 是为了输出稳定性。

优点：

- 完全不影响输出兼容性（最重要）；
- 改动最小。

缺点：

- 仍然需要 `# noqa: S324`；
- 对 FIPS/安全审计的“沟通成本”仍然存在。

性价比：

- 高（在“必须保持 fingerprint 稳定”的前提下，这是最划算的方案）。

### 方案 B：切换到 `sha256`（最干净，但会改变输出）

做法：

- 把 `sha1` 改为 `sha256`，去掉 `# noqa: S324`；
- 必要时考虑截断（例如取前 40 字符）以降低 meta/audit 的可读性压力，但截断不会保持旧值。

优点：

- 安全 lint 更干净；
- 算法层面更“现代”，降低被质疑成本；
- 在 FIPS 环境下通常更容易接受（视具体 OpenSSL/FIPS 配置）。

缺点：

- fingerprint 全量变化：会影响对拍/聚合/回归判定；
- 需要明确标注变更影响（如果 meta/audit 被视为稳定接口，可能需要 proposal 标注 **BREAKING** 或提供迁移说明）。

性价比：

- 中（工程更干净，但兼容性成本可能非常高）。

### 方案 C：双写/版本化（兼容迁移）

做法：

- 在 meta/audit 中同时输出：
  - `derived.<id>.fingerprint`（保持旧 sha1）
  - `derived.<id>.fingerprint_v2`（新 sha256）
- 或引入 `derived.<id>.fingerprint_algo` 字段。

优点：

- 兼容与升级两全；
- 下游可以渐进迁移到 v2。

缺点：

- 输出字段增加，复杂度上升；
- 需要额外文档/测试。

性价比：

- 中到高（当且仅当“想升级算法，但不能破坏兼容”时很划算）。

## 推荐方案

采用 **方案 B（切换到 sha256）**：

- 一步到位消除 `sha1` 与 `# noqa: S324` 的治理摩擦；
- 在工程语义上把 fingerprint 明确为“稳定标识符”（非安全用途），并将算法/格式变更视为 **显式 breaking 输出**；
- 接受 fingerprint 值（以及长度从 40→64）变化带来的对拍/下游聚合口径更新成本。

## 性价比总结

- 只为消除 S324：方案 A 最值（低成本、不破坏稳定性）。
- 想同时满足“现代算法 + 兼容”：方案 C 最值（中成本，长期收益）。
- 追求极简/彻底治理且允许变更：方案 B 最直接。

## 验证建议（QA）

- 新增单测（或快照测试）覆盖：
  - fingerprint 对相同输入稳定；
  - fingerprint 对输入变化敏感（target_id/parts 变化会变）。
- 若采用方案 B/C：
  - 在 release note/变更记录里明确说明指纹变更对下游的影响；
  - 对依赖 meta/audit 的集成用例做一次对拍更新。
