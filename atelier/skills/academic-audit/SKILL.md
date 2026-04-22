---
name: academic-audit
description: "全面审核学术项目的论文质量、数据完整性、代码规范和工程化水平。两阶段：Phase 1 自动扫描（秒级脚本）+ Phase 2 AI 深度审核（多 agent 团队）。务必在以下场景触发：用户说审计/审核/体检/检查项目、验证数据一致性、检查论文质量或格式、查重风险评估、AIGC 检测或降风险、投稿前检查、代码审查（针对整个项目而非单个 PR）、检查 git 历史或依赖安全、可复现性验证、开源合规检查。即使用户只说'帮我检查一下'或'看看有没有问题'，只要上下文涉及学术项目或论文，也应该触发。不要在用户只想修单个 bug、写新代码、跑实验、翻译、做 PPT 时触发。"
allowed-tools: Bash, Read, Glob, Grep, Agent, Write, Edit, TaskCreate, TaskUpdate, TaskList, TeamCreate, SendMessage
---

# Academic Audit — 学术项目全面审核

一个两阶段审核系统：**自动扫描**（定量，秒级）+ **AI 深度审核**（定性，agent 团队）。

## 设计理念

- **脚本做定量，AI 做定性** — 文件计数、引用匹配等确定性检查交给脚本；论文逻辑、AIGC 风格、架构评价交给 agent
- **评分可复现** — 基于 `references/rubric.yaml` 的量化评分量表，消除主观性
- **增量审计** — 对比上次审计结果，追踪修复进度
- **可配置** — 通过 profile 选择审核维度和深度

## 使用方式

```
/academic-audit                     # 完整审核（Phase 1 + 询问是否启动 Phase 2）
/academic-audit scan                # 仅 Phase 1 自动扫描
/academic-audit deep                # 跳过扫描，直接 Phase 2 AI 深度审核
/academic-audit --profile minimal   # 快速检查（仅数据+LaTeX）
/academic-audit --profile journal   # 期刊投稿前专项检查
```

## Phase 1: 自动扫描（30 秒内完成）

运行 `scripts/` 下的工具脚本，产出量化指标。

### 步骤

1. **检测项目类型** — 扫描目录结构，识别有哪些可审核的内容：
   - 存在 `datasets/` + `*.yaml` → 启用 data_audit
   - 存在 `*.tex` + `*.bib` → 启用 latex_audit
   - 存在 `.git/` → 启用 git_health
   - 存在 `*.py` + `requirements.txt` → 启用 code_metrics（如有 ruff/radon）
   - 存在 `Dockerfile` → 检查 Docker 配置

2. **运行工具脚本** — 对每个检测到的维度并行执行：

```bash
# 数据集审核
python <skill-path>/scripts/data_audit.py \
  --dataset-dir <path> \
  --results-dirs <dir1> <dir2> ... \
  --output json > scan_data.json

# LaTeX 审核
python <skill-path>/scripts/latex_audit.py \
  --thesis-dir <path> \
  --output json > scan_latex.json

# Git 健康度
python <skill-path>/scripts/git_health.py \
  --repo-dir <path> \
  --output json > scan_git.json
```

3. **汇总评分** — 读取 `references/rubric.yaml`，基于脚本输出计算各维度分数，输出汇总表。

4. **展示结果并询问**:
   - 显示各维度评分表 + 发现的问题清单
   - 询问用户："自动扫描完成。是否启动 AI 深度审核？（论文逻辑/AIGC 检测/代码架构等需要 AI 判断的维度）"

### 工具脚本说明

| 脚本 | 功能 | 依赖 |
|------|------|------|
| `data_audit.py` | 数据集完整性 + 实验结果提取与对比 | pyyaml |
| `latex_audit.py` | 引用匹配 + 编译日志 + label/ref 配对 | 无 |
| `git_health.py` | 大文件检测 + commit 规范 + 凭据泄漏 | git CLI |

脚本均支持 `--output json` 用于机器解析和 `--output text` 用于人类阅读。

## Phase 2: AI 深度审核（需用户确认）

基于 Phase 1 扫描结果，组建 agent 团队进行定性分析。

### agent 团队配置

根据项目内容动态组建团队，**只派出需要的 agent**：

| 条件 | agent | 审核内容 |
|------|-------|---------|
| 存在 .tex 论文 | `paper-structure` | 章节结构、逻辑链、学术语言 |
| 存在 .tex 论文 | `paper-quality` | AIGC 风格检测、查重风险评估 |
| 存在 Python 代码 | `code-reviewer` | 代码质量、架构设计、正确性 |
| 多个实验/内核 | `reproducibility` | 跨平台一致性、可复现性 |
| 开源/投稿需求 | `project-arch` | 工程化、LICENSE、CI/CD |

### agent 协作原则

1. **Phase 1 结果作为输入** — 不让 agent 重复做定量检查。将 `scan_*.json` 的关键数据直接注入 agent prompt。
2. **共享发现板** — 第一个发现某问题的 agent 记录到 task 系统，后续 agent 跳过重复分析。
3. **标准化报告模板** — 每个 agent 按统一格式输出（severity 分级、位置标注、修复建议）。

### agent prompt 模板

为每个 agent 提供：
- 项目背景（从 CLAUDE.md 或用户输入获取）
- Phase 1 扫描结果（相关维度的 JSON）
- 明确的审核维度清单
- 报告格式要求
- 完成后通过 TaskUpdate 标记任务完成

## Phase 3: 归档

审核完成后自动归档：

1. 在项目中创建 `audit/{date}_<type>/` 目录
2. 写入：
   - `00-SUMMARY.md` — 综合报告 + 评分 + 行动清单
   - `scan_*.json` — Phase 1 原始数据
   - `01-*.md` ~ `08-*.md` — 各 agent 详细报告（如有）
3. 更新 `audit/README.md` 审计索引
4. 如有上次审计，生成 diff 报告（新增/已修复/未修复）

## 审核 Profile

读取 `references/profiles/` 下的 YAML 配置选择审核范围：

### thesis（默认）— 毕设全面审核
```yaml
phase1: [data, latex, git, code]
phase2: [paper-structure, paper-quality, code-reviewer, project-arch]
archive: true
```

### journal — 期刊投稿前审核
```yaml
phase1: [data, latex, git]
phase2: [paper-quality, reproducibility]  # 重点: AIGC + 可复现性
archive: true
extra_checks:
  - aigc_focus: true       # AIGC 检测加深
  - cross_dataset: true    # 跨数据集验证
```

### minimal — 快速检查
```yaml
phase1: [data, latex]
phase2: []  # 不启动 AI 审核
archive: false
```

## 评分体系

读取 `references/rubric.yaml` 获取各维度的评分锚点和权重。

加权综合分 = Σ(维度分数 × 权重) / Σ(权重)

等级映射：A(9-10), B+(8-8.9), B(7-7.9), C+(6-6.9), C(5-5.9), D(<5)

## 增量审计（第 2 次+）

如果 `audit/` 目录中存在历次审计记录：
1. 读取上次审计的 `00-SUMMARY.md`
2. 对比本次扫描结果，生成 diff:
   - ✅ 已修复的问题
   - ⚠️ 仍未修复的问题
   - 🆕 新发现的问题
3. 将 diff 加入本次报告

## 未来扩展（TODO）

- [ ] `aigc_heuristic.py` — 基于句式模式的 AIGC 启发式检测
- [ ] `code_metrics.py` — ruff + radon 封装
- [ ] `dep_audit.py` — pip-audit 漏洞扫描封装
- [ ] `reproducibility.py` — seed/deterministic/Docker 检查
- [ ] MCP Plugin 化 — 将脚本注册为 MCP tool，支持任意客户端调用
