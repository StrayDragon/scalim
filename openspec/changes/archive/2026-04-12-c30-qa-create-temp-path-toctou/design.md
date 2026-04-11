## Context

仓库大量文件输出采用“临时文件 → 原子替换（temp+replace）”模式确保落盘一致性（避免读者看到半写文件）。现有核心 helper 为 `create_temp_path(output_path, suffix)`（位于 `src/scalim/sinks/_internal/base.py`）：用 `tempfile.mkstemp(dir=output_dir)` 创建唯一临时文件后立即 `os.close(fd)`，只返回 `temp_path` 供后续写入（往往由第三方库按 path 写入）并在完成后 `Path(temp_path).replace(output_path)`。

该模式的“同目录临时文件 + replace”动机是正确的（确保 replace 原子性与跨平台可用性），但“创建后立刻关闭 fd，仅返回 path”的行为在不可信输出目录场景中存在经典 TOCTOU 理论窗口：

- 临时文件创建后到实际写入发生前，攻击者若能在同目录内操作文件系统条目，可能通过 unlink/替换为 symlink/hardlink 的方式引导后续“按路径写入”落到非预期目标。

在常见的单用户本地目录风险很低，但在共享挂载目录、多用户机器或不可信路径输入场景中容易被安全审计指出。

约束：

- 尽量不引入大规模 API 改动（调用点多，且第三方库常只接受 path）
- `src/scalim/` 运行时代码保持 Python 3.6 兼容
- 保持 temp+replace 的原子落盘语义

## Goals / Non-Goals

**Goals:**

- 在“第三方库按 path 写入”的前提下，显著降低 TOCTOU 可利用性
- 保持现有调用形态尽量不变（仍返回 `temp_path` 供写入）
- 异常路径下尽量不留下大量临时残留（best-effort 清理）

**Non-Goals:**

- 不追求在“父目录可被任意删除且无 sticky-bit”的极端场景做到绝对安全（该类环境需要更强的系统级隔离）
- 不强制引入“fd 写入”作为唯一方案（会与 openpyxl 等生态冲突）

## Decisions

### 1) 采用“私有临时目录”策略作为默认实现（方案 B）

`create_temp_path()` 内部改为：

1. 在 `output_dir` 下创建一个权限收紧的私有临时目录（例如 `.scalim-tmp-<random>/`）
2. 在该私有目录内创建临时文件名（可继续使用 `mkstemp(dir=private_dir)` 生成唯一文件，并关闭 fd）
3. 返回该临时文件路径给调用点按 path 写入

这样做的关键收益是：即使 `output_dir` 可被其他用户写入，只要私有临时目录的权限收紧到仅当前用户可访问（常见为 `0o700`），攻击者通常无法进入目录去替换/劫持临时文件条目，TOCTOU 可利用性显著下降；同时对第三方库仍保持“按 path 写入”的兼容性。

### 2) 在 replace/完成后对私有临时目录做 best-effort 清理

由于 `create_temp_path` 仅返回 path，清理需要在“replace 完成”附近执行。Phase 0 选择：

- 为“temp+replace”封装一个统一 helper（或在现有调用点加一个小型清理步骤），在成功替换后尝试删除空的私有临时目录
- 异常路径下也尽量清理（例如 finally 尝试 unlink 临时文件与 rmdir 临时目录），但以 best-effort 为准（不因清理失败影响主流程）

### 3) 统一临时目录前缀，并提供集中清理入口（便于运维与治理）

为便于识别与外部清理：

- 私有临时目录前缀统一为 `.scalim-tmp-`（与现有提案/实现约定一致）
- 提供一个集中清理入口（例如 maintenance 脚本或 CLI 子命令），用于在进程崩溃/异常情况下清理历史残留的 `.scalim-tmp-*` 目录（best-effort；可按空目录/mtime/阈值策略清理）

## Risks / Trade-offs

- **残留风险**：若进程崩溃或异常路径未覆盖，私有临时目录可能残留；需通过测试覆盖与 best-effort 清理降低概率，并可在后续提供统一清理命令/脚本。
- **权限差异**：不同平台/文件系统对目录权限语义不同；因此规范以“降低可利用性”为目标，并以单测验证“目录隔离 + replace 原子性”关键属性。

## Migration Plan

- Phase 0：实现私有临时目录策略 + 更新典型调用点/封装 helper + 补单测覆盖
- 后续（可选）：在高安全需求场景提供可选的 fd 绑定写入增强（方案 A 的局部化），或增加更强的输出目录可信校验/allowed-roots 约束

## Open Questions

- 无。
