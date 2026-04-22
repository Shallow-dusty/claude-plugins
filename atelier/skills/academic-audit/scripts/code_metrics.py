#!/usr/bin/env python3
"""代码质量度量工具。

用法:
    python code_metrics.py --src-dir <path> [--output json|text]

功能:
    1. 运行 ruff check (如果可用)
    2. 统计代码行数和文件数
    3. 检测重复代码块 (简单哈希比较)
    4. 检查 requirements.txt / pyproject.toml 一致性
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def run_ruff(src_dir: Path) -> dict:
    """运行 ruff check，返回违规统计。"""
    try:
        result = subprocess.run(
            ["ruff", "check", str(src_dir), "--output-format=json", "--quiet"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        violations = json.loads(result.stdout) if result.stdout.strip() else []
        by_rule = {}
        for v in violations:
            code = v.get("code", "unknown")
            by_rule[code] = by_rule.get(code, 0) + 1
        return {
            "available": True,
            "total_violations": len(violations),
            "by_rule": dict(sorted(by_rule.items(), key=lambda x: -x[1])[:20]),
            "files_with_issues": len(set(v.get("filename", "") for v in violations)),
        }
    except FileNotFoundError:
        return {"available": False, "note": "ruff 未安装"}
    except Exception as e:
        return {"available": False, "error": str(e)}


def count_lines(src_dir: Path) -> dict:
    """统计代码行数。"""
    stats = {}
    skip_dirs = {"__pycache__", ".archive", "venv", ".venv", "node_modules", ".git", ".tessl", ".claude"}
    for py_file in sorted(src_dir.rglob("*.py")):
        if any(d in py_file.parts for d in skip_dirs):
            continue
        try:
            lines = py_file.read_text(encoding="utf-8", errors="replace").split("\n")
            code_lines = sum(1 for l in lines if l.strip() and not l.strip().startswith("#"))
            rel = str(py_file.relative_to(src_dir))
            stats[rel] = {
                "total": len(lines),
                "code": code_lines,
                "blank": sum(1 for l in lines if not l.strip()),
                "comment": sum(1 for l in lines if l.strip().startswith("#")),
            }
        except Exception:
            pass

    total = {
        "files": len(stats),
        "total_lines": sum(s["total"] for s in stats.values()),
        "code_lines": sum(s["code"] for s in stats.values()),
    }
    return {"files": stats, "total": total}


def find_duplicate_blocks(src_dir: Path, min_lines: int = 6) -> list[dict]:
    """检测重复代码块（简单的滑动窗口哈希）。"""
    # 收集所有文件的代码行
    file_lines = {}
    skip_dirs = {"__pycache__", ".archive", "venv", ".venv", "node_modules", ".git", ".tessl", ".claude"}
    for py_file in sorted(src_dir.rglob("*.py")):
        if any(d in py_file.parts for d in skip_dirs):
            continue
        try:
            lines = py_file.read_text(encoding="utf-8", errors="replace").split("\n")
            # 标准化：去除首尾空格、统一缩进
            normalized = [l.strip() for l in lines]
            rel = str(py_file.relative_to(src_dir))
            file_lines[rel] = normalized
        except Exception:
            pass

    # 滑动窗口哈希检测
    block_hashes = {}  # hash -> [(file, start_line), ...]
    for fname, lines in file_lines.items():
        for i in range(len(lines) - min_lines + 1):
            block = "\n".join(lines[i : i + min_lines])
            # 跳过空块或纯注释块
            code_lines = [l for l in lines[i : i + min_lines] if l and not l.startswith("#")]
            if len(code_lines) < min_lines // 2:
                continue
            h = hashlib.md5(block.encode()).hexdigest()
            if h not in block_hashes:
                block_hashes[h] = []
            block_hashes[h].append({"file": fname, "line": i + 1})

    # 找出出现在多个文件中的重复块
    duplicates = []
    seen_pairs = set()
    for h, locations in block_hashes.items():
        files = set(loc["file"] for loc in locations)
        if len(files) > 1:  # 跨文件重复
            pair_key = tuple(sorted(files))
            if pair_key not in seen_pairs:
                seen_pairs.add(pair_key)
                # 获取代码片段预览
                first_loc = locations[0]
                lines = file_lines[first_loc["file"]]
                preview = "\n".join(lines[first_loc["line"] - 1 : first_loc["line"] - 1 + min_lines])
                duplicates.append({
                    "locations": [{"file": loc["file"], "line": loc["line"]} for loc in locations if loc["file"] in files],
                    "preview": preview[:200],
                    "block_lines": min_lines,
                })

    return duplicates[:20]  # 限制数量


def check_deps(src_dir: Path) -> dict:
    """检查依赖文件。"""
    report = {"requirements_txt": None, "pyproject_toml": None, "issues": []}

    req_file = src_dir / "requirements.txt"
    if req_file.exists():
        lines = [l.strip() for l in req_file.read_text().split("\n") if l.strip() and not l.startswith("#")]
        pinned = sum(1 for l in lines if "==" in l)
        report["requirements_txt"] = {
            "total": len(lines),
            "pinned": pinned,
            "unpinned": len(lines) - pinned,
            "pin_ratio": round(pinned / len(lines), 2) if lines else 0,
        }

    pyproject = src_dir / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text()
        has_project = "[project]" in content
        has_ruff = "[tool.ruff" in content
        report["pyproject_toml"] = {
            "has_project_section": has_project,
            "has_ruff_config": has_ruff,
        }
        if not has_project:
            report["issues"].append("[pyproject.toml] 缺少 [project] 元数据段")

    if not req_file.exists() and not pyproject.exists():
        report["issues"].append("无依赖声明文件 (requirements.txt 或 pyproject.toml)")

    return report


def audit(src_dir: Path) -> dict:
    """执行完整代码度量审核。"""
    report = {
        "path": str(src_dir),
        "ruff": run_ruff(src_dir),
        "lines": count_lines(src_dir),
        "duplicates": find_duplicate_blocks(src_dir),
        "dependencies": check_deps(src_dir),
        "issues": [],
    }

    # 评分
    score = 10.0
    if report["ruff"].get("available"):
        violations = report["ruff"]["total_violations"]
        if violations > 30:
            score -= 2.0
        elif violations > 10:
            score -= 1.0
        elif violations > 0:
            score -= 0.3
    if len(report["duplicates"]) > 5:
        score -= 1.5
    elif len(report["duplicates"]) > 2:
        score -= 0.5
    for issue in report["dependencies"].get("issues", []):
        score -= 0.5
        report["issues"].append({"severity": "MEDIUM", "message": issue})

    report["score"] = max(0, min(10, round(score, 1)))
    return report


def _print_text(report: dict):
    print("=" * 60)
    print("代码质量度量报告")
    print("=" * 60)

    lines = report["lines"]["total"]
    print(f"\n📊 代码统计: {lines['files']} 个文件, {lines['code_lines']} 行代码 ({lines['total_lines']} 行总计)")

    top_files = sorted(report["lines"]["files"].items(), key=lambda x: -x[1]["code"])[:10]
    if top_files:
        print("\n   最大文件:")
        for fname, stats in top_files:
            print(f"   {stats['code']:>5} 行  {fname}")

    ruff = report["ruff"]
    if ruff.get("available"):
        print(f"\n🔍 Ruff: {ruff['total_violations']} 个违规 ({ruff['files_with_issues']} 个文件)")
        if ruff["by_rule"]:
            print("   按规则:")
            for rule, cnt in list(ruff["by_rule"].items())[:5]:
                print(f"   {cnt:>4}x  {rule}")
    else:
        print(f"\n🔍 Ruff: {ruff.get('note', ruff.get('error', '不可用'))}")

    if report["duplicates"]:
        print(f"\n🔄 跨文件重复代码块: {len(report['duplicates'])} 组")
        for dup in report["duplicates"][:5]:
            locs = ", ".join(f"{l['file']}:{l['line']}" for l in dup["locations"][:3])
            print(f"   → {locs}")
            print(f"     {dup['preview'][:100]}...")
    else:
        print("\n   ✅ 无跨文件重复代码块")

    deps = report["dependencies"]
    if deps["requirements_txt"]:
        r = deps["requirements_txt"]
        print(f"\n📦 依赖: {r['total']} 个, 锁定率 {r['pin_ratio']:.0%}")
    if deps["issues"]:
        for issue in deps["issues"]:
            print(f"   ⚠️ {issue}")

    print(f"\n📊 评分: {report['score']}/10")


def main():
    parser = argparse.ArgumentParser(description="代码质量度量")
    parser.add_argument("--src-dir", type=Path, required=True, help="源码根目录")
    parser.add_argument("--output", choices=["json", "text"], default="text")
    args = parser.parse_args()

    report = audit(args.src_dir)

    if args.output == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_text(report)


if __name__ == "__main__":
    main()
