## Context

当前 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment` 固定写入 JetBrains/IntelliJ 兼容的 `# $schema: <schema-ref>` 头,并以此作为“统一格式”。但在实际 IDE/LSP 生态中,Red Hat YAML Language Server 需要使用 `# yaml-language-server: $schema=<schema-ref>` 才能生效。

同时,`PROJECT_CLI_NAME yaml-dsl schema-serve` 作为一个内置 schema 的本地 HTTP server,在工作流上并非必需: schema 引用既可以是 URL,也可以是本地绝对/相对路径(由编辑器/LSP 决定如何解析)。移除该命令可降低维护面并避免用户依赖一个不稳定的额外服务。

约束:
- `src/IMPL_ROOT/` 运行时需兼容 Python 3.6。
- OpenSpec 规范位于 `openspec/specs/**/spec.md` 为 SSOT,本变更以增量规范文件表达,并通过 `just openspec-check` / `just qa` 做 drift gate。

## Goals / Non-Goals

**Goals:**
- 移除 `PROJECT_CLI_NAME yaml-dsl schema-serve` 命令及其相关实现/测试/规范引用。
- 为 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment` 增加 `--comment-style {all,jetbrains,redhat}` 用于生成:
  - JetBrains/IntelliJ: `# $schema: <schema-ref>`
  - Red Hat YAML LS: `# yaml-language-server: $schema=<schema-ref>`
- 保持“upsert”语义: 在文件头部注释块中插入/更新/移除相关 schema modeline,且幂等(文件已满足期望时不改写)。

**Non-Goals:**
- 不实现新的 schema server 或自动下载 schema。
- 不改变 schema 引用解析规则(仍由 `--type` + `--schema-path` 推导 `<schema-ref>` 的行为定义)。
- 不试图在 YAML 文件任意位置寻找/更新 schema 头(仅处理文件头部 comment block 范围内)。

## Decisions

- **CLI 选项**: `--comment-style` 作为枚举参数,取值:
  - `all`(默认): 同时 upsert 两种头,以最大化跨编辑器可用性
  - `jetbrains`: 仅保留/生成 JetBrains 头,并移除头部 comment block 中的 Red Hat 头
  - `redhat`: 仅保留/生成 Red Hat 头,并移除头部 comment block 中的 JetBrains 头
- **插入顺序**: 当 `all` 时,稳定输出顺序为:
  1) `# yaml-language-server: $schema=<schema-ref>`
  2) `# $schema: <schema-ref>`
  并在其后保留一个空行(与现有行为一致,但扩展为“最后一个 schema 头后保留空行”)。
- **更新范围**: 只在“文件起始处的注释块”内识别并 upsert:
  - `# yaml-language-server: $schema=...`
  - `# $schema: ...`
  其余位置不做改写。
- **SSOT / 生成边界**:
  - `openspec/specs/**/spec.md` 为 SSOT,手工维护。
  - 不编辑任何 `.gen.` 文件与 injected blocks。
  - 提交前通过 `just openspec-check` 与 `just qa` 作为 drift gate 验证规范与实现一致性。

## Risks / Trade-offs

- [Breaking] 移除 `schema-serve` 可能影响已有脚本/文档/笔记,需要同步更新并在变更说明中明确。
- [复杂性] `upsert-lsp-comment` 需要在幂等性与“仅保留指定风格”的约束下正确处理多种文件头形态(已有单头/双头/错误 schema/ref/空行)。
- [工具差异] 不同编辑器对本地路径/相对路径/URL 的解析细节不同;本变更只负责生成 comment,不保证所有工具在所有路径形态下都能解析。

## Migration Plan

1. 更新 `yaml-dsl-cli-validation` 与 `yaml-dsl-agent-guidance` 的规范(以增量规范表达)。
2. 修改 `src/IMPL_ROOT/cli/yaml_dsl_lsp.py`:
   - 删除 `schema-serve` 子命令
   - 扩展 `upsert-lsp-comment` 支持 `--comment-style`
3. 更新/新增测试覆盖:
   - `jetbrains` / `redhat` / `all` 三种输出与幂等性
   - 删除 `schema-serve` 相关回归测试

## Open Questions

- `--comment-style` 的默认值是否应为 `all`(更“开箱即用”)或 `jetbrains`(更贴近历史行为)。本变更倾向默认 `all` 以减少用户踩坑。
