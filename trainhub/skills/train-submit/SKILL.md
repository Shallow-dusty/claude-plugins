---
name: train-submit
description: 把训练任务派发到目标平台（Kaggle kernel / Colab notebook / SSH 远程主机）。适用：在本地准备好代码 + 配置后，推到远端开跑。触发词：提交训练、push kernel、run on kaggle/colab/ssh、派发实验。
---

# train-submit — 派发训练任务

## 先决条件
- 项目已有 `.trainhub.json`（未有 → 先跑 `train-config`）
- 目标平台对应凭据已配好（Kaggle: `~/.kaggle/kaggle.json`；SSH: ssh-config Host；Colab: 浏览器登录）

## 参数
| 参数 | 可选 | 含义 | 示例 |
|---|---|---|---|
| `platform` | 默认读 `.trainhub.json` | `kaggle` / `colab` / `ssh` | `platform=kaggle` |
| `script` | 必填 | 训练入口脚本 | `kaggle_kernels/L2-ema-p5/l2_ema.py` |
| `run_name` | 必填 | 运行唯一命名 | `L2-P4-ema-p5-kaggle` |
| `dataset` | Kaggle 专属 | 输入数据集 slug | `lilliareverie/wall-crack-v2-split` |

## 平台 adapter 逻辑

### Kaggle
1. 检查或生成 `kernel-metadata.json`（用 `.trainhub.json.platforms.kaggle` 填默认字段 + `run_name` → `id = "{account}/{kernel_prefix}-{run_name}"`）
2. `kaggle kernels push -p <kernel-dir>`
3. 返回 kernel id 给用户

### SSH
1. `rsync` 代码到 `platforms.ssh.remote_dir/{run_name}/`
2. 通过 `ssh host 'cd remote_dir/run_name && tmux new-session -d -s run_name "conda activate {conda_env} && python script > train.log 2>&1"'`
3. 返回 tmux session id + log 路径

### Colab
半自动：生成好 notebook 复制到 Drive → 指示用户打开 Colab 手动点 Run all（Colab 没有正式 CLI 派发 API）

## 并发规则
- Kaggle 免费账号同时最多 2 个 session — 提交前 `kaggle kernels list --mine` 检查
- SSH 用 tmux session 名防重复占用 GPU
- 同一 `run_name` 已存在 → 提示用户决定覆盖/改名

## 提交后
打印一条关键信息：下一步怎么 watch
```
提交成功。下一步：
  train-watch run={run_name} platform={platform}
  或 /loop 10m train-watch run={run_name}
```
