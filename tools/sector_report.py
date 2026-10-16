"""生成分赛道的技能图谱 HTML 报告（深色主题，零外部依赖）。

用法：
  python tools/sector_report.py <scored.json> [补充json ...] -o <输出.html>
"""
from __future__ import annotations

import argparse
import html
import json
import pathlib
import re
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from atlas.core import DOMAIN_LABELS, JD, Atlas, load_skills, render_md   # noqa: E402
from atlas.extract import build_learning_path, extract         # noqa: E402

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

SECTORS = [
    ("robotics", "机器人 · 具身智能", "#58a6ff", 80),
    ("ai", "人工智能 · 大模型", "#a371f7", 80),
    ("investment", "投资 · 金融", "#3fb950", 40),
]


def classify(title: str, company: str, text: str, track: str) -> str:
    if track == "investment" or INVEST_TITLES.search(title):
        return "investment"
    head = f"{title} {text[:400]}"
    r = len(ROBOT_SIGNALS.findall(head))
    a = len(AI_SIGNALS.findall(head))
    if r == 0 and a == 0:
        return "robotics" if ROBOT_SIGNALS.search(company + text[:120]) else "ai"
    return "robotics" if r >= a else "ai"


def load_all(paths: list[str]) -> list[dict]:
    jobs: list[dict] = []
    for p in paths:
        f = pathlib.Path(p)
        if not f.exists():
            print(f"  [!] 跳过不存在的文件：{p}", file=sys.stderr)
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            d = d.get("jobs") or d.get("roles") or []
        jobs.extend(d)
    seen, uniq = set(), []
    for j in jobs:
        key = j.get("url") or f"{j.get('company')}|{j.get('title')}"
        if key in seen:
            continue
        seen.add(key)
        uniq.append(j)
    return uniq


def bar(cov: float, color: str, width: float = 100.0) -> str:
    pct = min(cov * 100, 100)
    return (
        f'<div class="bar"><i style="width:{pct * width / 100:.2f}%;background:{color}"></i></div>'
    )


def skill_card(hit, total: int, color: str, rank: int) -> str:
    s = hit.skill
    cov = hit.count / total if total else 0
    learn = "".join(f"<li>{html.escape(x)}</li>" for x in s.learn_path)
    prereq = ""
    if s.prerequisite:
        prereq = (
            '<div class="field"><span class="k">前置</span><span class="v">'
            + "、".join(html.escape(p) for p in s.prerequisite)
            + "</span></div>"
        )
    samples = "".join(
        f'<div class="quote">「{html.escape(x)}」</div>' for x in hit.samples[:3]
    )
    return f"""<details class="skill" {'open' if rank <= 3 else ''}>
<summary><span class="nm">{html.escape(s.display)}</span>
<span class="cov" style="color:{color}">{cov:.1%}</span>
<span class="cnt">{hit.count}/{total} 个岗位提到</span></summary>
<div class="body">
<div class="field"><span class="k">一句话</span><span class="v">{render_md(s.what)}</span></div>
<div class="field"><span class="k">为什么岗位要它</span><span class="v md">{render_md(s.why)}</span></div>
<div class="field"><span class="k">展开说说</span><span class="v md">{render_md(s.how)}</span></div>
{prereq}
{('<div class="field"><span class="k">怎么学</span><span class="v"><ol class="lp">' + learn + '</ol></span></div>') if learn else ''}
{('<div class="field"><span class="k">JD 原话</span><span class="v">' + samples + '</span></div>') if samples else ''}
</div></details>"""


def render_sector(key: str, label: str, color: str, atlas: Atlas, total: int) -> str:
    must = atlas.must_have()
    nice = atlas.nice_to_have()
    rare = atlas.rare()

    def block(title: str, hits, limit=None) -> str:
        if not hits:
            return f'<h4 class="tier">{title}</h4><p class="muted">（无）</p>'
        rows = hits[:limit] if limit else hits
        out = [f'<h4 class="tier">{title} <span class="tn">{len(hits)}</span></h4>']
        out.append('<table class="rank"><tbody>')
        for i, h in enumerate(rows, 1):
            cov = h.count / total if total else 0
            out.append(
                f'<tr><td class="rk">{i}</td>'
                f'<td class="nm">{html.escape(h.skill.display)}'
                f'<span class="dom">{DOMAIN_LABELS.get(h.skill.domain, h.skill.domain)}</span></td>'
                f'<td class="barcell">{bar(cov, color)}</td>'
                f'<td class="pc">{cov:.1%}</td></tr>'
            )
        out.append("</tbody></table>")
        return "".join(out)

    cards = "".join(
        skill_card(h, total, color, i) for i, h in enumerate(must + nice, 1)
    )

    return f"""<section id="{key}">
<h2 style="border-color:{color}">{html.escape(label)}
<span class="sub">{atlas.total_jds} 条 JD · 命中 {len(atlas.hits)} 项能力</span></h2>
{block("🔴 必备 · ≥25% 的岗位要求", must)}
{block("🟡 加分 · 8% – 25%", nice)}
{block("🟢 差异化 · <8%，出现即加分", rare, 15)}
<h3>逐条解释（必备 + 加分）</h3>
<div class="cards">{cards or '<p class="muted">无</p>'}</div>
</section>"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--title", default="机器人 / 具身智能 / AI · 能力图谱")
    args = ap.parse_args()

    jobs = load_all(args.inputs)
    skills = load_skills()

    buckets: dict[str, list[dict]] = {k: [] for k, *_ in SECTORS}
    for j in jobs:
        if len(j.get("jd") or "") < 40:
            continue
        buckets[classify(j["title"], j.get("company") or "", j.get("jd") or "",
                         j.get("track") or "")].append(j)

    atlases: dict[str, Atlas] = {}
    for key, label, color, minc in SECTORS:
        if not buckets[key]:
            continue
        atlases[key] = extract(
            [JD(title=j.get("title") or "", text=j.get("jd") or "",
                company=j.get("company") or "", location=j.get("location") or "",
                url=j.get("url") or "") for j in buckets[key]],
            skills=skills, min_jd_chars=minc,
        )

    whole = extract(
        [JD(title=j.get("title") or "", text=j.get("jd") or "",
            company=j.get("company") or "") for j in jobs if len(j.get("jd") or "") >= 40],
        skills=skills,
    )

    # ---- 跨赛道：共性 vs 专属 ----
    cov = {k: {h.skill.id: h.count / (a.total_jds or 1) for h in a.hits} for k, a in atlases.items()}

    shared = []
    for sid in cov.get("robotics", {}):
        if sid in cov.get("ai", {}):
            r, a = cov["robotics"][sid], cov["ai"][sid]
            if r >= 0.08 and a >= 0.08:
                shared.append((sid, r, a))
    shared.sort(key=lambda x: -(x[1] + x[2]))

    exclusive = {}
    for key in atlases:
        others = [k for k in atlases if k != key]
        exclusive[key] = sorted(
            ((sid, c) for sid, c in cov[key].items()
             if c >= 0.10 and all(c >= cov.get(o, {}).get(sid, 0) * 1.8 for o in others)),
            key=lambda x: -x[1],
        )[:12]

    # ---- 地基知识专章 ----
    found = [h for h in whole.hits if h.skill.domain == "foundations"]
    found.sort(key=lambda h: -h.count)

    # ---- 学习路径 ----
    path_ids = [h.skill.id for h in whole.must_have()] + [h.skill.id for h in whole.nice_to_have()]
    stages = build_learning_path(whole, path_ids)

    # ---- 缺口 ----
    gaps = whole.unknown_terms[:18]

    def name_of(sid: str) -> str:
        s = skills.get(sid)
        return s.display if s else sid

    # ================= 组装 HTML =================
    P = []
    A = P.append
    A('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">')
    A('<meta name="viewport" content="width=device-width,initial-scale=1">')
    A(f"<title>{html.escape(args.title)}</title><style>")
    A("""
:root{--bg:#0d1117;--panel:#161b22;--panel2:#1c2128;--line:#30363d;--fg:#e6edf3;
--muted:#8b949e;--dim:#6e7681;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.7 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;}
.wrap{max-width:1080px;margin:0 auto;padding:44px 24px 90px}
h1{font-size:30px;margin:0 0 8px;letter-spacing:-.4px}
.lede{color:var(--muted);margin:0 0 30px;font-size:14px}
h2{font-size:22px;margin:56px 0 18px;padding-left:14px;border-left:4px solid #58a6ff}
h2 .sub{display:block;font-size:13px;color:var(--muted);font-weight:400;margin-top:5px}
h3{font-size:17px;margin:36px 0 14px;color:#c9d1d9}
h4.tier{font-size:14px;margin:24px 0 10px;color:#c9d1d9;font-weight:600}
h4.tier .tn{color:var(--dim);font-weight:400;font-size:12px;margin-left:6px}
.muted{color:var(--muted);font-size:13px}
.cards{margin-top:8px}
/* 统计块 */
.stats{display:flex;gap:12px;flex-wrap:wrap;margin:0 0 26px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:10px;
padding:16px 20px;flex:1;min-width:150px}
.stat b{display:block;font-size:26px;font-weight:700;letter-spacing:-.5px}
.stat span{font-size:12px;color:var(--muted)}
/* 排名表 */
table.rank{width:100%;border-collapse:collapse;background:var(--panel);
border:1px solid var(--line);border-radius:10px;overflow:hidden}
table.rank td{padding:9px 12px;border-bottom:1px solid #21262d;vertical-align:middle}
table.rank tr:last-child td{border-bottom:none}
td.rk{width:30px;color:var(--dim);font-size:12px;text-align:right}
td.nm{font-size:14px}
td.nm .dom{color:var(--dim);font-size:11px;margin-left:8px;
border:1px solid var(--line);border-radius:4px;padding:1px 6px}
td.barcell{width:180px}
td.pc{width:56px;text-align:right;font-variant-numeric:tabular-nums;
font-size:13px;color:#c9d1d9}
.bar{height:7px;background:#21262d;border-radius:4px;overflow:hidden}
.bar i{display:block;height:100%;border-radius:4px}
/* 技能卡 */
details.skill{background:var(--panel);border:1px solid var(--line);
border-radius:10px;margin:8px 0;overflow:hidden}
details.skill>summary{cursor:pointer;padding:13px 16px;display:flex;
align-items:center;gap:12px;list-style:none;font-size:15px}
details.skill>summary::-webkit-details-marker{display:none}
details.skill>summary::before{content:"▸";color:var(--dim);font-size:12px}
details.skill[open]>summary::before{content:"▾"}
details.skill[open]>summary{border-bottom:1px solid var(--line);background:var(--panel2)}
.summary .nm{font-weight:600}
summary .nm{font-weight:600;flex:1}
summary .cov{font-variant-numeric:tabular-nums;font-weight:600}
summary .cnt{color:var(--dim);font-size:12px}
.body{padding:6px 18px 18px}
.field{display:flex;gap:14px;padding:11px 0;border-bottom:1px dashed #21262d}
.field:last-child{border-bottom:none}
.field .k{flex:0 0 106px;color:#7d8590;font-size:13px;padding-top:2px}
.field .v{flex:1;font-size:14px;color:#d0d7de}
.field .v.md{line-height:1.85}
ol.lp{margin:0;padding-left:20px}
ol.lp li{margin:3px 0}
.quote{color:var(--muted);font-size:13px;font-style:italic;margin:3px 0;
padding-left:10px;border-left:2px solid var(--line)}
/* 双列对比 */
.cols{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:720px){.cols{grid-template-columns:1fr}}
.col{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 18px}
.col h5{margin:0 0 10px;font-size:14px;color:#c9d1d9}
.col ul{margin:0;padding-left:18px;font-size:13px;color:#b8c0c8}
.col li{margin:5px 0}
.tag{display:inline-block;font-size:11px;padding:1px 7px;border-radius:4px;
background:#21262d;color:var(--muted);margin-left:6px}
/* 路径 */
.stage{background:var(--panel);border:1px solid var(--line);border-radius:10px;
padding:14px 18px;margin:10px 0;position:relative}
.stage b{color:#58a6ff;font-size:13px}
.stage .sk{font-size:14px;margin-top:6px}
.note{background:#1c2128;border-left:3px solid #d29922;border-radius:8px;
padding:14px 18px;margin:18px 0;font-size:13.5px;color:#c9d1d9}
footer{margin-top:70px;padding-top:22px;border-top:1px solid var(--line);
color:var(--dim);font-size:12px}
""")
    A("</style></head><body><div class='wrap'>")
    A(f"<h1>{html.escape(args.title)}</h1>")
    A(f'<p class="lede">数据源：求职雷达抓取的 {len(jobs)} 条真实岗位 JD　·　'
      f"技能词典 {len(skills)} 条　·　"
      f"命中 {len(whole.hits)} 项能力　·　生成于 2026-10-16</p>")

    A('<div class="stats">')
    A(f'<div class="stat"><b>{whole.total_jds}</b><span>分析的有效 JD</span></div>')
    A(f'<div class="stat"><b>{len(whole.hits)}</b><span>命中的能力项</span></div>')
    A(f'<div class="stat"><b>{len(whole.must_have())}</b><span>行业必备能力</span></div>')
    A(f'<div class="stat"><b>{len(found)}</b><span>被 JD 提到的地基知识</span></div>')
    A("</div>")

    A('<div class="note"><b>怎么读这份报告。</b>'
      "「必备 / 加分 / 差异化」是按<b>岗位覆盖率</b>分的，不是按难度 ——"
      "覆盖率高的意思是：<b>不学它就过不了简历关</b>。"
      "每一条都能展开看三层：这是什么、为什么岗位要它、具体怎么学。"
      "文末有按依赖关系排好的学习顺序。</div>")

    for key, label, color, _ in SECTORS:
        if key in atlases:
            A(render_sector(key, label, color, atlases[key], atlases[key].total_jds or 1))

    # ---- 共性 vs 专属 ----
    A('<h2 style="border-color:#d29922">跨赛道对比 <span class="sub">'
      "哪些能力是共性的，哪些只属于某个赛道</span></h2>")
    A('<div class="cols">')
    A('<div class="col"><h5>🤝 机器人 × AI 的共性能力（两个赛道都高频）</h5><ul>')
    for sid, r, a in shared[:12]:
        A(f"<li>{html.escape(name_of(sid))} "
          f'<span class="tag">机器人 {r:.0%} · AI {a:.0%}</span></li>')
    A("</ul></div>")
    A('<div class="col"><h5>🎯 只在机器人赛道必备</h5><ul>')
    for sid, c in exclusive.get("robotics", [])[:10]:
        A(f'<li>{html.escape(name_of(sid))} <span class="tag">{c:.0%}</span></li>')
    A("</ul></div><div class='col'><h5>🎯 只在 AI 赛道必备</h5><ul>")
    for sid, c in exclusive.get("ai", [])[:10]:
        A(f'<li>{html.escape(name_of(sid))} <span class="tag">{c:.0%}</span></li>')
    A("</ul></div><div class='col'><h5>💼 只在投资岗必备</h5><ul>")
    for sid, c in exclusive.get("investment", [])[:10]:
        A(f'<li>{html.escape(name_of(sid))} <span class="tag">{c:.0%}</span></li>')
    A("</ul></div></div>")

    # ---- 地基知识 ----
    A('<h2 style="border-color:#f85149">地基知识 <span class="sub">'
      "不写在 JD 显眼处，但面试一定会问 —— 上层工具学再多也绕不过</span></h2>")
    A('<table class="rank"><tbody>')
    for h in found:
        cov_r = h.count / (whole.total_jds or 1)
        A(f'<tr><td class="nm">{html.escape(h.skill.display)}'
          f'<span class="dom">{html.escape(h.skill.level)}</span></td>'
          f'<td class="barcell">{bar(cov_r, "#f85149")}</td>'
          f'<td class="pc">{cov_r:.1%}</td></tr>')
    A("</tbody></table>")
    A('<h3>逐条解释</h3><div class="cards">')
    for i, h in enumerate(found, 1):
        A(skill_card(h, whole.total_jds or 1, "#f85149", i))
    A("</div>")

    # ---- 学习路径 ----
    A('<h2 style="border-color:#3fb950">学习顺序 <span class="sub">'
      "按前置依赖排好的路径 —— 不是按重要性，而是按「先学什么才不会卡住」</span></h2>")
    for st in stages:
        names = "　·　".join(html.escape(x["name"]) for x in st.get("skills", []))
        A(f'<div class="stage"><b>第 {st["stage"]} 阶段</b>'
          f'<div class="sk">{names}</div></div>')

    # ---- 缺口 ----
    A('<h2 style="border-color:#8b949e">词典还需要补的词 <span class="sub">'
      "高频出现但尚未收录，说明本报告的覆盖边界在哪</span></h2>")
    A('<div class="col"><ul>')
    for t, n in gaps:
        A(f'<li>{html.escape(t)} <span class="tag">{n} 次</span></li>')
    A("</ul></div>")

    A("<footer>由 jd-skill-atlas 生成 · 纯词典 + 规则抽取，无 LLM 参与，结果可复现　·　"
      "岗位数据来自 cn-job-radar</footer>")
    A("</div></body></html>")

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(P), encoding="utf-8")
    print(f"✓ 报告已生成：{out}  ({out.stat().st_size // 1024} KB)")
    for key, label, *_ in SECTORS:
        if key in atlases:
            a = atlases[key]
            print(f"   {label:<18} {a.total_jds:4d} 条 JD · 必备 {len(a.must_have())} · 加分 {len(a.nice_to_have())} · 差异化 {len(a.rare())}")
    print(f"   地基知识命中 {len(found)} 项 · 学习路径 {len(stages)} 个阶段")
    return 0


if __name__ == "__main__":
    sys.exit(main())
