"""按赛道拆分分析：机器人/具身智能、AI/大模型、投资岗。

用法：
  python tools/analyze_sectors.py <scored.json>
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from atlas.core import JD, load_skills          # noqa: E402
from atlas.extract import extract               # noqa: E402
from atlas.core import Atlas                    # noqa: E402

# ---------------------------------------------------------------------------
#  赛道判定
# ---------------------------------------------------------------------------
ROBOT_SIGNALS = re.compile(
    r"机器人|具身|人形|灵巧手|关节|运控|运动控制|轨迹规划|抓取|机械臂|"
    r"抓握|步态|双足|四足|SLAM|点云|标定|仿真|ROS|遥操作|触觉|力控|VLA"
)
AI_SIGNALS = re.compile(
    r"大模型|LLM|AIGC|多模态|生成式|Agent|智能体|Transformer|推理优化|"
    r"训练框架|微调|RLHF|RAG|提示工程|向量|embedding|Diffusion|扩散|"
    r"文生图|文生视频|对话系统|语料|预训练|MoE|蒸馏|量化"
)
INVEST_TITLES = re.compile(
    r"投资经理|投资总监|投资VP|投资副总裁|高级投资经理|投资分析师|投资助理|"
    r"投研|行业研究|战投|战略投资|CVC|投资岗|投资者关系|IR|基金经理"
)


def classify(title: str, company: str, text: str, track: str) -> str:
    """给每条 JD 打一个赛道标签。"""
    if track == "investment" or INVEST_TITLES.search(title):
        return "investment"
    head = f"{title} {text[:400]}"
    r = len(ROBOT_SIGNALS.findall(head))
    a = len(AI_SIGNALS.findall(head))
    if r == 0 and a == 0:
        # 回退：看公司
        return "robotics" if ROBOT_SIGNALS.search(company + text[:120]) else "ai"
    if r >= a:
        return "robotics"
    return "ai"


def load_jobs(path: pathlib.Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["jobs"]


def show_tier(atlas: Atlas, label: str, hits, total: int, limit: int | None = None) -> None:
    print(f"\n{label}")
    if not hits:
        print("   （无）")
        return
    rows = hits[:limit] if limit else hits
    for h in rows:
        cov = h.count / total if total else 0
        bar = "█" * max(1, int(cov * 40))
        print(f"   {cov:6.1%} {bar:<42} {h.skill.display}")


def run_sector(name: str, jobs: list[dict], skills, min_chars: int = 80) -> Atlas:
    jds = [
        JD(
            title=j.get("title") or "",
            text=j.get("jd") or "",
            company=j.get("company") or "",
            location=j.get("location") or "",
            url=j.get("url") or "",
        )
        for j in jobs
    ]
    atlas = extract(jds, skills=skills, min_jd_chars=min_chars)
    print("\n" + "=" * 78)
    print(f"  {name}   共 {atlas.total_jds} 条 JD")
    print("=" * 78)
    total = atlas.total_jds or 1
    show_tier(atlas, "🔴 必备（≥25% 的岗位都要求）", atlas.must_have(), total)
    show_tier(atlas, "🟡 加分（8% – 25%）", atlas.nice_to_have(), total)
    show_tier(atlas, "🟢 差异化（<8%，出现即加分）", atlas.rare(), total, 14)
    return atlas


def load_extra(paths: list[str]) -> list[dict]:
    """额外输入：雷达 data/raw/*.json（投资岗等）。"""
    out: list[dict] = []
    for p in paths:
        f = pathlib.Path(p)
        if not f.exists():
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            d = d.get("roles") or d.get("jobs") or []
        for r in d:
            r.setdefault("track", "investment")
            out.append(r)
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = pathlib.Path(sys.argv[1])
    jobs = load_jobs(path) + load_extra(sys.argv[2:])
    skills = load_skills()

    buckets: dict[str, list[dict]] = {"robotics": [], "ai": [], "investment": []}
    for j in jobs:
        if len(j.get("jd") or "") < 40:
            continue
        buckets[classify(j["title"], j.get("company") or "", j.get("jd") or "", j.get("track") or "")].append(j)

    print(f"输入：{path.name} + {len(sys.argv) - 2} 个补充文件  有效 JD {sum(len(v) for v in buckets.values())} 条")
    for k, v in buckets.items():
        print(f"  {k:<12} {len(v):4d} 条")

    atlases = {}
    for key, title, minc in (("robotics", "赛道 A · 机器人 / 具身智能", 80),
                             ("ai", "赛道 B · AI / 大模型", 80),
                             ("investment", "赛道 C · 投资 / 金融", 40)):
        if buckets[key]:
            atlases[key] = run_sector(title, buckets[key], skills, minc)

    # ---- 跨赛道对比：哪些技能只在某个赛道必备 ----
    print("\n" + "=" * 78)
    print("  跨赛道对比 —— 各赛道的专属高覆盖技能")
    print("=" * 78)
    cov: dict[str, dict[str, float]] = {}
    for key, at in atlases.items():
        t = at.total_jds or 1
        cov[key] = {h.skill.id: h.count / t for h in at.hits}

    for key in atlases:
        others = [k for k in atlases if k != key]
        mine = cov[key]
        exclusive = sorted(
            ((sid, c) for sid, c in mine.items()
             if c >= 0.10 and all(mine.get(sid, 0) >= cov.get(o, {}).get(sid, 0) * 1.8 for o in others)),
            key=lambda x: -x[1],
        )
        print(f"\n  【{key}】专属（覆盖率为其他赛道的 1.8 倍以上）:")
        for sid, c in exclusive[:12]:
            s = skills.get(sid)
            if s:
                print(f"    {c:6.1%}  {s.display}")

    # ---- 词典缺口 ----
    print("\n" + "=" * 78)
    print("  词典缺口 —— 高频但词典尚未收录的技术词（按出现 JD 数排序）")
    print("=" * 78)
    merged: Counter = Counter()
    for at in atlases.values():
        for term, n in at.unknown_terms[:120]:
            merged[term] += n
    for term, n in merged.most_common(30):
        print(f"   {n:4d}  {term}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
