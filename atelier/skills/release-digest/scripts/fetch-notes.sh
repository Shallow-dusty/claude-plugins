#!/bin/bash
# 从 GitHub 拉取 Claude Code CHANGELOG，提取最近 N 个版本
COUNT=${1:-3}

# 校验：必须是正整数，否则回退默认值
if ! [[ "$COUNT" =~ ^[1-9][0-9]*$ ]]; then
  COUNT=3
fi

# 上界保护：防止输出过大挤占 context
if [ "$COUNT" -gt 20 ]; then
  COUNT=20
fi

# -f: HTTP 4xx/5xx 时返回空内容，被 -z 检查捕获
RAW=$(curl -sfL --max-time 10 "https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md" 2>/dev/null)

if [ -z "$RAW" ]; then
  echo "FETCH_FAILED: 无法获取 CHANGELOG"
  exit 0
fi

# 兼容 "## 2.1.39"、"## v2.1.39"、"## [2.1.39]" 格式
echo "$RAW" | awk -v count="$COUNT" '
  /^## [v\[]?[0-9]/ {
    if (++n > count) exit
  }
  n >= 1 { print }
'
