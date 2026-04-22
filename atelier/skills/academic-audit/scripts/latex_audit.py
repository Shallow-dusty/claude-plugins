#!/usr/bin/env python3
"""LaTeX 论文格式自动审核工具。

用法:
    python latex_audit.py --thesis-dir <path> [--output json|text]

功能:
    1. 解析 .bib 文件，检查条目完整性
    2. 扫描 .tex 文件中的 \\cite{} 和 \\ref{}
    3. 检查引用-文献配对
    4. 解析编译日志 (main.log)
    5. 检查 label/ref 配对
"""

import argparse
import json
import re
from pathlib import Path


def parse_bib(bib_path: Path) -> dict:
    """解析 .bib 文件，提取条目及其字段。"""
    entries = {}
    if not bib_path.exists():
        return entries

    content = bib_path.read_text(encoding="utf-8", errors="replace")

    # 匹配 @type{key, ... }
    pattern = re.compile(r"@(\w+)\s*\{([^,]+),([^@]*?)(?=\n@|\Z)", re.DOTALL)
    required_fields = {"author", "title", "year"}
    optional_fields = {"journal", "booktitle", "volume", "pages", "doi", "publisher", "url"}

    for match in pattern.finditer(content):
        entry_type = match.group(1).lower()
        key = match.group(2).strip()
        body = match.group(3)

        if entry_type in ("comment", "string", "preamble"):
            continue

        # 提取字段
        fields = {}
        field_pattern = re.compile(r"(\w+)\s*=\s*[{\"](.*?)[}\"]", re.DOTALL)
        for fm in field_pattern.finditer(body):
            fields[fm.group(1).lower()] = fm.group(2).strip()

        present = set(fields.keys())
        missing_required = required_fields - present
        missing_optional = optional_fields - present

        entries[key] = {
            "type": entry_type,
            "fields": list(present),
            "missing_required": list(missing_required),
            "missing_optional": list(missing_optional),
            "completeness": len(present & (required_fields | optional_fields))
            / len(required_fields | optional_fields),
        }

    return entries


def scan_tex_citations(tex_dir: Path) -> dict:
    """扫描所有 .tex 文件，提取 \\cite 和 \\ref 命令。"""
    cite_keys = set()
    ref_keys = set()
    label_keys = set()
    cite_locations = {}  # key -> [file:line, ...]
    ref_locations = {}
    label_locations = {}

    cite_pattern = re.compile(r"\\cite[pt]?\{([^}]+)\}")
    ref_pattern = re.compile(r"\\(?:ref|eqref|autoref|cref)\{([^}]+)\}")
    label_pattern = re.compile(r"\\label\{([^}]+)\}")

    for tex_file in sorted(tex_dir.rglob("*.tex")):
        # 跳过 .archive 目录
        if ".archive" in str(tex_file) or "archive" in tex_file.parts:
            continue

        try:
            lines = tex_file.read_text(encoding="utf-8", errors="replace").split("\n")
        except Exception:
            continue

        rel_path = str(tex_file.relative_to(tex_dir))
        for i, line in enumerate(lines, 1):
            # 跳过注释行
            stripped = line.lstrip()
            if stripped.startswith("%"):
                continue

            for m in cite_pattern.finditer(line):
                for key in m.group(1).split(","):
                    key = key.strip()
                    if key:
                        cite_keys.add(key)
                        cite_locations.setdefault(key, []).append(f"{rel_path}:{i}")

            for m in ref_pattern.finditer(line):
                key = m.group(1).strip()
                ref_keys.add(key)
                ref_locations.setdefault(key, []).append(f"{rel_path}:{i}")

            for m in label_pattern.finditer(line):
                key = m.group(1).strip()
                label_keys.add(key)
                label_locations.setdefault(key, []).append(f"{rel_path}:{i}")

    return {
        "cite_keys": cite_keys,
        "ref_keys": ref_keys,
        "label_keys": label_keys,
        "cite_locations": cite_locations,
        "ref_locations": ref_locations,
        "label_locations": label_locations,
    }


def parse_log(log_path: Path) -> dict:
    """解析 LaTeX 编译日志。"""
    report = {
        "exists": log_path.exists(),
        "errors": [],
        "warnings": [],
        "overfull_hbox": 0,
        "underfull_hbox": 0,
        "overfull_vbox": 0,
        "undefined_refs": [],
        "missing_citations": [],
    }

    if not log_path.exists():
        return report

    try:
        content = log_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return report

    for line in content.split("\n"):
        if line.startswith("!"):
            report["errors"].append(line[:200])
        if "Overfull \\hbox" in line:
            report["overfull_hbox"] += 1
        if "Underfull \\hbox" in line:
            report["underfull_hbox"] += 1
        if "Overfull \\vbox" in line:
            report["overfull_vbox"] += 1
        if "LaTeX Warning: Reference" in line and "undefined" in line:
            m = re.search(r"`([^']+)'", line)
            if m:
                report["undefined_refs"].append(m.group(1))
        if "LaTeX Warning: Citation" in line and "undefined" in line:
            m = re.search(r"`([^']+)'", line)
            if m:
                report["missing_citations"].append(m.group(1))

    return report


def audit(thesis_dir: Path) -> dict:
    """执行完整审核。"""
    report = {"path": str(thesis_dir), "bib": {}, "citations": {}, "log": {}, "issues": []}

    # 1. 查找 .bib 文件
    bib_files = list(thesis_dir.rglob("*.bib"))
    bib_files = [f for f in bib_files if ".archive" not in str(f) and "archive" not in f.parts]
    bib_entries = {}
    for bib_file in bib_files:
        entries = parse_bib(bib_file)
        bib_entries.update(entries)
    report["bib"] = {
        "files": [str(f) for f in bib_files],
        "total_entries": len(bib_entries),
        "entries": {
            k: {
                "type": v["type"],
                "missing_required": v["missing_required"],
                "completeness": round(v["completeness"], 2),
            }
            for k, v in bib_entries.items()
        },
    }

    # 2. 扫描 tex 引用
    tex_scan = scan_tex_citations(thesis_dir)
    cite_keys = tex_scan["cite_keys"]
    bib_keys = set(bib_entries.keys())

    # 引用-文献交叉检查
    dangling_cites = cite_keys - bib_keys  # 正文引用了但 bib 中没有
    orphan_bibs = bib_keys - cite_keys  # bib 中有但正文未引用
    dangling_refs = tex_scan["ref_keys"] - tex_scan["label_keys"]
    unused_labels = tex_scan["label_keys"] - tex_scan["ref_keys"]

    report["citations"] = {
        "total_cite_keys": len(cite_keys),
        "total_bib_entries": len(bib_keys),
        "dangling_cites": sorted(dangling_cites),
        "orphan_bibs": sorted(orphan_bibs),
        "total_labels": len(tex_scan["label_keys"]),
        "total_refs": len(tex_scan["ref_keys"]),
        "dangling_refs": sorted(dangling_refs),
        "unused_labels": len(unused_labels),
    }

    # 3. 编译日志
    log_path = thesis_dir / "main.log"
    report["log"] = parse_log(log_path)

    # 4. 汇总问题
    if dangling_cites:
        report["issues"].append(
            {
                "severity": "HIGH",
                "message": f"{len(dangling_cites)} 个引用无对应 bib 条目: {sorted(dangling_cites)}",
            }
        )
    if dangling_refs:
        report["issues"].append(
            {
                "severity": "HIGH",
                "message": f"{len(dangling_refs)} 个 \\ref 指向不存在的 \\label: {sorted(dangling_refs)}",
            }
        )
    if report["log"]["errors"]:
        report["issues"].append(
            {
                "severity": "HIGH",
                "message": f"{len(report['log']['errors'])} 个编译错误",
            }
        )
    if orphan_bibs:
        report["issues"].append(
            {
                "severity": "LOW",
                "message": f"{len(orphan_bibs)} 个 bib 条目未被引用: {sorted(orphan_bibs)}",
            }
        )
    for key, entry in bib_entries.items():
        if entry["missing_required"]:
            report["issues"].append(
                {
                    "severity": "MEDIUM",
                    "message": f"bib [{key}] 缺少必需字段: {entry['missing_required']}",
                }
            )

    # 评分
    score = 10.0
    for issue in report["issues"]:
        if issue["severity"] == "HIGH":
            score -= 2.0
        elif issue["severity"] == "MEDIUM":
            score -= 0.5
        elif issue["severity"] == "LOW":
            score -= 0.2
    report["score"] = max(0, min(10, round(score, 1)))

    return report


def _print_text(report: dict):
    print("=" * 60)
    print("LaTeX 格式与引用审核报告")
    print("=" * 60)

    bib = report["bib"]
    print(f"\n📚 参考文献: {bib['total_entries']} 条 ({', '.join(bib['files'])})")
    for key, entry in bib["entries"].items():
        status = "✅" if not entry["missing_required"] else "⚠️"
        print(f"   {status} [{key}] ({entry['type']}) 完整度: {entry['completeness']:.0%}")
        if entry["missing_required"]:
            print(f"      缺少: {entry['missing_required']}")

    cit = report["citations"]
    print(f"\n🔗 引用配对:")
    print(f"   \\cite 键: {cit['total_cite_keys']}  |  bib 条目: {cit['total_bib_entries']}")
    if cit["dangling_cites"]:
        print(f"   ❌ 悬空引用 (cite 无 bib): {cit['dangling_cites']}")
    else:
        print("   ✅ 零悬空引用")
    if cit["orphan_bibs"]:
        print(f"   ⚠️ 孤立 bib (未被引用): {cit['orphan_bibs']}")
    else:
        print("   ✅ 零孤立条目")

    print(f"\n🏷️ Label/Ref:")
    print(f"   \\label: {cit['total_labels']}  |  \\ref: {cit['total_refs']}")
    if cit["dangling_refs"]:
        print(f"   ❌ 悬空引用: {cit['dangling_refs']}")
    else:
        print("   ✅ 零悬空引用")
    print(f"   未被引用的 label: {cit['unused_labels']} 个")

    log = report["log"]
    if log["exists"]:
        print(f"\n📋 编译日志:")
        print(f"   错误: {len(log['errors'])}  |  Overfull hbox: {log['overfull_hbox']}  |  Underfull: {log['underfull_hbox']}")
        if log["errors"]:
            for err in log["errors"][:5]:
                print(f"   ❌ {err}")

    if report["issues"]:
        print(f"\n⚠️ 问题汇总 ({len(report['issues'])} 项):")
        for issue in report["issues"]:
            print(f"   [{issue['severity']}] {issue['message']}")

    print(f"\n📊 评分: {report['score']}/10")


def main():
    parser = argparse.ArgumentParser(description="LaTeX 论文格式审核工具")
    parser.add_argument("--thesis-dir", type=Path, required=True, help="论文根目录")
    parser.add_argument("--output", choices=["json", "text"], default="text")
    args = parser.parse_args()

    report = audit(args.thesis_dir)

    if args.output == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_text(report)


if __name__ == "__main__":
    main()
