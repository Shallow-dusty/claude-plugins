---
description: 快速切换 Claude API 配置（AnyRouter 多账号/官方）
argument-hint: <配置名称|anyrouter|official|list|current|序号>
allowed-tools: Bash, Read, Edit
model: claude-haiku-4-5-20251001
---

# API 切换命令

快速切换 Claude Code 的 API 配置，支持多账号管理。

## ⚠️ 重要提示：死锁问题

**如果当前 API 已失效/额度耗尽**，此命令将无法执行（因为需要 Claude API 来理解命令）。

**应急解决方案** - 在 Shell 终端（非 Claude 对话）直接运行：
```bash
sos                 # 显示帮助 + 当前状态 + 所有配置
sos list            # 列出所有配置
sos <配置名称>       # 直接切换（如: sos fox-droid）
```

## 可用选项

| 选项 | 说明 |
|------|------|
| `<序号>` | 按 list 中的序号直接切换（如：`3`） |
| `<配置名称>` | 直接切换到指定配置（如：`anyrouter-Gwen`） |
| `anyrouter` | 交互式选择 AnyRouter 账号（列出所有 anyrouter-* 配置） |
| `official` 或 `off` | 关闭第三方 API，切换回官方 Claude API |
| `list` | 列出所有可用 API 配置 |
| `current` | 显示当前使用的 API 配置详情 |

## 使用示例

### 直接切换到指定账号
```bash
/switch-api anyrouter-Gwen         # 切换到 Gwen 账号
/switch-api anyrouter-Alune        # 切换到 Alune 账号
/switch-api anyrouter-LinuxDO      # 切换到 LinuxDO 账号
/switch-api anyrouter-github       # 切换到 GitHub 账号
/switch-api fox-droid              # 切换到 Fox Droid
/switch-api infinite-temp          # 切换到临时池
```

### 交互式选择
```bash
/switch-api anyrouter  # 显示菜单，选择要切换的 AnyRouter 账号
```

### 查看和管理
```bash
/switch-api list       # 查看所有配置（带序号和当前标记）
/switch-api current    # 查看当前使用的配置详情
/switch-api official   # 切换回官方 API
```

## 特性

✨ **智能匹配**：
- 精确匹配：`anyrouter-Gwen` → 直接切换
- 前缀匹配：`anyrouter` → 列出所有 anyrouter-* 供选择
- 序号切换：`3` → 按列表序号直接切换

🎨 **可视化增强**：
- 彩色输出，清晰易读
- 当前使用的配置高亮显示
- 带序号的配置列表

🔒 **安全机制**：
- 自动备份 settings.json
- JSON 格式验证
- 失败时自动恢复

---

## 执行

目标：**$ARGUMENTS**

请执行以下脚本：

```bash
~/.claude/api_pools/switch-api.sh $ARGUMENTS
```

**如果切换成功**，配置会自动热重载生效，无需重启。

### 验证
```bash
/switch-api current  # 确认切换成功
```
