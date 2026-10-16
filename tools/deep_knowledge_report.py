"""生成「隐形知识」报告 —— 针对 JD 里看不见、但面试与实战一定卡人的知识点。

用法：
  python tools/deep_knowledge_report.py <jd.json> [...] -o <输出.html>
"""
from __future__ import annotations

import argparse
import html
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from atlas.core import DOMAIN_LABELS, JD, Skill, load_skills   # noqa: E402
from atlas.extract import build_learning_path, extract          # noqa: E402

# 三个分组：这一批就是「隐形知识」的全部范围
GROUPS = [
    ("robotics-advanced", "机器人进阶 · 控制与工程深水区", "#58a6ff",
     "几乎不会写在 JD 的任职要求里，但一问就能分出「看过论文」和「真做过」"),
    ("ai-infra-deep", "AI Infra 深水区 · 推理与训练", "#a371f7",
     "JD 里通常只写「熟悉推理优化」一行字 —— 这层是「懂模型」和「懂生产部署」的分界线"),
    ("ecosystem", "生态与流程 · 行业默认术语", "#3fb950",
     "不是知识点而是生态位：因为行业默认你会，所以没人教你，而面试官默认你知道"),
]

# 可见度分档
BANDS = [
    (0.0, 0.0, "🕳 完全隐形", "在全部 JD 里一次都没出现 —— 只能靠主动学，没有任何岗位会提醒你", "#f85149"),
    (0.0, 0.02, "🌑 极低可见", "不到 2% 的岗位提到。通常是资深岗才会写出来", "#d29922"),
    (0.02, 0.05, "🌘 少量可见", "2%–5%。写出来的岗位基本是这个方向的核心岗", "#a371f7"),
    (0.05, 1.01, "🌗 相对常见", "5% 以上。说明已经是该赛道的事实要求", "#3fb950"),
]


def band_of(cov: float):
    for lo, hi, name, desc, color in BANDS:
        if lo <= cov <= hi:
            return name, desc, color
    return BANDS[-1][2], BANDS[-1][3], BANDS[-1][4]


def card(s: Skill, count: int, total: int, color: str, open_it: bool) -> str:
    cov = count / total if total else 0
    learn = "".join(f"<li>{html.escape(x)}</li>" for x in s.learn_path)
    prereq = ""
    if s.prerequisite:
        prereq = ('<div class="field"><span class="k">前置</span><span class="v">'
                  + "、".join(html.escape(p) for p in s.prerequisite) + "</span></div>")
    return f"""<details class="skill"{' open' if open_it else ''}>
<summary><span class="nm">{html.escape(s.display)}</span>
<span class="lvl">{html.escape(s.level)}</span>
<span class="cov" style="color:{color}">{'未出现' if count == 0 else f'{cov:.1%}'}</span>
<span class="cnt">{count}/{total} 个岗位</span></summary>
<div class="body">
<div class="field"><span class="k">一句话</span><span class="v">{html.escape(s.what)}</span></div>
<div class="field"><span class="k">为什么岗位要它</span><span class="v md">{html.escape(s.why).replace(chr(10), '<br>')}</span></div>
<div class="field"><span class="k">展开说说</span><span class="v md">{html.escape(s.how).replace(chr(10), '<br>')}</span></div>
{prereq}
{('<div class="field"><span class="k">怎么学</span><span class="v"><ol class="lp">' + learn + '</ol></span></div>') if learn else ''}
</div></details>"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()

    jobs: list[dict] = []
    for p in args.inputs:
        f = pathlib.Path(p)
        if not f.exists():
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            d = d.get("jobs") or d.get("roles") or []
        jobs.extend(d)
    seen, uniq = set(), []
    for j in jobs:
        k = j.get("url") or f"{j.get('company')}|{j.get('title')}"
        if k in seen:
            continue
        seen.add(k)
        uniq.append(j)

    skills = load_skills()
    jds = [JD(title=j.get("title") or "", text=j.get("jd") or "",
              company=j.get("company") or "")
           for j in uniq if len(j.get("jd") or "") >= 40]
    atlas = extract(jds, skills=skills)
    total = atlas.total_jds or 1
    cov = {h.skill.id: h.count for h in atlas.hits}

    groups = {}
    for gid, title, color, blurb in GROUPS:
        ids = [s.id for s in skills.values() if s.tags and gid.replace("-advanced", "") in " ".join(s.tags)] or []
        # 用「文件来源」不稳，改为按标签域筛选：直接从 skills 里挑属于这一组的
        groups[gid] = (title, color, blurb, ids)

    # 更可靠的归属：按 id 显式列（与三个词典文件的收录范围一致）
    MEMBERS = {
        "robotics-advanced": ["zmp", "lipm", "wbc", "contact-dynamics", "actuator-control",
                              "calibration", "state-estimation", "retargeting", "data-flywheel",
                              "loco-manipulation", "realtime-scheduling", "onboard-compute",
                              "force-tactile-fusion", "dual-system-arch", "robot-lifecycle"],
        "ai-infra-deep": ["kv-cache", "paged-attention", "continuous-batching", "pd-disaggregation",
                          "speculative-decoding", "quantization", "parallelism", "collective-comm",
                          "prefix-caching", "serving-metrics", "long-context", "mixed-precision",
                          "moe", "mcp", "llm-app-platform"],
        "ecosystem": ["dds", "umi", "hardware-bus", "auto-quality-tools", "npi", "emc",
                      "checkpoint-resilience", "hf-ecosystem", "hmi"],
    }

    all_ids = [i for ids in MEMBERS.values() for i in ids]
    invisible = [i for i in all_ids if i not in cov]

    P = []
    A = P.append
    A('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">')
    A('<meta name="viewport" content="width=device-width,initial-scale=1">')
    A("<title>机器人 &amp; AI 的隐形知识地图</title><style>")
    A("""
:root{--bg:#0d1117;--panel:#161b22;--panel2:#1c2128;--line:#30363d;--fg:#e6edf3;
--muted:#8b949e;--dim:#6e7681}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.75 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1060px;margin:0 auto;padding:46px 24px 96px}
h1{font-size:29px;margin:0 0 8px;letter-spacing:-.4px}
.lede{color:var(--muted);font-size:13.5px;margin:0 0 30px}
h2{font-size:21px;margin:54px 0 6px;padding-left:14px;border-left:4px solid #58a6ff}
h2+.blurb{color:var(--muted);font-size:13.5px;margin:0 0 18px;padding-left:18px}
h3{font-size:16px;margin:34px 0 12px;color:#c9d1d9}
.stats{display:flex;gap:12px;flex-wrap:wrap;margin:0 0 24px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:10px;
padding:16px 20px;flex:1;min-width:148px}
.stat b{display:block;font-size:25px;font-weight:700;letter-spacing:-.5px}
.stat span{font-size:12px;color:var(--muted)}
.stat.warn b{color:#f85149}
.note{background:#1c2128;border-left:3px solid #58a6ff;border-radius:8px;
padding:15px 19px;margin:20px 0;font-size:13.5px;color:#c9d1d9}
.note.warn{border-left-color:#f85149}
table{width:100%;border-collapse:collapse;background:var(--panel);
border:1px solid var(--line);border-radius:10px;overflow:hidden;font-size:13.5px}
td,th{padding:9px 12px;border-bottom:1px solid #21262d;text-align:left}
th{color:#8b949e;font-weight:500;font-size:12px}
tr:last-child td{border-bottom:none}
.pct{text-align:right;font-variant-numeric:tabular-nums;width:74px}
.bar{height:7px;background:#21262d;border-radius:4px;overflow:hidden;margin-top:2px}
.bar i{display:block;height:100%;border-radius:4px}
details.skill{background:var(--panel);border:1px solid var(--line);
border-radius:10px;margin:8px 0;overflow:hidden}
details.skill>summary{cursor:pointer;padding:13px 16px;display:flex;
align-items:center;gap:11px;list-style:none;font-size:14.5px}
details.skill>summary::-webkit-details-marker{display:none}
details.skill>summary::before{content:"▸";color:var(--dim);font-size:12px}
details.skill[open]>summary::before{content:"▾"}
details.skill[open]>summary{border-bottom:1px solid var(--line);background:var(--panel2)}
summary .nm{font-weight:600;flex:1}
summary .lvl{font-size:11px;color:#7d8590;border:1px solid var(--line);
border-radius:4px;padding:1px 6px}
summary .cov{font-variant-numeric:tabular-nums;font-weight:600}
summary .cnt{color:var(--dim);font-size:11.5px}
.body{padding:4px 18px 16px}
.field{display:flex;gap:13px;padding:11px 0;border-bottom:1px dashed #21262d}
.field:last-child{border-bottom:none}
.field .k{flex:0 0 104px;color:#7d8590;font-size:12.5px;padding-top:2px}
.field .v{flex:1;font-size:13.5px;color:#d0d7de}
.field .v.md{line-height:1.9}
ol.lp{margin:0;padding-left:19px}
ol.lp li{margin:3px 0}
.stage{background:var(--panel);border:1px solid var(--line);border-radius:10px;
padding:13px 18px;margin:9px 0}
.stage b{color:#58a6ff;font-size:12.5px}
.stage .sk{font-size:13.5px;margin-top:5px;color:#c9d1d9}
footer{margin-top:66px;padding-top:20px;border-top:1px solid var(--line);
color:var(--dim);font-size:12px}
""")
    A("</style></head><body><div class='wrap'>")
    A("<h1>机器人 &amp; AI 的隐形知识地图</h1>")
    A(f'<p class="lede">数据源：{len(uniq)} 条真实岗位 JD（去重后 {total} 条有正文）'
      f"　·　词典 130 条　·　本报告聚焦其中 {len(all_ids)} 条「JD 里看不见」的知识</p>")

    A('<div class="stats">')
    A(f'<div class="stat"><b>{total}</b><span>分析的 JD 条数</span></div>')
    A(f'<div class="stat"><b>{len(all_ids)}</b><span>本报告的隐形知识项</span></div>')
    A(f'<div class="stat warn"><b>{len(invisible)}</b><span>JD 里一次都没出现</span></div>')
    low = sum(1 for i in all_ids if 0 < cov.get(i, 0) / total < 0.02)
    A(f'<div class="stat"><b>{low}</b><span>可见度低于 2%</span></div>')
    A("</div>")

    A('<div class="note warn"><b>为什么叫「隐形」。</b>'
      f"这一批 {len(all_ids)} 个知识点，在 {total} 条 JD 里的平均可见度不到 5%，"
      f"其中 <b>{len(invisible)} 个一次都没出现</b>。"
      "原因不是它们不重要 —— 恰恰相反，"
      "<b>它们默认你会，所以 JD 不需要写</b>；而面试官会默认你知道，所以会直接追问。"
      "这就是转行者最容易踩的坑：<b>用 JD 关键词自学，永远学不到这一层。</b></div>")

    A("<h2>一、按可见度分档</h2>")
    A('<p class="blurb">可见度越低，越说明它是「隐性门槛」而不是「招聘硬性条件」</p>')
    A("<table><thead><tr><th>知识点</th><th>所属</th><th>熟练度</th>"
      "<th style='width:150px'>JD 可见度</th><th class='pct'>占比</th></tr></thead><tbody>")
    GN = {"robotics-advanced": "机器人进阶", "ai-infra-deep": "AI Infra", "ecosystem": "生态流程"}
    SORTED = [(i, cov.get(i, 0) / total) for i in all_ids]
    SORTED.sort(key=lambda x: x[1])
    for sid, c in SORTED:
        s = skills[sid]
        _, _, color = band_of(c)
        grp = next((GN[g] for g, ids in MEMBERS.items() if sid in ids), "")
        pct = "未出现" if c == 0 else f"{c:.1%}"
        w = min(c * 100 / 12 * 100, 100)
        A(f'<tr><td>{html.escape(s.display)}</td><td style="color:#8b949e">{grp}</td>'
          f'<td style="color:#7d8590;font-size:12.5px">{html.escape(s.level)}</td>'
          f'<td><div class="bar"><i style="width:{w:.1f}%;background:{color}"></i></div></td>'
          f'<td class="pct" style="color:{color}">{pct}</td></tr>')
    A("</tbody></table>")

    for gid, title, color, blurb in GROUPS:
        A(f'<h2 style="border-color:{color}">二、{html.escape(title)}</h2>')
        A(f'<p class="blurb">{html.escape(blurb)}</p>')
        ids = sorted(MEMBERS[gid], key=lambda i: cov.get(i, 0) / total)
        A('<div class="cards">')
        for i, sid in enumerate(ids, 1):
            if sid not in skills:
                continue
            _, _, c2 = band_of(cov.get(sid, 0) / total)
            A(card(skills[sid], cov.get(sid, 0), total, c2, open_it=(i == 1)))
        A("</div>")

    A('<h2 style="border-color:#3fb950">三、学习顺序</h2>')
    A('<p class="blurb">把全部 130 个技能按前置依赖拓扑排序 —— '
      '看这些隐形知识分别该在什么阶段补</p>')
    path_ids = [h.skill.id for h in atlas.must_have()] + [h.skill.id for h in atlas.nice_to_have()] + all_ids
    for st in build_learning_path(atlas, path_ids):
        names = []
        for x in st.get("skills", []):
            mark = " ★" if x["id"] in all_ids else ""
            names.append(html.escape(x["name"]) + mark)
        A(f'<div class="stage"><b>第 {st["stage"]} 阶段</b>'
          f'<div class="sk">{"　·　".join(names)}</div></div>')
    A('<div class="note">★ 标记的是本报告的隐形知识。'
      '注意它们分散在多个阶段 —— 说明这些不是「入门就该会的」，'
      '而是<b>必须按依赖顺序逐层补上去的</b>。</div>')

    A("<footer>由 jd-skill-atlas 生成 · 纯词典 + 规则抽取，无 LLM 参与　·　"
      "岗位数据来自 cn-job-radar</footer>")
    A("</div></body></html>")

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(P), encoding="utf-8")
    print(f"✓ 报告生成：{out}  ({out.stat().st_size // 1024} KB)")
    print(f"  JD {total} 条 · 隐形知识 {len(all_ids)} 项 · 其中 {len(invisible)} 项零出现")
    return 0


if __name__ == "__main__":
    sys.exit(main())
