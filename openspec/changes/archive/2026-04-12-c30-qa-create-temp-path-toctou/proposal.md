## Meta

- Type: `qa-0`
- Topic: `create_temp_path()` 关闭 fd 后仅返回 path 的 TOCTOU 理论窗口
- Related code:
  - `src/scalim/sinks/_internal/base.py:23` (`create_temp_path`)
  - Typical call sites:
    - `src/scalim/sinks/_internal/excel.py:247`
    - `src/scalim/workflow/resources_workbook.py:332`
    - `src/scalim/workflow/resources_csv.py:237`

## 背景

仓库大量输出路径采用“临时文件 → 原子替换”的模式确保落盘一致性（例如 Excel/CSV 输出），核心 helper 为：

- `create_temp_path(output_path, suffix)`：用 `tempfile.mkstemp(dir=output_dir)` 创建一个唯一临时文件，然后 `os.close(fd)`，只返回 `temp_path`。

这种写法的动机是正确的：保证临时文件名唯一且位于目标目录，从而支持 `Path(temp).replace(final)` 的原子替换。

但它也引入一个经典的 TOCTOU（time-of-check to time-of-use）理论窗口：**创建临时文件后立刻关闭 fd，后续写入阶段通常会“按路径重新打开/由第三方库按路径写入”**。在“输出目录不可信/多用户共享/存在恶意进程”的场景下，攻击者可能在该窗口内替换 `temp_path`（例如改成 symlink），导致写入落到非预期位置。

## 现状与触发条件

### 现状

- `create_temp_path()` 创建的是“真实文件”，但 fd 被关闭；后续写入往往走“按 path 写”（例如 `openpyxl.Workbook.save(path)`）。
- 多处调用点使用该 path 交给外部库写入，然后再 `replace()` 到最终路径。

### 触发条件（通常需要同时满足）

- `output_dir` 是共享且可被其他用户/进程写入/删除的目录（或在容器/多租户环境中目录隔离不严格）。
- 攻击者可以在 temp 文件创建后、写入发生前，对 `temp_path` 做替换（unlink + 创建 symlink/hardlink 等）。

在常见的“单用户本地目录”场景中，风险很低；但在“共享挂载目录 / 不可信路径输入 / 多用户机器”场景中，这属于可被安全审计指出的模式。

## 例子（帮助评审者理解风险）

假设输出路径为：`/shared/output/report.xlsx`，而 `/shared/output/` 对多用户可写。

1) `create_temp_path()` 创建 `/shared/output/tmpabcd.xlsx.tmp` 并关闭 fd；  
2) 攻击者监控目录变化，快速删除该 temp 文件并创建同名 symlink 指向攻击目标（例如另一个敏感文件或另一个用户目录下文件）；  
3) openpyxl 之后按路径写入，最终写到攻击者指定的目标。

（注：是否能写入成功取决于权限；但这会把“输出写入”变成“可被引导写入任意路径”的能力。）

## 目标

- 保持“同目录临时文件 + 原子替换”的正确性与跨平台可用性。
- 降低在不可信输出目录上的 TOCTOU 风险。
- 尽量不引入大规模 API 改动（调用点多）。
- `src/scalim/` 运行时代码保持 Python 3.6 兼容。

## 方案候选

### 方案 A：`create_temp_path` 返回 `(fd, path)`，并强制调用点用 fd 写入

优点：

- 从机制上消除“关闭后再打开”的窗口（写入过程始终绑定到 fd）。

缺点：

- 大量调用点需要改造。
- 很多第三方库（例如 openpyxl）只接受 `path`，不接受 fd/fileobj 或兼容性不稳定。

性价比：

- 中（安全收益高，但改造成本/兼容性风险也高）。

### 方案 B：改为“私有临时目录”策略（推荐）

做法：

- 在 `output_dir` 下创建一个权限收紧的私有临时目录（统一前缀 `.scalim-tmp-`，例如 `tempfile.mkdtemp(dir=output_dir, prefix='.scalim-tmp-')`；其 mode 通常为 `0o700`）。
- 返回该目录内的 `temp_path`（文件可由第三方库按路径创建/写入），写完后再原子替换到最终路径，并清理临时目录。

优点：

- 对第三方库友好：仍然是 “按 path 写入”。
- 攻击面显著收敛：攻击者即使能写 `output_dir`，也通常不能进入/替换私有临时目录内部文件（在 sticky-bit 或正确权限隔离下尤其有效）。

缺点：

- 仍然不能在“父目录可被任意删除且无 sticky-bit”的极端场景做到绝对安全（攻击者可删除整个临时目录条目）。
- 需要处理清理逻辑（异常路径清理、目录残留），并建议提供一个集中清理入口（maintenance 脚本/CLI）便于运维清理历史残留的 `.scalim-tmp-*`。

性价比：

- 高（小幅改动即可显著降低风险；对生态兼容好）。

### 方案 C：保持现状，仅文档约束输出目录必须可信（可作为补充，但不单独推荐）

优点：

- 零改动。

缺点：

- 对安全审计不友好；且“输出目录可信”很难在工程上长期保证（尤其是支持用户自定义输出路径的产品形态）。

性价比：

- 低。

## 推荐方案

推荐 **方案 B（私有临时目录）**：

- 保持现有 API（仍返回 `str temp_path`），改动集中在 `create_temp_path()` 内部；
- 对 openpyxl 等第三方库最友好；
- 安全收益可观，且不会改变最终输出语义。

如果未来确实出现“高安全场景”需求，可以在方案 B 的基础上再引入可选的“fd 写入”增强（方案 A 的局部化）。

## 代价/收益（性价比）

- 代码改动量：中（`create_temp_path` + 清理逻辑 + 少量调用点若依赖现有 temp 文件“已存在”的语义需要调整）。
- 行为变更风险：低到中（需要确认是否有调用点依赖 temp 文件预先存在；大多数第三方库写文件会覆盖/创建）。
- 安全收益：中到高（显著降低 TOCTOU 窗口的可利用性）。
- 性能影响：低（额外 mkdir/rmdir；相对 Excel 写入成本可忽略）。

## 验证建议（QA 口径）

- 单测：
  - `create_temp_path` 返回路径位于与输出同目录（或同父目录）以确保 `replace` 原子性；
  - 异常路径清理（临时目录/临时文件残留）；
  - 多线程/并发调用生成路径唯一性。
- 安全回归：
  - 在临时目录策略下，验证第三方库按 path 写入仍然工作；
  - 如果输出目录在 `/tmp`（sticky-bit）下，验证其他用户无法替换临时目录内部文件（手工/集成测试可选）。
