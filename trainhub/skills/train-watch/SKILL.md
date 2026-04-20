---
name: train-watch
description: 轮询训练任务状态（Kaggle kernel / SSH tmux session / Colab runtime）。单次查询，不循环。要周期性监控请组合 /loop。触发词：查训练状态、kernel status、实验跑完没、training 进度。
---

# train-watch — 训练状态查询

## 参数
| 参数 | 必填 | 含义 |
|---|---|---|
| `run` | 是 | run_name（与 train-submit 对齐） |
| `platform` | 否（默认读 `.trainhub.json`） | kaggle / ssh / colab |

## 平台 adapter

### Kaggle
```bash
kaggle kernels status <account>/<kernel_prefix>-<run_name> 2>&1 | grep -v -i warning
```
状态映射：
- `RUNNING` → 继续
- `COMPLETE` → 调 `train-harvest run=<run_name>`
- `ERROR` / `CANCELLED` → 拉 log 诊断：
  ```bash
  kaggle kernels output <id> -p /tmp/kg-err-<run_name>
  tail -100 /tmp/kg-err-<run_name>/<script_name>.log
  ```

### SSH
```bash
ssh <host> 'tmux list-sessions 2>/dev/null | grep <run_name>'
ssh <host> 'tail -30 <remote_dir>/<run_name>/train.log'
```
- session 存在且 log 有最近输出 → RUNNING
- session 消失且 log 末尾有 `training complete` 或 `mAP` → COMPLETE
- session 消失且 log 有 `Error` / `Traceback` → ERROR

### Colab
Colab 没有服务端轮询 API。建议约定：训练脚本末尾 `curl -s` POST 一个 webhook（或把 results.csv 传到 Drive），train-watch 通过检查 Drive 判定完成。

## 循环监控建议
本 skill 单次查询。要每 10min 自动轮询用 `/loop`：
```
/loop 10m 跑 train-watch run=L2-P4-ema-p5-kaggle，COMPLETE 时调 train-harvest
```

## 和 `/loop` 配合时的终止条件
Loop 内容里指定"所有 runs 都 COMPLETE 后 CronDelete"，避免空转。
