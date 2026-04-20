---
name: exp-table
description: 从实验数据文件自动生成 LaTeX 表格。用法：/exp-table [表格类型] [选项]。消除手工抄录错误，支持期刊改写时快速切换格式。
---

# 实验数据表格生成器

从权威数据源自动生成论文所需的 LaTeX 表格代码，确保数据零误差。

## 数据源位置

### 测试集数据 (Single Source of Truth)

`results/supplementary/test_set_results.json` — 包含 E0-E7 的 P/R/F1/mAP50/mAP50-95/推理速度。

### 验证集数据 (需从 CSV 提取 best-epoch)

每个实验的 **论文权威来源**（即论文中实际引用的那一轮训练）：

| 实验 | 权威 CSV 路径 | 训练平台 |
|------|--------------|----------|
| E0 | `results/E0_baseline/results_3070_run1.csv` | 3070 (Kaggle原始已覆盖) |
| E1 | `results/E1_cbam/results.csv` | 3070 原始 |
| E2 | `results/E2_eca/results.csv` | 3070 原始 |
| E3 | `results/kaggle_phase2_output/results/E3_wiou/results.csv` | Kaggle P100 |
| E4 | `results/kaggle_phase2_output/results/E4_augment/results.csv` | Kaggle P100 |
| E5 | `results/E5_cbam_wiou/results.csv` | 3070 原始 |
| E6 | `results/kaggle_phase2_output/results/E6_eca_augment/results.csv` | Kaggle P100 |
| E7 | `results_3070_run1/E7_all/results.csv` | 3070 |

CSV 列格式: `epoch,time,...,metrics/precision(B),metrics/recall(B),metrics/mAP50(B),metrics/mAP50-95(B),...`
- Precision = 第 6 列 (0-indexed: 5)
- Recall = 第 7 列 (0-indexed: 6)
- mAP50 = 第 8 列 (0-indexed: 7)
- mAP50-95 = 第 9 列 (0-indexed: 8)

**提取规则**: 取整个训练过程中 **mAP50 最大的那一行**（best epoch），不是最后一行。

### 参数量

固定值（模型结构决定，不会变）：

| 实验 | 参数量 |
|------|--------|
| E0 | 2.59M |
| E1 | 2.69M |
| E2 | 2.59M |
| E3 | 2.59M |
| E4 | 2.59M |
| E5 | 2.69M |
| E6 | 2.59M |
| E7 | 2.67M |

### 改进标签

| 实验 | 标签 |
|------|------|
| E0 | Baseline |
| E1 | +CBAM |
| E2 | +ECA |
| E3 | +WIoU |
| E4 | +Mixup |
| E5 | +CBAM+WIoU |
| E6 | +ECA+Mixup |
| E7 | All |

## 可用表格类型

### `ablation` — 消融实验总表（验证集）

对应 `\label{tab:ablation_results}`。包含所有 E0-E7，列：实验/改进/Params/P/R/F1/mAP50/mAP50-95/Delta。

### `single` — 单模块消融（验证集）

对应 `\label{tab:single_module}`。仅 E0-E4，列：实验/改进/P/R/mAP50/DeltaP/DeltaR/DeltamAP50。

### `combo` — 组合消融（验证集）

对应 `\label{tab:combo_results}`。E0 + E5-E7，列：实验/改进/P/R/mAP50/mAP50-95/DeltamAP50。

### `test` — 测试集性能（直接读 JSON）

对应 `\label{tab:test_results}`。全部 E0-E7，列：实验/改进/P/R/F1/mAP50/mAP50-95/推理ms/Delta。

### `custom` — 自定义格式

用户指定实验子集和列，生成任意格式。用于期刊投稿时适配不同模板。

## 生成流程

1. **读取数据**: 根据表格类型决定读 JSON（test）还是 CSV（val），用上面的路径映射
2. **提取 best-epoch**: 对 CSV，遍历所有行找 mAP50 最大值所在行
3. **计算衍生列**: Delta = 该实验值 - E0 值；F1 = 2*P*R/(P+R)
4. **格式化数值**: 小数点 3 位 (0.xxx)；百分点 1 位 (+x.x / -x.x)
5. **加粗最优值**: 每列数值最优的加 `\textbf{}`
6. **生成 LaTeX**: 包含 `\begin{table}...\end{table}` 完整环境
7. **输出**: 直接打印 LaTeX 代码，用户复制到论文中

## 用法示例

```
/exp-table ablation          # 生成验证集消融总表
/exp-table test              # 生成测试集表
/exp-table single            # 生成单模块对比表
/exp-table combo             # 生成组合实验表
/exp-table custom E0 E2 E7 --cols P,R,mAP50 --set val   # 自定义
```

## 注意事项

- **验证集 vs 测试集**: 论文的主要结论基于验证集（best epoch），测试集用于补充验证
- **数据冻结**: 所有训练已完成，数据不会变化
- **四舍五入**: 小数第 4 位四舍五入到第 3 位，与论文现有精度一致
- **Delta 符号**: 正值显示 `+x.x`，负值显示 `$-$x.x`（LaTeX 负号用数学模式）
