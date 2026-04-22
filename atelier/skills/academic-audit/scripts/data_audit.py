#!/usr/bin/env python3
"""数据集与实验结果自动审核工具。

用法:
    python data_audit.py --dataset-dir <path> [--results-dirs <path>...] [--output json|text]

功能:
    1. 验证数据集 train/val/test 划分完整性
    2. 检查图片-标签配对
    3. 解析 data.yaml 配置
    4. 提取 results.csv 关键指标
    5. 跨目录结果对比
"""

import argparse
import json
from pathlib import Path

import yaml


def check_dataset(dataset_dir: Path) -> dict:
    """验证 YOLO 数据集的完整性。"""
    report = {"path": str(dataset_dir), "splits": {}, "issues": [], "data_yaml": None}

    # 解析 data.yaml
    data_yaml = dataset_dir / "data.yaml"
    if data_yaml.exists():
        with open(data_yaml) as f:
            cfg = yaml.safe_load(f)
        report["data_yaml"] = {
            "nc": cfg.get("nc"),
            "names": cfg.get("names"),
            "path": cfg.get("path"),
        }
    else:
        report["issues"].append({"severity": "HIGH", "message": "data.yaml 不存在"})

    # 检查各划分
    for split in ["train", "valid", "test"]:
        split_info = {"images": 0, "labels": 0, "orphan_images": [], "orphan_labels": []}
        img_dir = dataset_dir / split / "images"
        lbl_dir = dataset_dir / split / "labels"

        if not img_dir.exists():
            # 尝试其他命名
            for alt in [dataset_dir / "images" / split, dataset_dir / split]:
                if alt.exists():
                    img_dir = alt
                    break

        if not lbl_dir.exists():
            for alt in [dataset_dir / "labels" / split]:
                if alt.exists():
                    lbl_dir = alt
                    break

        if img_dir.exists():
            img_stems = set()
            for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.webp"):
                for f in img_dir.glob(ext):
                    img_stems.add(f.stem)
            split_info["images"] = len(img_stems)
        else:
            report["issues"].append(
                {"severity": "HIGH", "message": f"{split}/images 目录不存在"}
            )
            img_stems = set()

        if lbl_dir.exists():
            lbl_stems = {f.stem for f in lbl_dir.glob("*.txt")}
            split_info["labels"] = len(lbl_stems)
        else:
            if split_info["images"] > 0:
                report["issues"].append(
                    {"severity": "HIGH", "message": f"{split}/labels 目录不存在"}
                )
            lbl_stems = set()

        # 孤立文件检查
        orphan_imgs = img_stems - lbl_stems
        orphan_lbls = lbl_stems - img_stems
        if orphan_imgs:
            split_info["orphan_images"] = sorted(list(orphan_imgs))[:20]  # 最多列 20 个
            report["issues"].append(
                {
                    "severity": "MEDIUM",
                    "message": f"{split}: {len(orphan_imgs)} 张图片无标签",
                }
            )
        if orphan_lbls:
            split_info["orphan_labels"] = sorted(list(orphan_lbls))[:20]
            report["issues"].append(
                {
                    "severity": "MEDIUM",
                    "message": f"{split}: {len(orphan_lbls)} 个标签无图片",
                }
            )

        report["splits"][split] = split_info

    return report


def parse_results_csv(csv_path: Path) -> dict | None:
    """从 ultralytics results.csv 提取关键指标。"""
    try:
        lines = csv_path.read_text().strip().split("\n")
        if len(lines) < 2:
            return None

        # 解析 header（ultralytics 的 CSV header 有前导空格）
        header = [h.strip() for h in lines[0].split(",")]
        rows = []
        for line in lines[1:]:
            vals = [v.strip() for v in line.split(",")]
            if len(vals) == len(header):
                rows.append(dict(zip(header, vals)))

        if not rows:
            return None

        # 找 mAP50 列（不同版本列名可能不同）
        map50_col = None
        for col in header:
            if "metrics/mAP50(B)" in col or "mAP_0.5" in col or "mAP50" in col:
                map50_col = col
                break

        map5095_col = None
        for col in header:
            if "metrics/mAP50-95(B)" in col or "mAP_0.5:0.95" in col:
                map5095_col = col
                break

        result = {
            "path": str(csv_path),
            "epochs": len(rows),
            "columns": header,
        }

        if map50_col:
            vals = [float(r[map50_col]) for r in rows if r.get(map50_col)]
            if vals:
                best_idx = max(range(len(vals)), key=lambda i: vals[i])
                result["best_mAP50"] = round(vals[best_idx], 4)
                result["best_mAP50_epoch"] = best_idx + 1
                result["last_mAP50"] = round(vals[-1], 4)

        if map5095_col:
            vals = [float(r[map5095_col]) for r in rows if r.get(map5095_col)]
            if vals:
                best_idx = max(range(len(vals)), key=lambda i: vals[i])
                result["best_mAP50-95"] = round(vals[best_idx], 4)

        return result
    except Exception as e:
        return {"path": str(csv_path), "error": str(e)}


def scan_results(results_dirs: list[Path]) -> dict:
    """扫描多个结果目录，提取所有实验的关键指标。"""
    all_results = {}
    for rdir in results_dirs:
        if not rdir.exists():
            continue
        dir_results = {}
        for csv_file in sorted(rdir.rglob("results.csv")):
            # 用相对路径作为实验名
            rel = csv_file.relative_to(rdir).parent
            exp_name = str(rel) if str(rel) != "." else rdir.name
            parsed = parse_results_csv(csv_file)
            if parsed:
                dir_results[exp_name] = parsed
        all_results[str(rdir)] = dir_results
    return all_results


def cross_compare(all_results: dict) -> list[dict]:
    """跨目录对比同名实验的 mAP50。"""
    # 收集所有实验名
    exp_values = {}
    for dir_path, experiments in all_results.items():
        for exp_name, data in experiments.items():
            if "best_mAP50" in data:
                key = exp_name.split("/")[-1]  # 取最后一段作为规范名
                if key not in exp_values:
                    exp_values[key] = []
                exp_values[key].append(
                    {
                        "source": dir_path,
                        "full_name": exp_name,
                        "mAP50": data["best_mAP50"],
                        "epoch": data.get("best_mAP50_epoch"),
                    }
                )

    comparisons = []
    for exp_name, runs in exp_values.items():
        if len(runs) > 1:
            vals = [r["mAP50"] for r in runs]
            delta = max(vals) - min(vals)
            comparisons.append(
                {
                    "experiment": exp_name,
                    "runs": runs,
                    "delta": round(delta, 4),
                    "consistent": delta < 0.03,  # 3pp 阈值
                }
            )
    return comparisons


def main():
    parser = argparse.ArgumentParser(description="数据集与实验结果审核工具")
    parser.add_argument("--dataset-dir", type=Path, help="数据集根目录")
    parser.add_argument(
        "--results-dirs", type=Path, nargs="+", default=[], help="结果目录列表"
    )
    parser.add_argument("--output", choices=["json", "text"], default="text")
    args = parser.parse_args()

    report = {"dataset": None, "results": {}, "comparisons": [], "score": None}

    # 数据集审核
    if args.dataset_dir:
        report["dataset"] = check_dataset(args.dataset_dir)

    # 结果扫描
    if args.results_dirs:
        report["results"] = scan_results(args.results_dirs)
        report["comparisons"] = cross_compare(report["results"])

    # 评分
    score = 10.0
    if report["dataset"]:
        for issue in report["dataset"]["issues"]:
            if issue["severity"] == "HIGH":
                score -= 2.0
            elif issue["severity"] == "MEDIUM":
                score -= 0.5
    if report["comparisons"]:
        inconsistent = sum(1 for c in report["comparisons"] if not c["consistent"])
        score -= inconsistent * 0.5
    report["score"] = max(0, min(10, round(score, 1)))

    # 输出
    if args.output == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_text(report)


def _print_text(report: dict):
    print("=" * 60)
    print("数据集与实验结果审核报告")
    print("=" * 60)

    if report["dataset"]:
        ds = report["dataset"]
        print(f"\n📁 数据集: {ds['path']}")
        if ds["data_yaml"]:
            y = ds["data_yaml"]
            print(f"   nc={y['nc']}, names={y['names']}")
        print(f"\n   {'划分':<8} {'图片':>6} {'标签':>6} {'状态'}")
        print(f"   {'─'*8} {'─'*6} {'─'*6} {'─'*10}")
        for split, info in ds["splits"].items():
            status = "✅" if not info["orphan_images"] and not info["orphan_labels"] else "⚠️"
            print(f"   {split:<8} {info['images']:>6} {info['labels']:>6} {status}")

        if ds["issues"]:
            print("\n   ⚠️ 问题:")
            for issue in ds["issues"]:
                print(f"   [{issue['severity']}] {issue['message']}")

    if report["results"]:
        print(f"\n📊 实验结果 ({sum(len(v) for v in report['results'].values())} 个实验)")
        for dir_path, experiments in report["results"].items():
            print(f"\n   {dir_path}:")
            for exp_name, data in sorted(experiments.items()):
                if "error" in data:
                    print(f"   ❌ {exp_name}: {data['error']}")
                elif "best_mAP50" in data:
                    print(
                        f"   {exp_name}: mAP50={data['best_mAP50']:.4f} "
                        f"(epoch {data.get('best_mAP50_epoch', '?')}/{data['epochs']})"
                    )

    if report["comparisons"]:
        print("\n🔄 跨目录一致性对比:")
        for comp in report["comparisons"]:
            status = "✅" if comp["consistent"] else "⚠️"
            vals = ", ".join(f"{r['mAP50']:.4f}" for r in comp["runs"])
            print(f"   {status} {comp['experiment']}: [{vals}] Δ={comp['delta']:.4f}")

    print(f"\n📊 评分: {report['score']}/10")


if __name__ == "__main__":
    main()
