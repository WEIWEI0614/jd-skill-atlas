"""报告生成：把技能图谱落成可读的 Markdown + 机器可读的 JSON。"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from .core import Atlas, REPORT_DIR, DOMAIN_LABELS, LEVEL_ORDER, SkillHit

LEVEL_EMOJI = {"入门": "🟢", "进阶": "🟡", "高级": "🔴", "专家": "⚫"}


def _coverage_bar(h: SkillHit, total: int, width: int = 20) -> str:
    if not total:
        return ""
    n = max(1, round(h.count / total * width))
    return "█" * n + "░" * (width - n)


def _skill_section(h: SkillHit, total: int) -> list[str]:
    s = h.skill
    pct = h.count / total if total else 0
    L = [
        f"#### {s.name}" + (f"（{s.zh}）" if s.zh else "") + f"  `{pct:.0%}`",
        "",
        f"`{_coverage_bar(h, total)}` {h.count}/{total} 个岗位提到"
        f" · {LEVEL_EMOJI.get(s.level, '')} {s.level} · {DOMAIN_LABELS.get(s.domain, s.domain)}",
        "",
    ]
    if s.what:
        L += [f"**一句话**：{s.what}", ""]
    if s.why:
        L += ["**为什么这个岗位要它**", "", s.why.rstrip(), ""]
    if s.how:
        L += ["**展开说说**", "", s.how.rstrip(), ""]
    if s.prerequisite:
        L += [f"**前置**：{'、'.join(s.prerequisite)}", ""]
    if s.learn_path:
        L += ["**怎么学**", ""]
        L += [f"{i}. {step}" for i, step in enumerate(s.learn_path, 1)]
        L.append("")
    if h.samples:
        L += ["**JD 里是这么说的**", ""]
        L += [f"> {x}" for x in h.samples[:2]]
        L.append("")
    if h.jobs:
        L += [f"_出现在：{'、'.join(h.jobs[:6])}_", ""]
    L.append("---")
    L.append("")
    return L


def build_markdown(atlas: Atlas, title: str = "技能图谱", owner_have: list[str] | None = None) -> str:
    today = date.today().isoformat()
    total = atlas.total_jds
    L = [
        f"# {title}",
        "",
        f"> 从 **{total}** 条岗位 JD 里提炼。生成于 {today}。",
        f"> 词典收录 {atlas.meta.get('skills_in_dict', 0)} 个技能，本次命中 {len(atlas.hits)} 个。",
        "",
        "## 目录",
        "",
        "- [一、能力分级总览](#一能力分级总览)",
        "- [二、必备能力](#二必备能力)",
        "- [三、加分能力](#三加分能力)",
        "- [四、差异化能力](#四差异化能力)",
        "- [五、学习路径](#五学习路径)",
        "",
    ]

    must = atlas.must_have()
    nice = atlas.nice_to_have()
    rare = atlas.rare()

    # ---- 总览 ----
    L += ["## 一、能力分级总览", "", "| 分级 | 含义 | 数量 | 代表技能 |", "|---|---|---|---|"]
    L.append(f"| 🔴 必备 | ≥35% 的岗位要求 | {len(must)} | "
             f"{'、'.join(h.skill.name for h in must[:5])} |")
    L.append(f"| 🟡 加分 | 10%–35% | {len(nice)} | "
             f"{'、'.join(h.skill.name for h in nice[:5])} |")
    L.append(f"| 🟢 差异化 | <10%，但出现即加分 | {len(rare)} | "
             f"{'、'.join(h.skill.name for h in rare[:5])} |")
    L.append("")

    if atlas.by_domain:
        L += ["**按领域分布**", "", "| 领域 | 提及次数 |", "|---|---|"]
        for d, n in atlas.by_domain.items():
            L.append(f"| {DOMAIN_LABELS.get(d, d)} | {n} |")
        L.append("")

    # ---- 各分级明细 ----
    for header, items in (("二、必备能力", must), ("三、加分能力", nice), ("四、差异化能力", rare)):
        L += [f"## {header}", ""]
        if not items:
            L += ["_本批 JD 中没有命中。_", ""]
            continue
        for h in items:
            L += _skill_section(h, total)

    # ---- 学习路径 ----
    L += ["## 五、学习路径", "", "按前置依赖排序 —— 上面的先学完，下面的才学得动。", ""]
    from .extract import build_learning_path
    path = build_learning_path(atlas, [h.skill.id for h in must + nice[:10]])
    if path:
        for stage in path:
            names = "、".join(s["name"] for s in stage["skills"])
            L += [f"**阶段 {stage['stage']}**：{names}", ""]
    else:
        L += ["_（技能的前置依赖关系中未形成多阶段路径）_", ""]

    # ---- 待补充 ----
    if atlas.unknown_terms:
        L += [
            "## 六、词典待补充的高频词",
            "",
            "这些词在本批 JD 里频繁出现，但技能词典还没收录 —— "
            "**把它们补进 `atlas/data/skills/*.yaml`，下次分析就更准**。",
            "",
            "| 词 | 出现次数 |",
            "|---|---|",
        ]
        for t, c in atlas.unknown_terms[:40]:
            L.append(f"| `{t}` | {c} |")
        L.append("")

    if owner_have:
        L += ["## 附：你的技能对照", "", f"已标注掌握：{'、'.join(owner_have)}", ""]

    return "\n".join(L)


def write_report(atlas: Atlas, out_dir: Path | None = None,
                 title: str = "技能图谱", owner_have: list[str] | None = None) -> dict[str, Path]:
    out_dir = out_dir or REPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    md_path = out_dir / f"{today}.md"
    json_path = out_dir / f"{today}.json"

    md_path.write_text(build_markdown(atlas, title, owner_have), encoding="utf-8")

    payload = atlas.to_dict()
    payload["title"] = title
    payload["generated_at"] = datetime.now().isoformat(timespec="seconds")
    payload["owner_have"] = owner_have or []
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    return {"md": md_path, "json": json_path}
