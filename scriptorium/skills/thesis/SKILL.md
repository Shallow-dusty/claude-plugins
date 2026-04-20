---
name: thesis
description: 论文编译助手 — 编译、错误解析、字数统计、交叉引用检查。用法：/thesis [build|errors|wordcount|refs]
---

# 论文编译助手

封装 LaTeX 编译流程和常用诊断操作，服务于论文编辑-编译-修复循环。

## 论文路径

- **根目录**: `thesis/`
- **主文件**: `thesis/main.tex`
- **章节文件**: `thesis/data/chapter-{1..6}.tex`, `abstract-*.tex`, `appendix.tex` 等
- **编译日志**: `thesis/main.log`
- **输出 PDF**: `thesis/main.pdf`

## 命令

### `/thesis build`

编译论文并输出结果摘要。

**执行步骤:**
1. `cd thesis && latexmk -xelatex -latexoption='-interaction=nonstopmode -halt-on-error' main`
2. 如果编译成功：报告 "编译成功" + PDF 页数
3. 如果编译失败：自动执行 `/thesis errors` 解析错误

### `/thesis errors`

解析 `thesis/main.log` 提取可读的错误和警告信息。

**解析规则:**
1. **错误** — 搜索 `! ` 开头的行（LaTeX fatal error），向上追溯找到 `l.\d+` 行号
2. **文件定位** — 从 `(./data/chapter-5.tex` 这类括号匹配确定当前文件
3. **警告** — 搜索以下模式：
   - `LaTeX Warning: Reference .* undefined` → 未定义的引用
   - `LaTeX Warning: Citation .* undefined` → 未定义的参考文献
   - `Overfull \\hbox` → 排版溢出（宽度 > 10pt 才报告）
   - `Package hyperref Warning` → 超链接问题

**输出格式:**
```
=== 编译错误 (N 个) ===
[1] data/chapter-5.tex:123 — Undefined control sequence \textbff
[2] data/appendix.tex:45  — Missing $ inserted

=== 警告 (M 个) ===
[1] 未定义引用: \ref{tab:nonexist} (data/chapter-5.tex)
[2] 排版溢出: Overfull \hbox (15.2pt) at data/chapter-3.tex:89
```

### `/thesis wordcount`

统计论文各章节的字数/字符数。

**执行方式:**
由于 texcount 可能未安装，使用以下策略：

1. 对每个 `thesis/data/*.tex` 文件：
   - 用 `grep -v '^\s*%'` 去掉注释行
   - 用 `sed` 去掉 LaTeX 命令（`\xxx{...}` → 保留花括号内容）
   - 去掉 `\begin{...}`, `\end{...}`, `\label{...}`, `\ref{...}` 等结构命令
   - 统计剩余中文字符数 (`grep -oP '[\x{4e00}-\x{9fff}]' | wc -l`)
   - 统计剩余英文单词数 (`wc -w` 减去中文字符)

2. 输出格式：
```
章节                    中文字数    英文词数    合计(估)
─────────────────────────────────────────────────
chapter-1.tex (绪论)        2,450       120      2,570
chapter-2.tex (相关工作)    3,800        85      3,885
...
─────────────────────────────────────────────────
合计                       18,500       650     19,150
```

注：中文字数按字符计，英文按词计。"合计(估)"为两者简单相加，供参考。

### `/thesis refs`

检查交叉引用完整性。

**检查项:**
1. **未定义引用**: 从 `main.log` 搜索 `Reference .* undefined`
2. **未定义参考文献**: 从 `main.log` 搜索 `Citation .* undefined`
3. **孤立标签**: 扫描所有 `\label{xxx}` 和 `\ref{xxx}`/`\eqref{xxx}`，找出从未被引用的标签
4. **重复标签**: 找出同一 label 名定义多次的情况
5. **图表编号连续性**: 检查 `fig:` 和 `tab:` 前缀的标签是否有遗漏

**输出格式:**
```
=== 引用完整性检查 ===
未定义引用: (无)
未定义参考文献: [Zhang2024] (chapter-2.tex:45)
孤立标签 (定义了但从未引用): tab:old_results (chapter-5.tex:200)
重复标签: (无)
```

## 注意事项

- 编译需要 `xelatex` 和 `latexmk`（已安装）
- 论文使用南通大学模板 `csbachelor.cls`，对 XeLaTeX 有硬依赖
- 编译时间约 15-30 秒（取决于图片数量）
- `main.log` 是编译后自动生成的，`/thesis errors` 和 `/thesis refs` 依赖它存在
- 如果日志不存在或过期，先运行 `/thesis build`
