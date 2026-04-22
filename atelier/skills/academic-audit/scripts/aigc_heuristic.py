#!/usr/bin/env python3
"""AIGC 写作特征启发式标注工具。

⚠️ 重要声明：这不是 AIGC 检测器，不输出"AIGC 率"。
这是一个"可疑段落标注器"——基于已知 AI 写作模式标注高风险段落，
供人工复查和优先改写。真正的 AIGC 检测需要 GPTZero/知网等专业工具。

用法:
    python aigc_heuristic.py --input <file.tex|dir> [--lang zh|en] [--output json|text]

功能:
    1. 统计 AI 高频句式出现次数和密度
    2. 测量段落结构对称性
    3. 计算词汇多样性 (Type-Token Ratio)
    4. 测量过渡词密度
    5. 逐段落标注风险等级 (HIGH/MEDIUM/LOW)
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

# ===== AI 高频句式模式库 =====

ZH_AI_PATTERNS = [
    # 开头模式
    (r"随着.{2,20}的(?:不断|快速|持续)?(?:发展|推进|普及|进步)", "AI典型开头：'随着...的发展'"),
    (r"近年来[，,].{5,30}(?:越来越|日益|逐渐)", "AI典型开头：'近年来...越来越'"),
    (r"在.{2,15}(?:背景|领域|方面)(?:下|中)[，,]", "AI典型开头：'在...背景下'"),
    # 过渡模式
    (r"(?:此外|此外)[，,]", "过渡词：此外"),
    (r"(?:同时|与此同时)[，,]", "过渡词：同时"),
    (r"(?:另外|除此之外)[，,]", "过渡词：另外"),
    (r"值得注意的是[，,]", "AI典型句式：值得注意的是"),
    (r"(?:综上所述|总的来说|总而言之)[，,]", "AI典型总结：综上所述"),
    (r"(?:具体而言|具体来说)[，,]", "AI典型展开：具体而言"),
    (r"(?:不仅如此|不仅.{2,10}而且)", "AI典型递进：不仅...而且"),
    # 评价模式
    (r"(?:有效|显著|极大)地(?:提高|改善|提升|增强|优化)了", "AI典型评价：有效地提高了"),
    (r"(?:在一定程度上|从某种意义上说)", "AI模糊限定"),
    (r"(?:为.{2,15}提供了.{2,10}(?:思路|方案|基础|参考|借鉴))", "AI典型贡献句式"),
    (r"(?:研究表明|实验(?:结果)?表明|(?:由此)?可见)", "AI典型引出结论"),
    # 展望模式
    (r"未来[，,]?(?:可以|将|有望|需要)(?:进一步)?", "AI典型展望"),
    (r"(?:仍然|还)存在(?:一些|诸多|不少)(?:不足|局限|问题|挑战)", "AI典型局限性描述"),
]

EN_AI_PATTERNS = [
    (r"(?i)it is worth (?:noting|mentioning) that", "AI phrase: it is worth noting"),
    (r"(?i)in recent years[,.]", "AI phrase: in recent years"),
    (r"(?i)(?:moreover|furthermore|additionally)[,.]", "AI transition: moreover/furthermore"),
    (r"(?i)(?:in conclusion|to summarize|in summary)[,.]", "AI summary phrase"),
    (r"(?i)plays (?:a |an )?(?:crucial|vital|important|significant) role", "AI phrase: plays a crucial role"),
    (r"(?i)it (?:should be|is) (?:noted|emphasized) that", "AI phrase: it should be noted"),
    (r"(?i)has (?:gained|attracted|received) (?:significant |considerable )?(?:attention|interest)", "AI phrase: has gained attention"),
    (r"(?i)(?:effectively|significantly|greatly) (?:improve|enhance|boost)", "AI evaluation: effectively improve"),
]


def strip_latex(text: str) -> str:
    """移除 LaTeX 命令，保留纯文本。"""
    # 移除注释
    text = re.sub(r"(?<!\\)%.*$", "", text, flags=re.MULTILINE)
    # 移除常见命令
    text = re.sub(r"\\(?:cite|ref|eqref|label|autoref)\{[^}]*\}", "", text)
    text = re.sub(r"\\(?:textbf|textit|emph|underline)\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\(?:section|subsection|subsubsection|chapter|paragraph)\*?\{([^}]*)\}", r"\1", text)
    # 移除数学环境
    text = re.sub(r"\$[^$]+\$", " MATH ", text)
    text = re.sub(r"\\begin\{(?:equation|align|gather|math)\*?\}.*?\\end\{(?:equation|align|gather|math)\*?\}", " MATH ", text, flags=re.DOTALL)
    # 移除图表环境
    text = re.sub(r"\\begin\{(?:figure|table)\*?\}.*?\\end\{(?:figure|table)\*?\}", "", text, flags=re.DOTALL)
    # 移除其他命令
    text = re.sub(r"\\[a-zA-Z]+(?:\[[^\]]*\])?\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+", " ", text)
    text = re.sub(r"[{}]", "", text)
    return text


def split_paragraphs(text: str) -> list[str]:
    """将文本分割为段落（以空行分隔）。"""
    paragraphs = re.split(r"\n\s*\n", text)
    # 过滤掉太短的段落（可能是标题或命令残留）
    return [p.strip() for p in paragraphs if len(p.strip()) > 30]


def analyze_paragraph(para: str, patterns: list[tuple], lang: str) -> dict:
    """分析单个段落的 AI 写作特征。"""
    findings = []
    risk_score = 0

    # 1. 模式匹配
    for pattern, description in patterns:
        matches = re.findall(pattern, para)
        if matches:
            findings.append({"type": "pattern", "description": description, "count": len(matches)})
            risk_score += len(matches) * 2

    # 2. 段落结构分析
    sentences = re.split(r"[。.！!？?；;]", para)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
    if len(sentences) >= 3:
        # 检查句子长度的均匀性（AI 倾向于产生长度均匀的句子）
        lengths = [len(s) for s in sentences]
        if lengths:
            avg_len = sum(lengths) / len(lengths)
            variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
            cv = (variance ** 0.5) / avg_len if avg_len > 0 else 0
            if cv < 0.25:  # 变异系数很低 = 句子长度很均匀
                findings.append({"type": "structure", "description": "句子长度高度均匀 (AI特征)", "cv": round(cv, 3)})
                risk_score += 3

    # 3. 词汇多样性 (TTR)
    if lang == "zh":
        chars = re.findall(r"[\u4e00-\u9fff]", para)
        if len(chars) > 50:
            ttr = len(set(chars)) / len(chars)
            if ttr < 0.45:  # 中文 TTR 低于 0.45 可能是模式化文本
                findings.append({"type": "diversity", "description": f"词汇多样性偏低 (TTR={ttr:.3f})", "ttr": round(ttr, 3)})
                risk_score += 2
    else:
        words = re.findall(r"\b[a-zA-Z]+\b", para.lower())
        if len(words) > 30:
            ttr = len(set(words)) / len(words)
            if ttr < 0.40:
                findings.append({"type": "diversity", "description": f"Lexical diversity low (TTR={ttr:.3f})", "ttr": round(ttr, 3)})
                risk_score += 2

    # 风险等级
    if risk_score >= 6:
        risk = "HIGH"
    elif risk_score >= 3:
        risk = "MEDIUM"
    else:
        risk = "LOW"

    return {
        "text_preview": para[:120] + ("..." if len(para) > 120 else ""),
        "char_count": len(para),
        "risk": risk,
        "risk_score": risk_score,
        "findings": findings,
    }


def analyze_file(file_path: Path, lang: str) -> dict:
    """分析单个文件。"""
    content = file_path.read_text(encoding="utf-8", errors="replace")
    clean_text = strip_latex(content)
    paragraphs = split_paragraphs(clean_text)
    patterns = ZH_AI_PATTERNS if lang == "zh" else EN_AI_PATTERNS

    para_results = []
    for para in paragraphs:
        result = analyze_paragraph(para, patterns, lang)
        if result["findings"]:  # 只保留有发现的段落
            para_results.append(result)

    # 文件级统计
    total_paras = len(paragraphs)
    high_risk = sum(1 for r in para_results if r["risk"] == "HIGH")
    medium_risk = sum(1 for r in para_results if r["risk"] == "MEDIUM")

    # 全文模式统计
    all_pattern_counts = Counter()
    for r in para_results:
        for f in r["findings"]:
            if f["type"] == "pattern":
                all_pattern_counts[f["description"]] += f["count"]

    return {
        "file": str(file_path.name),
        "total_paragraphs": total_paras,
        "flagged_paragraphs": len(para_results),
        "high_risk": high_risk,
        "medium_risk": medium_risk,
        "pattern_summary": dict(all_pattern_counts.most_common(20)),
        "paragraphs": para_results,
    }


def audit(input_path: Path, lang: str) -> dict:
    """执行完整 AIGC 启发式分析。"""
    files_to_check = []
    if input_path.is_file():
        files_to_check = [input_path]
    elif input_path.is_dir():
        for tex in sorted(input_path.rglob("*.tex")):
            if ".archive" not in str(tex) and "archive" not in tex.parts:
                files_to_check.append(tex)

    report = {
        "disclaimer": "⚠️ 这是启发式模式匹配，不是 AIGC 检测。仅标注可疑段落供人工复查。",
        "language": lang,
        "files": [],
        "summary": {},
    }

    total_paras = 0
    total_flagged = 0
    total_high = 0
    total_medium = 0
    global_patterns = Counter()

    for fpath in files_to_check:
        file_result = analyze_file(fpath, lang)
        report["files"].append(file_result)
        total_paras += file_result["total_paragraphs"]
        total_flagged += file_result["flagged_paragraphs"]
        total_high += file_result["high_risk"]
        total_medium += file_result["medium_risk"]
        for pat, cnt in file_result["pattern_summary"].items():
            global_patterns[pat] += cnt

    report["summary"] = {
        "total_files": len(files_to_check),
        "total_paragraphs": total_paras,
        "flagged_paragraphs": total_flagged,
        "high_risk_paragraphs": total_high,
        "medium_risk_paragraphs": total_medium,
        "flagged_ratio": round(total_flagged / total_paras, 3) if total_paras else 0,
        "top_patterns": dict(global_patterns.most_common(10)),
    }

    # 评分（反转：高风险越多分越低）
    if total_paras > 0:
        risk_ratio = (total_high * 2 + total_medium) / total_paras
        score = max(0, min(10, round(10 - risk_ratio * 15, 1)))
    else:
        score = 10
    report["score"] = score

    return report


def _print_text(report: dict):
    print("=" * 60)
    print("AIGC 写作特征启发式分析报告")
    print(f"⚠️ {report['disclaimer']}")
    print("=" * 60)

    s = report["summary"]
    print(f"\n📊 总览: {s['total_files']} 个文件, {s['total_paragraphs']} 个段落")
    print(f"   标注段落: {s['flagged_paragraphs']} ({s['flagged_ratio']:.1%})")
    print(f"   🔴 高风险: {s['high_risk_paragraphs']}  🟡 中风险: {s['medium_risk_paragraphs']}")

    if s["top_patterns"]:
        print("\n📋 高频 AI 模式 (Top 10):")
        for pat, cnt in s["top_patterns"].items():
            print(f"   {cnt:>3}x  {pat}")

    for file_result in report["files"]:
        if not file_result["paragraphs"]:
            continue
        print(f"\n{'─'*60}")
        print(f"📄 {file_result['file']} ({file_result['total_paragraphs']} 段, "
              f"🔴{file_result['high_risk']} 🟡{file_result['medium_risk']})")

        for para in file_result["paragraphs"]:
            icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}[para["risk"]]
            print(f"\n   {icon} [{para['risk']}] {para['text_preview']}")
            for f in para["findings"]:
                if f["type"] == "pattern":
                    print(f"      → {f['description']} (x{f['count']})")
                elif f["type"] == "structure":
                    print(f"      → {f['description']}")
                elif f["type"] == "diversity":
                    print(f"      → {f['description']}")

    print(f"\n📊 启发式评分: {report['score']}/10 (越高越不像 AI)")


def main():
    parser = argparse.ArgumentParser(
        description="AIGC 写作特征启发式标注（非检测器）"
    )
    parser.add_argument("--input", type=Path, required=True, help=".tex 文件或目录")
    parser.add_argument("--lang", choices=["zh", "en"], default="zh", help="语言")
    parser.add_argument("--output", choices=["json", "text"], default="text")
    args = parser.parse_args()

    report = audit(args.input, args.lang)

    if args.output == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_text(report)


if __name__ == "__main__":
    main()
