"""命令行入口。

    atlas analyze <JD文件或目录>   从一批 JD 里提炼技能图谱
    atlas ui                       打开本地学习平台
    atlas skills [--domain ai]     查看技能词典
    atlas explain <技能>           查一个技能（含学习路径）
    atlas path [--jd FILE]         只看学习路径
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import (
    DOMAIN_LABELS,
    HOME,
    ensure_dirs,
    list_skill_files,
    load_jd_dir,
    load_jds,
    load_skills,
)
from .extract import build_learning_path, extract, gap_analysis
from .report import write_report

BANNER = "jd-skill-atlas · JD 技能图谱"


def _load(path_str: str):
    p = Path(path_str).expanduser()
    if not p.exists():
        print(f"找不到：{p}")
        sys.exit(2)
    jds = load_jd_dir(p) if p.is_dir() else load_jds(p)
    if not jds:
        print(f"{p} 里没有解析出任何 JD。支持 cn-job-radar 的 data/scored/*.json 或 JD 数组。")
        sys.exit(2)
    return jds


def cmd_analyze(args) -> int:
    ensure_dirs()
    jds = _load(args.path)
    print(f"{BANNER}\n\n📥 读入 {len(jds)} 条 JD")

    atlas = extract(jds)
    skills = load_skills()
    print(f"🧠 词典 {len(skills)} 个技能 → 命中 {len(atlas.hits)} 个\n")

    must = atlas.must_have()
    nice = atlas.nice_to_have()
    rare = atlas.rare()

    def show(title: str, items, limit: int = 12):
        print(f"  {title}")
        if not items:
            print("    （无）")
        for h in items[:limit]:
            pct = h.count / atlas.total_jds if atlas.total_jds else 0
            bar = "█" * max(1, round(pct * 14))
            print(f"    {pct:5.1%} {bar:<14} {h.skill.name}"
                  + (f"（{h.skill.zh}）" if h.skill.zh else ""))
        print()

    show("🔴 必备（≥25% 的岗位要求）", must)
    show("🟡 加分（8%–25%）", nice)
    show("🟢 差异化（<8%，但出现即加分）", rare, 8)

    if atlas.unknown_terms:
        print("  ❓ 词典未收录的高频词（补进 skills/*.yaml 会更准）")
        for t, c in atlas.unknown_terms[:10]:
            print(f"    {c:4d}  {t}")
        print()

    have = [s.strip() for s in (args.have or "").split(",") if s.strip()]
    paths = write_report(atlas, title=args.title, owner_have=have)
    print("📄 报告已生成：")
    for k, v in paths.items():
        print(f"   {k:<5} → {v}")

    if have:
        g = gap_analysis(atlas, have)
        print(f"\n🎯 你的覆盖率：{g['coverage']:.0%}（必备 {g['required_count']} 项中已掌握 {len(g['owned'])} 项）")
        if g["missing"]:
            print("   待补：")
            for m in g["missing"][:10]:
                print(f"     · {m['name']}（{m['coverage']:.0%} 的岗位要求）")

    print(f"\n下一步：atlas ui 打开学习平台  →  {HOME}\n")
    return 0


def cmd_ui(args) -> int:
    from .ui.server import serve
    ensure_dirs()
    serve(port=args.port, open_browser=not args.no_open)
    return 0


def cmd_skills(args) -> int:
    skills = load_skills(domain=args.domain)
    if not skills:
        print("没找到技能。用 `atlas skills` 看全部。")
        return 0
    by_domain: dict[str, list] = {}
    for s in skills.values():
        by_domain.setdefault(s.domain, []).append(s)

    print(f"\n{BANNER} · 技能词典（{len(skills)} 个）\n")
    for d, items in sorted(by_domain.items()):
        print(f"  {DOMAIN_LABELS.get(d, d)}（{len(items)}）")
        for s in sorted(items, key=lambda x: x.name):
            print(f"    {s.name:<22} {s.level:<4} {s.zh}")
        print()

    print("词典文件：")
    for f in list_skill_files():
        tag = "（用户自定义，覆盖内置）" if f["source"] == "user" else ""
        print(f"  {f['domain']:<14} {f['count']:3d} 条  {f['label']}{tag}")
    print(f"\n自定义：把同名 yaml 放到 {HOME / 'skills'}/ 即可覆盖内置版本。\n")
    return 0


def cmd_explain(args) -> int:
    """查一个技能 —— 支持按 id、中文名、英文名、别名模糊匹配。"""
    skills = load_skills()
    q = args.skill.strip().lower()
    hits = [s for s in skills.values()
            if q in {s.id.lower(), s.name.lower(), s.zh.lower(), s.full_name.lower()}
            or any(q == a.lower() for a in s.aliases)
            or q in s.name.lower() or q in s.zh.lower()]
    if not hits:
        print(f"词典里没有「{args.skill}」。\n试试 `atlas skills` 看看有哪些。")
        return 2

    for s in hits[:3]:
        print(f"\n{'═' * 66}")
        print(f"  {s.name}" + (f"（{s.zh}）" if s.zh else ""))
        print(f"{'═' * 66}")
        print(f"  领域：{DOMAIN_LABELS.get(s.domain, s.domain)}   熟练度：{s.level}")
        if s.full_name and s.full_name != s.name:
            print(f"  全称：{s.full_name}")
        if s.aliases:
            print(f"  别名：{'、'.join(s.aliases)}")
        if s.what:
            print(f"\n  【一句话】\n  {s.what}")
        if s.why:
            print(f"\n  【为什么这个岗位要它】")
            for line in s.why.strip().splitlines():
                print(f"  {line}")
        if s.how:
            print(f"\n  【展开说说】")
            for line in s.how.strip().splitlines():
                print(f"  {line}")
        if s.prerequisite:
            print(f"\n  【前置技能】{'、'.join(s.prerequisite)}")
        if s.learn_path:
            print(f"\n  【怎么学】")
            for i, step in enumerate(s.learn_path, 1):
                print(f"   {i}. {step}")
        if s.jd_phrases:
            print(f"\n  【JD 里常见的说法】{'、'.join(s.jd_phrases)}")
        print()
    return 0


def cmd_path(args) -> int:
    """输出学习路径：按前置依赖排序。"""
    if args.jd:
        jds = _load(args.jd)
        atlas = extract(jds)
    else:
        print("需要 --jd 指定 JD 来源（或用 `atlas analyze` 先跑一遍）")
        return 2

    must = atlas.must_have()
    nice = atlas.nice_to_have()
    ids = [h.skill.id for h in must + nice[:10]]
    stages = build_learning_path(atlas, ids)

    print(f"\n{BANNER} · 学习路径\n")
    print(f"（基于 {atlas.total_jds} 条 JD，按前置依赖排序）\n")
    if not stages:
        print("  没有可排序的技能。")
        return 0
    for st in stages:
        print(f"  ── 阶段 {st['stage']} " + "─" * 40)
        for s in st["skills"]:
            print(f"    · {s['name']}" + (f"（{s['zh']}）" if s.get("zh") else "")
                  + f"   {s['coverage']:.0%}")
        print()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="atlas",
        description=f"{BANNER} —— 从一批 JD 里提炼出「这个行业要什么能力」，并把每个术语讲清楚",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="从一批 JD 提炼技能图谱")
    a.add_argument("path", help="JD 文件或目录（支持 cn-job-radar 的 data/scored/*.json）")
    a.add_argument("--title", default="技能图谱", help="报告标题")
    a.add_argument("--have", help="你已掌握的技能，逗号分隔（用于算覆盖率）")
    a.set_defaults(func=cmd_analyze)

    a = sub.add_parser("ui", help="打开本地学习平台")
    a.add_argument("--port", type=int, default=8899)
    a.add_argument("--no-open", action="store_true")
    a.set_defaults(func=cmd_ui)

    a = sub.add_parser("skills", help="查看技能词典")
    a.add_argument("--domain", help="只看某个领域（ai / robotics / investment / tools / common）")
    a.set_defaults(func=cmd_skills)

    a = sub.add_parser("explain", help="查一个技能的含义与学习路径")
    a.add_argument("skill", help="技能名（中英均可，支持模糊匹配）")
    a.set_defaults(func=cmd_explain)

    a = sub.add_parser("path", help="输出按前置依赖排序的学习路径")
    a.add_argument("--jd", help="JD 文件或目录")
    a.set_defaults(func=cmd_path)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n已中断。")
        return 130


if __name__ == "__main__":
    sys.exit(main())
