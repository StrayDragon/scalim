---
name: openspec-onboard
description: Guided onboarding for OpenSpec - walk through a complete workflow cycle with narration and real codebase work.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.1.1"
---

引导用户完成第一次完整 OpenSpec 工作流(从选题到归档).

这是教学模式:你要在真实代码库中推进真实任务,同时解释每一步的意义.

---

## 阶段 0:前置检查

先确认 CLI 可用:

```bash
# Unix/macOS
openspec --version 2>&1 || echo "CLI_NOT_INSTALLED"
# Windows (PowerShell)
# if (Get-Command openspec -ErrorAction SilentlyContinue) { openspec --version } else { echo "CLI_NOT_INSTALLED" }
```

若未安装:提示用户先安装后再继续,停止流程.

---

## 阶段 1:欢迎与目标对齐

清晰说明本次目标:
- 选择一个小而真实的任务
- 走完一轮完整工件流转(proposal → specs → design → tasks)
- 进入 apply 并完成实现
- 最后归档 change

建议控制在 15~20 分钟,重点是“看懂工作流如何工作”.

---

## 阶段 2:挑选练习任务

在仓库中快速寻找 3~4 个“适合 onboarding 的小任务”,例如:
- TODO/FIXME/HACK
- 明显缺失的错误处理
- 可补的测试覆盖
- 可替换的 `any`
- 非必要调试输出

并给出每个候选项的:
- 位置(文件路径)
- 预估改动范围
- 为什么适合首轮演示

若用户选的范围过大,先建议切片再做.

---

## 阶段 3:快速演示 explore

在正式建 change 前,先做 1~2 分钟探索:
- 读取关键文件
- 用简短分析说明现状
- 必要时画一张 ASCII 小图

然后暂停,确认用户是否继续创建 change.

---

## 阶段 4:创建 change

1. 协助命名(kebab-case)
2. 执行:

```bash
openspec new change "<name>"
```

如用户指定 schema,则添加 `--schema <schema>`.

3. 展示状态:

```bash
openspec status --change "<name>"
```

解释当前 ready / blocked 工件.

---

## 阶段 5:逐步创建工件

按 `status` 中 ready 顺序推进.每个工件都执行:

```bash
openspec instructions <artifact-id> --change "<name>"
```

然后:
- 解释该工件目的
- 起草内容(可让用户补充)
- 写入对应文件
- 更新状态并说明下一步

至少覆盖 proposal/specs/design/tasks(以 schema 为准).

---

## 阶段 6:进入实现(apply)

执行:

```bash
openspec instructions apply --change "<name>"
```

根据输出推进:
- blocked:先补齐缺失工件
- ready:按 tasks 执行实现
- all_done:进入归档准备

实现过程中保持“轻讲解、重实操”.

---

## 阶段 7:归档收尾

确认任务完成后,执行归档流程并解释归档结果.

最后给出简短 recap:
- 今天走过了哪些阶段
- 关键命令有哪些
- 后续可独立使用哪些入口(`/opsx:new`、`/opsx:ff`、`/opsx:continue`、`/opsx:apply`、`/opsx:archive`)

---

## 护栏

- 不要跳阶段(onboarding 目标是让用户看到完整闭环)
- 每个关键切换点都做短暂停顿确认
- 不要为了“讲完流程”牺牲真实任务质量
- 用户想中途退出时,礼貌收尾并给出下次继续的最短路径


