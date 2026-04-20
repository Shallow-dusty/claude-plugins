---
name: train-config
description: 配置或查看项目的训练平台默认值（Kaggle/Colab/SSH 远程 GPU）。首次在项目中使用 trainhub 前运行，或要切换默认平台、更新凭据引用、调整指标口径时使用。触发词：配置训练平台、setup training、训练默认值、切平台。
---

# train-config — 项目训练平台配置

## 职责
管理项目级 `.trainhub.json`（放在项目根），声明本项目训练任务的默认平台、运行命名、指标解析规则。让后续 `train-submit` / `train-watch` / `train-harvest` 零额外参数就能跑。

## `.trainhub.json` 结构

```json
{
  "default_platform": "kaggle",
  "platforms": {
    "kaggle": {
      "account": "lilliareverie",
      "dataset_sources": ["lilliareverie/my-dataset"],
      "kernel_prefix": "project-exp",
      "enable_gpu": true,
      "enable_internet": true
    },
    "ssh": {
      "host": "kindred@100.70.77.33",
      "remote_dir": "/home/kindred/runs",
      "conda_env": "ml"
    },
    "colab": {
      "notebook_template": "templates/colab_train.ipynb",
      "drive_folder": "MyDrive/ml-runs"
    }
  },
  "metric": {
    "primary": "mAP50",
    "source": "results.csv",
    "best_fn": "max"
  },
  "archive": {
    "weights_dir": "weights/",
    "filename_pattern": "{platform}-{run_name}/",
    "keep": ["best.pt", "results.csv"]
  }
}
```

## 何时新建
- 项目首次要提交训练任务
- 换平台（如毕业后实验室给新 GPU 服务器）
- 指标从 `mAP50` 换成 `accuracy` / `F1` 等

## 行为
1. 如果 `.trainhub.json` 不存在 → 向用户询问必要字段（default_platform、account/host、metric.primary），写入最小配置
2. 如果存在 → 展示当前配置，询问要改什么
3. 凭据**不存** `.trainhub.json`（引用 `~/.secrets/.env` 对应段），只存 account name / host alias

## 凭据引用约定
- Kaggle：`~/.kaggle/kaggle.json`（kaggle CLI 标准位置）
- SSH：`~/.ssh/config` 的 Host 别名
- Colab：浏览器 OAuth（无配置）

## 注意
- `.trainhub.json` **进 git**（无敏感信息）
- 项目未初始化过就直接调 train-submit → 先 prompt 跑 train-config
