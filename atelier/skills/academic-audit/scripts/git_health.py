#!/usr/bin/env python3
"""Git 仓库健康度自动审核工具。

用法:
    python git_health.py --repo-dir <path> [--output json|text]

功能:
    1. 检测 git 历史中的大文件
    2. 检查 .gitignore 覆盖率
    3. 分析 commit message 规范性 (conventional commits)
    4. 检查是否有凭据/密钥泄漏
    5. 统计分支和 tag 信息
"""

import argparse
import json
import re
import subprocess
from pathlib import Path


def run_git(repo_dir: Path, args: list[str]) -> str:
    """执行 git 命令。"""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_dir)] + args,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def check_large_files(repo_dir: Path, threshold_mb: float = 10) -> list[dict]:
    """检测 git 历史中的大文件。"""
    # 用 git rev-list 查找所有 blob
    output = run_git(
        repo_dir,
        ["rev-list", "--objects", "--all"],
    )
    if not output:
        return []

    # 获取所有 blob 大小
    blobs = output.split("\n")
    large_files = []

    # 批量获取大小（更高效）
    blob_hashes = []
    blob_names = {}
    for line in blobs:
        parts = line.split(None, 1)
        if len(parts) == 2:
            blob_hashes.append(parts[0])
            blob_names[parts[0]] = parts[1]

    # 用 cat-file --batch-check 批量查询
    if blob_hashes:
        try:
            proc = subprocess.run(
                ["git", "-C", str(repo_dir), "cat-file", "--batch-check"],
                input="\n".join(blob_hashes[:5000]),  # 限制数量
                capture_output=True,
                text=True,
                timeout=30,
            )
            for line in proc.stdout.strip().split("\n"):
                parts = line.split()
                if len(parts) >= 3 and parts[1] == "blob":
                    size = int(parts[2])
                    if size > threshold_mb * 1024 * 1024:
                        blob_hash = parts[0]
                        name = blob_names.get(blob_hash, "unknown")
                        large_files.append(
                            {
                                "path": name,
                                "size_mb": round(size / 1024 / 1024, 1),
                                "hash": blob_hash[:8],
                            }
                        )
        except Exception:
            pass

    return sorted(large_files, key=lambda x: -x["size_mb"])


def check_commit_quality(repo_dir: Path, max_commits: int = 100) -> dict:
    """分析 commit message 质量。"""
    output = run_git(repo_dir, ["log", f"--max-count={max_commits}", "--format=%s"])
    if not output:
        return {"total": 0, "conventional": 0, "percentage": 0}

    messages = output.split("\n")
    conventional_pattern = re.compile(
        r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)"
        r"(\(.+\))?\!?:\s.+"
    )

    conventional_count = 0
    samples_bad = []
    for msg in messages:
        if conventional_pattern.match(msg):
            conventional_count += 1
        elif len(samples_bad) < 5:
            samples_bad.append(msg[:80])

    return {
        "total": len(messages),
        "conventional": conventional_count,
        "percentage": round(conventional_count / len(messages) * 100, 1) if messages else 0,
        "non_conventional_samples": samples_bad,
    }


def check_secrets(repo_dir: Path) -> list[dict]:
    """检查可能的凭据泄漏。"""
    patterns = {
        ".env": "环境变量文件",
        "credentials": "凭据文件",
        "secret": "密钥文件",
        "token": "Token 文件",
        "password": "密码文件",
        ".pem": "PEM 证书",
        ".key": "密钥文件",
        "id_rsa": "SSH 私钥",
    }

    tracked_files = run_git(repo_dir, ["ls-files"])
    if not tracked_files:
        return []

    findings = []
    for tracked_file in tracked_files.split("\n"):
        lower = tracked_file.lower()
        for pattern, desc in patterns.items():
            if pattern in lower and not lower.endswith(".example") and not lower.endswith(".sample"):
                findings.append({"file": tracked_file, "type": desc, "severity": "HIGH"})
                break

    return findings


def check_gitignore(repo_dir: Path) -> dict:
    """评估 .gitignore 覆盖度。"""
    gitignore = repo_dir / ".gitignore"
    if not gitignore.exists():
        return {"exists": False, "lines": 0, "patterns": []}

    content = gitignore.read_text()
    patterns = [
        line.strip()
        for line in content.split("\n")
        if line.strip() and not line.startswith("#")
    ]

    # 检查常见应忽略的文件/目录
    recommended = {
        "__pycache__": "Python 缓存",
        "*.pyc": "Python 编译文件",
        ".env": "环境变量",
        "*.pt": "PyTorch 权重",
        "*.pth": "PyTorch 权重",
        "node_modules": "Node 依赖",
        ".vscode": "IDE 配置",
        "*.log": "日志文件",
    }

    missing = []
    for pattern, desc in recommended.items():
        found = any(pattern in p for p in patterns)
        if not found:
            # 检查是否通过其他模式覆盖
            if not any(p.startswith(pattern.replace("*", "")) for p in patterns):
                missing.append({"pattern": pattern, "description": desc})

    return {
        "exists": True,
        "lines": len(patterns),
        "missing_recommended": missing,
    }


def audit(repo_dir: Path) -> dict:
    """执行完整 Git 健康度审核。"""
    report = {
        "path": str(repo_dir),
        "is_git": (repo_dir / ".git").exists(),
        "large_files": [],
        "commits": {},
        "secrets": [],
        "gitignore": {},
        "branches": [],
        "issues": [],
    }

    if not report["is_git"]:
        report["issues"].append({"severity": "HIGH", "message": "不是 git 仓库"})
        report["score"] = 0
        return report

    report["large_files"] = check_large_files(repo_dir)
    report["commits"] = check_commit_quality(repo_dir)
    report["secrets"] = check_secrets(repo_dir)
    report["gitignore"] = check_gitignore(repo_dir)

    # 分支信息
    branches = run_git(repo_dir, ["branch", "-a", "--format=%(refname:short)"])
    report["branches"] = branches.split("\n") if branches else []

    # 评分
    score = 10.0
    for lf in report["large_files"]:
        if lf["size_mb"] > 50:
            score -= 1.5
        else:
            score -= 0.5
    if report["secrets"]:
        score -= len(report["secrets"]) * 2.0
    if report["commits"]["percentage"] < 50:
        score -= 1.0
    elif report["commits"]["percentage"] < 70:
        score -= 0.5
    if not report["gitignore"]["exists"]:
        score -= 1.5
    elif report["gitignore"]["missing_recommended"]:
        score -= len(report["gitignore"]["missing_recommended"]) * 0.2

    report["score"] = max(0, min(10, round(score, 1)))

    # 问题汇总
    if report["large_files"]:
        total_mb = sum(f["size_mb"] for f in report["large_files"])
        report["issues"].append(
            {
                "severity": "MEDIUM",
                "message": f"{len(report['large_files'])} 个大文件 (总计 {total_mb:.0f}MB) 在 git 历史中",
            }
        )
    if report["secrets"]:
        report["issues"].append(
            {
                "severity": "HIGH",
                "message": f"{len(report['secrets'])} 个疑似凭据文件被 git 跟踪",
            }
        )

    return report


def _print_text(report: dict):
    print("=" * 60)
    print("Git 仓库健康度审核报告")
    print("=" * 60)

    print(f"\n📁 仓库: {report['path']}")
    print(f"   分支: {len(report['branches'])} 个")

    gi = report["gitignore"]
    if gi.get("exists"):
        print(f"\n📄 .gitignore: {gi['lines']} 条规则")
        if gi["missing_recommended"]:
            print("   缺少推荐规则:")
            for m in gi["missing_recommended"]:
                print(f"   ⚠️ {m['pattern']} ({m['description']})")
        else:
            print("   ✅ 推荐规则全覆盖")
    else:
        print("\n   ❌ .gitignore 不存在")

    cm = report["commits"]
    print(f"\n📝 Commit 质量 (最近 {cm.get('total', 0)} 个):")
    print(f"   Conventional commits: {cm.get('conventional', 0)}/{cm.get('total', 0)} ({cm.get('percentage', 0)}%)")
    if cm.get("non_conventional_samples"):
        print("   非规范示例:")
        for s in cm["non_conventional_samples"][:3]:
            print(f"   - {s}")

    if report["large_files"]:
        print(f"\n📦 大文件 (>10MB):")
        for lf in report["large_files"][:10]:
            print(f"   ⚠️ {lf['path']} ({lf['size_mb']}MB)")
    else:
        print("\n   ✅ 无大文件泄漏")

    if report["secrets"]:
        print(f"\n🔐 疑似凭据泄漏:")
        for s in report["secrets"]:
            print(f"   ❌ {s['file']} ({s['type']})")
    else:
        print("\n   ✅ 无凭据泄漏")

    if report["issues"]:
        print(f"\n⚠️ 问题汇总:")
        for issue in report["issues"]:
            print(f"   [{issue['severity']}] {issue['message']}")

    print(f"\n📊 评分: {report['score']}/10")


def main():
    parser = argparse.ArgumentParser(description="Git 仓库健康度审核")
    parser.add_argument("--repo-dir", type=Path, required=True, help="Git 仓库根目录")
    parser.add_argument("--output", choices=["json", "text"], default="text")
    args = parser.parse_args()

    report = audit(args.repo_dir)

    if args.output == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_text(report)


if __name__ == "__main__":
    main()
