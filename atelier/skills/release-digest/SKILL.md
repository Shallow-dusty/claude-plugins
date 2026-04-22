---
name: release-digest
description: Use when the user asks to interpret, summarize, or explain recent Claude Code release notes, changelogs, version updates, or new features
argument-hint: "[count]"
disable-model-invocation: true
allowed-tools: Read, Edit
---

# Release Notes 解读

解读 Claude Code 最近的版本更新，并同步维护特性速查文档。

## 原始数据

以下是自动拉取的最近几个版本的 CHANGELOG（数量由参数指定，默认 3，上限 20）：

!`${CLAUDE_PLUGIN_ROOT}/skills/release-digest/scripts/fetch-notes.sh $ARGUMENTS`

如果上方显示 `FETCH_FAILED`，告知用户：
- "GitHub CHANGELOG 拉取失败，可能是网络问题"
- "你可以先运行 `/release-notes` 查看更新日志，然后让我帮你解读（不需要再运行 /release-digest）"

## 解读格式

对每个版本输出：

```
## vX.Y.Z
[一句话总结本版本重点]

[分为以下分类，空分类跳过；只有 1-2 个条目的小版本可省略分类标题直接列出]

**新功能**
- **功能名** — 通俗解释 + 对用户的实际影响

**改进**
- **改进点** — 变化说明

**修复**
- 简要列出，小修复可合并为一行
```

**纯修复版本判定**：如果所有条目均为 Fixed/Improved 且没有任何 Added，标注为"稳定性修复版本"，用一两句话概括即可，不需逐条展开。

## 解读原则

1. 用自然的中文重新表述，不要逐条翻译英文原文
2. 每个条目说清楚"对用户意味着什么"
3. 重要新功能详细说，小 bugfix 一笔带过
4. 保留广泛使用的技术术语原文（如 MCP、hook、sandbox、OAuth、streaming 等），不确定的术语保留原文并括号加简短说明
5. 用户是非计算机科班背景，解读时侧重"这对我有什么用"而非技术实现细节

## 总结

所有版本解读完毕后，用 1-2 句话概括这批更新的整体方向和重点。

## 同步特性速查文档

**注意**：先完整输出全部解读和总结，确保用户能看到完整内容，然后再执行以下操作。

**目标文件**：`~/.claude/docs/cc-features.md`

读取该文件，对照本次 changelog 检查是否需要更新。

**记录标准**（只记影响日常使用的变更）：
- 新模型发布 → 替换旧模型条目
- 新特性取代旧特性 → 删旧加新
- 新功能/新快捷键/行为变化 → 添加到对应分类
- 行为变化（即使标为 Fixed）→ 如果改变了用户需要知道的操作方式，记录
- 纯 bugfix、性能优化 → 不记录
- 拿不准时不记录（宁漏勿滥）

**排除规则**（以下情况不写入）：
- **系统提示词已包含的信息** → 当前模型名称/上下文窗口大小、内置斜杠命令列表、可用 agent 类型、已加载的 skill 列表等，会随版本更新自动写入系统提示词。判断方法：回顾当前对话的系统提示词，已存在的不记录
- **需要 opt-in 的实验性功能** → 需手动开启设置项才能使用的功能（如 `experimentalXxx`、managed settings 专属等），先检查 `~/.claude/settings.json` 确认是否已启用。未启用则不记录；已启用则记录，并在条目末尾标注 `[opt-in: 设置项名]`

**存量校验**：每次运行本 skill 时，扫描文档中带 `[opt-in: ...]` 标注的条目，检查对应设置项是否仍启用。已关闭或已毕业为默认行为的，清理标注或移除条目。同时检查是否有条目与当前系统提示词重复，如有则移除。

**操作**：
- 有更新 → 先告知用户计划改动什么，然后直接编辑文件
- 无更新 → 告知"特性速查已是最新"
- 文件不存在或路径错误 → 告知用户，跳过更新步骤
