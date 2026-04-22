---
name: translate
description: "学术翻译工作流（三阶段反思）。适用场景：翻译论文段落/摘要/全文、LaTeX 文件翻译+编译、arXiv 论文源码翻译、中英互译。当用户说翻译/translate/帮我翻成英文/中文/polish my writing 时触发。不要在用户只想查术语解释时触发（那用对话即可）。"
argument-hint: "<文本|文件路径|arxiv:ID> [--to en|zh] [--glossary path] [--compile]"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent
---

# Academic Translation — 三阶段反思翻译工作流

基于吴恩达 Translation Agent 的反思范式，针对学术场景深度优化。

## 核心原理

```
阶段 1 — 直译 (Draft)     忠实原文语义，不遗漏、不增添
阶段 2 — 反思 (Reflect)   自评 6 个维度，列出具体问题
阶段 3 — 优化 (Refine)    逐条修复反思中发现的问题，输出终稿
```

这不是三次重复翻译，而是模拟人类译审流程：译者初稿 → 审校批注 → 译者修订。

## 参数解析

输入 `$ARGUMENTS`，按以下规则解析：

| 模式 | 触发条件 | 示例 |
|------|---------|------|
| **文本模式** | 输入不是文件路径也不是 arxiv ID | `/translate 基于改进YOLOv11的墙体裂缝检测` |
| **文件模式** | 输入是 `.tex` / `.md` / `.txt` 文件路径 | `/translate thesis/chapters/ch3.tex` |
| **目录模式** | 输入是目录路径 | `/translate thesis/chapters/` |
| **arXiv 模式** | 输入匹配 `arxiv:XXXX.XXXXX` | `/translate arxiv:2502.17882` |

**可选 flag**（出现在参数任意位置均可）：
- `--to en` 或 `--to zh`：指定目标语言（默认自动检测：中文→英文，英文→中文）
- `--glossary <path>`：注入术语表文件（YAML 格式）
- `--compile`：翻译完成后自动编译 LaTeX（仅文件/目录模式）
- `--draft-only`：仅输出阶段 1 直译，跳过反思和优化（用于速度优先场景）
- `--side-by-side`：输出双语对照格式

## 执行流程

### 步骤 0：解析与准备

1. 解析 `$ARGUMENTS`，确定模式和 flag
2. 自动检测语言方向（如未指定 `--to`）
3. 如有 `--glossary`，读取术语表文件
4. 如果是文件/目录模式，读取源文件内容

### 步骤 1：阶段 1 — 直译 (Draft Translation)

**对于文本模式**：直接翻译输入文本。

**对于文件模式**：
- 读取文件内容
- 识别可翻译内容（跳过 LaTeX 命令、数学公式、引用键、label/ref）
- 按段落/章节分块翻译（每块不超过 ~2000 字，保持段落完整性）

**直译 Prompt 核心指令**：

```
你是一位学术翻译专家。请将以下{source_lang}学术文本翻译为{target_lang}。

要求：
- 忠实传达原文每一个语义单元，不遗漏、不增添、不改变原意
- 保持学术文体的正式程度
- 术语翻译准确，首次出现时附注原文（如：注意力机制(Attention Mechanism)）
- 人名、机构名、模型名（如 YOLOv11、ResNet）保留原文不翻译
- 数字、公式、引用标记原样保留
{glossary_injection}

原文：
{source_text}
```

如有术语表，`{glossary_injection}` 替换为：
```
- 以下术语必须按指定方式翻译（术语表优先级最高）：
{术语表内容}
```

### 步骤 2：阶段 2 — 反思 (Reflection)

对阶段 1 的译文进行系统性自评。**不是重新翻译，而是生成批注**。

**反思 Prompt 核心指令**：

```
你是一位资深学术翻译审校专家。请审阅以下翻译，从 6 个维度逐一检查，对每个发现的问题给出具体的修改建议。

## 审校维度

1. **准确性 (Accuracy)**：是否有误译、漏译、过度翻译？逐句对照原文检查。
2. **术语一致性 (Terminology)**：同一术语是否全篇统一？是否符合该领域惯用译法？
3. **学术语体 (Register)**：是否符合{target_lang}学术论文的表达习惯？是否有口语化/机翻痕迹？
4. **流畅度 (Fluency)**：译文本身是否通顺自然？是否有生硬的直译痕迹？
5. **完整性 (Completeness)**：是否有遗漏的句子、脚注、图表说明？
6. **格式保持 (Format Integrity)**：LaTeX 命令、公式、引用、交叉引用是否完好无损？

## 输出格式

对每个维度，如果发现问题，按以下格式列出：
- **[维度名]** 问题描述 → 建议修改（附原文对照）

如果某维度无问题，简要确认即可（如"术语一致性：无问题"）。

原文：
{source_text}

译文：
{draft_translation}
```

### 步骤 3：阶段 3 — 优化 (Refinement)

根据阶段 2 的反思结果修订译文。

**优化 Prompt 核心指令**：

```
你是一位学术翻译定稿专家。请根据审校意见修订译文，生成最终版本。

规则：
- 逐条处理审校意见中的每一条修改建议
- 修改时保持未被指出问题的部分不变（最小改动原则）
- 如果某条建议你认为不合理，保持原译并简要说明理由
- 最终输出仅包含修订后的完整译文，不包含批注
{glossary_injection}

审校意见：
{reflection}

当前译文：
{draft_translation}
```

### 步骤 4：输出

**文本模式**：直接在对话中输出终稿。如指定 `--side-by-side`，输出双语对照表格。

**文件模式**：
1. 将译文写入新文件（原文件名 + `_translated` 后缀，如 `ch3_translated.tex`）
2. 不覆盖原文件
3. 如指定 `--compile`，尝试编译翻译后的 .tex 文件：
   - 运行 `latexmk -xelatex` 或项目已有的编译命令
   - 如果编译失败，读取错误日志，自动修复 LaTeX 语法问题，重试（最多 3 轮）
   - 编译成功后告知用户 PDF 路径

**目录模式**：
1. 在目标目录下创建 `_translated/` 子目录
2. 保持原目录结构，逐文件翻译
3. 非文本文件（图片、.bib、.cls 等）直接复制
4. 如指定 `--compile`，在 `_translated/` 目录中编译

**arXiv 模式**：
1. 下载论文源码：`wget https://arxiv.org/e-print/{arxiv_id} -O source.tar.gz`
2. 解压到临时目录
3. 按目录模式处理
4. 编译生成中文 PDF

## LaTeX 特殊处理规则

翻译 LaTeX 文件时，严格遵守以下规则：

### 不翻译（原样保留）
- 所有 `\command{}` 的命令名本身
- `$...$` 和 `$$...$$` 和 `\[...\]` 和 `\(...\)` 内的数学公式
- `\begin{equation}...\end{equation}` 等数学环境内容
- `\label{...}`、`\ref{...}`、`\cite{...}`、`\eqref{...}` 等引用命令及其参数
- `\begin{figure}...\end{figure}` 中的 `\includegraphics` 路径
- `\bibliographystyle{...}`、`\bibliography{...}`
- `\usepackage{...}`、文档类声明等导言区命令
- 算法环境中的关键字（`\If`、`\For`、`\While` 等）

### 翻译
- `\section{}`、`\subsection{}`、`\caption{}` 等的花括号内容
- `\title{}`、`\abstract` 环境内的文本
- 正文段落文本
- `\footnote{}` 内容
- `\textbf{}`、`\textit{}` 等格式命令包裹的文本

### 编译适配
- 中文输出需要 CTeX 宏包或 xeCJK，翻译后自动检查导言区是否包含中文支持
- 如缺少，在 `\documentclass` 之后自动添加：
  ```latex
  \usepackage{xeCJK}
  \setCJKmainfont{SimSun}  % 或其他可用中文字体
  ```
- 英文输出通常无需额外处理

## 术语表格式

术语表文件（YAML）格式：

```yaml
# glossary.yaml
# 格式：原文术语: 目标语言译文
# 空值表示保留原文不翻译

terms:
  mAP: mAP
  mAP@0.5: mAP@0.5
  attention mechanism: 注意力机制
  feature pyramid network: 特征金字塔网络
  backbone: 骨干网络
  neck: 颈部网络
  anchor-free: 无锚框
  wall crack: 墙体裂缝
  YOLOv11: null  # null = 保留原文
  
# 可选：领域标注，帮助消歧
domain: computer vision / object detection
```

## 质量保证

### 长文档一致性
- 翻译前先扫描全文，提取高频术语，自动构建临时术语表
- 每个分块翻译时注入该术语表，确保全篇一致

### 输出验证
- 翻译完成后，统计原文和译文的段落数，确保一一对应
- LaTeX 文件检查 `\begin`/`\end` 配对完整性
- 检查是否有未翻译的残留文本（通过语言检测）

## 示例用法

```bash
# 翻译一段摘要到英文
/translate 本文提出了一种基于改进YOLOv11的墙体裂缝实时检测方法

# 翻译 LaTeX 章节文件
/translate thesis/chapters/ch3.tex --to en --compile

# 用术语表翻译整个论文目录
/translate thesis/chapters/ --to en --glossary glossary.yaml --compile

# 翻译 arXiv 论文到中文
/translate arxiv:2502.17882

# 快速直译（跳过反思，速度优先）
/translate 一段文本 --draft-only

# 双语对照输出
/translate some paragraph --side-by-side
```

---

## 开始执行

输入：**$ARGUMENTS**

请按照上述流程处理。先解析参数、确定模式，然后执行三阶段翻译。
