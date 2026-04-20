---
name: train-harvest
description: 训练完成后下载产物，解析指标，归档到 weights/ 目录。接在 train-watch 检测到 COMPLETE 之后。触发词：收实验结果、下载 kernel output、归档 weights、parse results.csv。
---

# train-harvest — 结果回收 + 归档

## 参数
| 参数 | 必填 | 含义 |
|---|---|---|
| `run` | 是 | run_name |
| `platform` | 否（默认读 `.trainhub.json`） | kaggle / ssh / colab |

## 平台 adapter

### Kaggle
```bash
kaggle kernels output <account>/<kernel_prefix>-<run_name> -p /tmp/kg-<run_name>
# 产物通常是 <run_name>.zip 里面打包了整个 results/<run_name>/
unzip -q /tmp/kg-<run_name>/<run_name>.zip -d /tmp/kg-<run_name>/extracted/
```

### SSH
```bash
rsync -az <host>:<remote_dir>/<run_name>/results/ /tmp/ssh-<run_name>/
```

### Colab
从 Google Drive 的 `drive_folder/<run_name>/` 下载（用 rclone 或 gdown）。

## 指标解析（读 `.trainhub.json.metric`）

```bash
# 最佳 epoch 行（按 primary metric 的 best_fn=max/min）
awk -F',' -v col="metrics/mAP50(B)" '
  NR==1 { for(i=1;i<=NF;i++) if($i==col) k=i; next }
  { if(!best || $k>best){ best=$k; row=$0 } }
  END { print row }
' results.csv
```

提取：`epoch`, `metrics/mAP50(B)`, `metrics/mAP50-95(B)`, `metrics/precision(B)`, `metrics/recall(B)`

## 归档（按 `.trainhub.json.archive`）
```bash
target="<weights_dir>/<filename_pattern>"  # 如 weights/L2-P4-ema-p5-kaggle/
mkdir -p "$target"
cp /tmp/*/extracted/**/best.pt "$target/"
cp /tmp/*/extracted/**/results.csv "$target/"
```

## CHRONICLE 写入
若项目有 `docs/CHRONICLE.md`，追加一条实验条目，格式：
```markdown
### <run_name>（YYYY-MM-DD 完成）
- 平台：<platform>
- 最佳 mAP50: <val> @ epoch <n>
- 对照 baseline <baseline_val> → Δ <diff> pp
- weights 归档：<target>
- 备注：<自动空或 TODO>
```

baseline 数值从 `.trainhub.json.metric.baseline` 读（没有就留 `TODO`）。

## 清理
harvest 成功后删 `/tmp/<platform>-<run_name>/` 临时目录，避免 /tmp 堆积。
