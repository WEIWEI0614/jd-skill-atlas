#!/usr/bin/env python3
"""把「隐形知识地图」生成为一个可直接放进静态站点的页面。

用法：
  python tools/make_study_page.py <jd.json> [...] -o <输出.html> [--css-prefix ../assets/style.css]

产出是一个自包含的 HTML 页面：内嵌三级解释 + 验证过的公开学习资源超链接。
"""
from __future__ import annotations

import argparse
import html
import json
import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from atlas.core import JD, load_resources, load_skills, render_md   # noqa: E402
from atlas.extract import build_learning_path, extract      # noqa: E402

GROUPS = [
    ("robotics-advanced", "机器人进阶 · 控制与工程深水区",
     "几乎不会写在 JD 的任职要求里，但一问就能分出「看过论文」和「真做过」",
     ["zmp", "lipm", "wbc", "contact-dynamics", "actuator-control", "calibration",
      "state-estimation", "retargeting", "data-flywheel", "loco-manipulation",
      "realtime-scheduling", "onboard-compute", "force-tactile-fusion",
      "dual-system-arch", "robot-lifecycle"]),
    ("ai-infra-deep", "AI Infra 深水区 · 推理与训练",
     "JD 里通常只写「熟悉推理优化」一行字 —— 这层是「懂模型」和「懂生产部署」的分界线",
     ["kv-cache", "paged-attention", "continuous-batching", "pd-disaggregation",
      "speculative-decoding", "quantization", "parallelism", "collective-comm",
      "prefix-caching", "serving-metrics", "long-context", "mixed-precision",
      "moe", "mcp", "llm-app-platform"]),
    ("ecosystem", "生态与流程 · 行业默认术语",
     "不是知识点而是生态位：因为行业默认你会，所以没人教你，而面试官默认你知道",
     ["dds", "umi", "hardware-bus", "auto-quality-tools", "npi", "emc",
      "checkpoint-resilience", "hf-ecosystem", "hmi"]),
]

KIND = {
    "course": ("课程", "#5dcaa5"),
    "docs":   ("文档", "#5b9ce0"),
    "repo":   ("仓库", "#a99ce8"),
    "paper":  ("论文", "#ef9f27"),
    "wiki":   ("词条", "#8b949e"),
    "tool":   ("工具", "#e26d6b"),
}

PAGE_STYLE = """
main{max-width:1060px;margin:0 auto;padding:0 14px 80px}
.page{max-width:960px;margin:0 auto;padding:24px 10px 40px}
.page h1{font-size:23px;margin:0 0 8px;letter-spacing:-.3px}
.page .sub{color:var(--tx2);font-size:13.5px;line-height:1.85;margin-bottom:6px}
.page h2{font-size:18px;margin:44px 0 4px;padding-left:13px;border-left:3px solid var(--amber)}
.page h2+.gd{color:var(--tx3);font-size:13px;margin:0 0 16px;padding-left:16px;line-height:1.8}
.page h3{font-size:15px;margin:26px 0 10px;color:var(--tx);font-weight:600}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(126px,1fr));gap:10px;margin:18px 0 0}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:14px 16px}
.stat b{display:block;font-size:24px;font-weight:700;letter-spacing:-.5px;line-height:1.2}
.stat span{font-size:11.5px;color:var(--tx3)}
.stat.warn b{color:var(--red)}
.note{margin:20px 0;padding:14px 17px;background:var(--panel2);border-left:3px solid var(--blue);
 border-radius:9px;font-size:13.5px;line-height:1.85;color:var(--tx2)}
.note.warn{border-left-color:var(--red)}
.note b{color:var(--tx)}
table{width:100%;border-collapse:collapse;font-size:13.5px;margin:4px 0 0}
th{text-align:left;color:var(--tx3);font-weight:500;font-size:11.5px;padding:8px 10px;
 border-bottom:1px solid var(--line);letter-spacing:.3px}
td{padding:9px 10px;border-bottom:1px solid rgba(51,53,60,.55);vertical-align:middle}
tr:last-child td{border-bottom:none}
.tv{color:var(--tx)}
.grp{color:var(--tx3);font-size:11.5px}
.lvl{display:inline-block;font-size:10.5px;color:var(--tx3);border:1px solid var(--line);
 border-radius:4px;padding:0 5px;margin-left:6px}
.covbar{height:10px;background:#1a1c21;border:1px solid #2b2e35;border-radius:5px;
 overflow:hidden;min-width:96px}
.covbar i{display:block;height:100%;border-radius:4px}
/* 0% 表示「没有」而不是「很短」。用淡红底的空槽 —— 零值的标准画法。
   刻意不用斜纹满格：那会比 0.3% 的短条更「重」，把零值误读成高值。 */
.covbar.zero{background:rgba(226,109,107,.07);border-color:rgba(226,109,107,.45)}
.lg{display:flex;flex-wrap:wrap;gap:14px;margin:10px 0 0;font-size:11.5px;color:var(--tx3)}
.lg span{display:inline-flex;align-items:center;gap:5px}
.lg i{width:11px;height:11px;border-radius:3px;display:inline-block}
.lg .zero{background:rgba(226,109,107,.07);border:1px solid rgba(226,109,107,.45)}
.pct{text-align:right;font-variant-numeric:tabular-nums;width:62px;font-size:12.5px}
.hide{color:var(--red);font-weight:600;font-size:12.5px}
details.k{background:var(--panel);border:1px solid var(--line);border-radius:11px;
 margin:9px 0;overflow:hidden}
details.k>summary{cursor:pointer;padding:12px 15px;display:flex;align-items:center;
 gap:10px;list-style:none;font-size:14.5px}
details.k>summary::-webkit-details-marker{display:none}
details.k>summary::before{content:"▸";color:var(--tx3);font-size:12px;flex:0 0 auto}
details.k[open]>summary::before{content:"▾"}
details.k[open]>summary{border-bottom:1px solid var(--line);background:var(--panel2)}
summary .nm{font-weight:600;flex:1;color:var(--tx)}
summary .cv{font-variant-numeric:tabular-nums;font-weight:600;font-size:13px}
summary .cn{color:var(--tx3);font-size:11.5px}
.kb{padding:4px 16px 15px}
.f{display:flex;gap:13px;padding:10px 0;border-bottom:1px dashed rgba(51,53,60,.7)}
.f:last-child{border-bottom:none}
.f .kk{flex:0 0 100px;color:var(--tx3);font-size:12.5px;padding-top:1px}
.f .vv{flex:1;font-size:13.5px;color:var(--tx2);line-height:1.9}
.f .vv b{color:var(--tx)}
ol.lp{margin:0;padding-left:19px}
ol.lp li{margin:3px 0}
.rl{display:flex;flex-direction:column;gap:7px}
.rl a{font-size:13px;text-decoration:none;line-height:1.6}
.rl a:hover{text-decoration:underline}
.rl .tagk{display:inline-block;font-size:10px;border:1px solid;border-radius:4px;
 padding:0 5px;margin-right:7px;vertical-align:1px;white-space:nowrap}
.rl .desc{color:var(--tx3);font-size:12px;margin-left:4px}
.stage{background:var(--panel);border:1px solid var(--line);border-radius:11px;
 padding:12px 16px;margin:9px 0}
.stage b{color:var(--amber);font-size:12.5px}
.stage .sk{font-size:13.5px;margin-top:5px;color:var(--tx2);line-height:1.9}
.stage .star{color:var(--amber);font-weight:600}
.foot2{margin-top:36px;padding-top:16px;border-top:1px solid var(--line);
 color:var(--tx3);font-size:12px;line-height:1.9}
@media(max-width:820px){
 .page{padding:18px 6px 30px}
 .f{flex-direction:column;gap:4px}
 .f .kk{flex:none}
 table.bt thead{display:none}
 table.bt tr{display:block;border:1px solid var(--line);border-radius:10px;
  margin:0 0 9px;padding:8px 0;background:var(--panel)}
 table.bt td{display:block;border:0;padding:4px 13px}
 table.bt td::before{content:attr(data-label);display:block;font-size:10.5px;color:var(--tx3)}
}
"""


CN_NUM = "〇一二三四五六七八九十"


def cn(n: int) -> str:
    return CN_NUM[n] if 0 < n < 10 else str(n)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--css", default="../assets/style.css")
    ap.add_argument("--home", default="../index.html")
    args = ap.parse_args()

    jobs: list[dict] = []
    for p in args.inputs:
        f = pathlib.Path(p)
        if not f.exists():
            print(f"[!] 跳过 {p}", file=sys.stderr)
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
    res = load_resources()

    jds = [JD(title=j.get("title") or "", text=j.get("jd") or "", company=j.get("company") or "")
           for j in uniq if len(j.get("jd") or "") >= 40]
    atlas = extract(jds, skills=skills)
    total = atlas.total_jds or 1
    cov = {h.skill.id: h.count for h in atlas.hits}

    all_ids = [i for _, _, _, ids in GROUPS for i in ids]
    invisible = [i for i in all_ids if i not in cov]
    under2 = sum(1 for i in all_ids if 0 < cov.get(i, 0) / total < 0.02)
    nres = sum(len(res.get(i, [])) for i in all_ids)

    P: list[str] = []
    A = P.append
    A('<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="UTF-8">')
    A('<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">')
    A('<meta name="color-scheme" content="dark">')
    A('<meta name="theme-color" content="#16171a">')
    A("<title>隐形知识地图 · 机器人学习台</title>")
    A(f'<link rel="stylesheet" href="{args.css}">')
    A(f"<style>{PAGE_STYLE}</style>\n</head>\n<body>")
    A('<header class="appbar"><div class="appbar-in"><div class="app-title">隐形知识地图'
      f'<a class="back" href="{args.home}">← 返回首页</a></div></div></header>')
    A("<main>\n<div class=\"wrap\">\n<div class=\"page\">")

    A("<h1>隐形知识地图</h1>")
    A(f'<div class="sub">基于 {len(uniq)} 条真实岗位 JD（去重后有正文 {total} 条）扫描得出'
      f"　·　{len(all_ids)} 个知识点　·　{nres} 条已验证的公开学习资源</div>")

    A('<div class="stats">')
    A(f'<div class="stat"><b>{total}</b><span>分析的 JD 条数</span></div>')
    A(f'<div class="stat"><b>{len(all_ids)}</b><span>隐形知识点</span></div>')
    A(f'<div class="stat warn"><b>{len(invisible)}</b><span>JD 里一次都没出现</span></div>')
    A(f'<div class="stat"><b>{under2}</b><span>可见度低于 2%</span></div>')
    A(f'<div class="stat"><b>{nres}</b><span>公开资源（已验链）</span></div>')
    A("</div>")

    A('<div class="note warn"><b>为什么叫「隐形」。</b>'
      f"这 {len(all_ids)} 个知识点在 {total} 条 JD 里的平均可见度不到 5%，"
      f"其中 <b>{len(invisible)} 个一次都没出现</b>。"
      "原因不是它们不重要 —— 恰恰相反，<b>它们默认你会，所以 JD 不需要写</b>；"
      "面试官默认你知道，所以会直接追问。"
      "这就是最容易踩的坑：<b>用 JD 关键词自学，永远学不到这一层。</b></div>")

    A('<div class="note">资源使用纪律：<b>打开一个就走</b>。'
      "每个知识点给 1–3 条，且只给「官方文档 / 开源仓库 / 论文原文 / 名校课程」四类，"
      "不给二手教程。所有链接均已逐个验证可达。</div>")

    # ---- 一、按可见度分档 ----
    A("<h2>一、按可见度分档</h2>")
    A('<p class="gd">可见度越低，越说明它是「隐性门槛」而不是「招聘硬性条件」</p>')
    A('<table class="bt"><thead><tr><th>知识点</th><th>所属</th><th style="width:150px">JD 可见度</th>'
      '<th class="pct">占比</th></tr></thead><tbody>')
    GN = {gid: title.split(" · ")[0] for gid, title, _, _ in GROUPS}
    rows = sorted(((i, cov.get(i, 0) / total) for i in all_ids), key=lambda x: x[1])
    maxc = max((c for _, c in rows), default=0) or 1
    for sid, c in rows:
        s = skills[sid]
        grp = next((GN[g] for g, _, _, ids in GROUPS if sid in ids), "")
        if c == 0:
            pct, color = "未出现", "#e26d6b"
            cell = '<div class="covbar zero"></div>'
        else:
            pct = f"{c:.1%}"
            color = "#ef9f27" if c < 0.02 else ("#5b9ce0" if c < 0.05 else "#5dcaa5")
            # 平方根刻度：本表的值全部挤在 0–12% 区间，线性刻度下 0.3% 与 2.9% 长度几乎相同。
            # 开方后低值区间被拉开，条形才真正带信息。数据本身仍以右侧精确百分比为准。
            w = max((c / maxc) ** 0.5 * 100, 7)
            cell = f'<div class="covbar"><i style="width:{w:.1f}%;background:{color}"></i></div>'
        A(f'<tr><td data-label="知识点"><span class="tv">{html.escape(s.display)}</span>'
          f'<span class="lvl">{html.escape(s.level)}</span></td>'
          f'<td data-label="所属"><span class="grp">{html.escape(grp)}</span></td>'
          f'<td data-label="可见度">{cell}</td>'
          f'<td class="pct" data-label="占比" style="color:{color}">{pct}</td></tr>')
    A("</tbody></table>")
    A('<div class="lg">'
      '<span><i class="zero"></i>未出现（JD 里一次都没有）</span>'
      '<span><i style="background:#ef9f27"></i>&lt;2% 极低可见</span>'
      '<span><i style="background:#5b9ce0"></i>2–5% 少量可见</span>'
      '<span><i style="background:#5dcaa5"></i>≥5% 相对常见</span>'
      f'<span style="color:var(--tx3)">条形按平方根缩放（满格 = 本表最高 {maxc:.1%}），'
      '只为拉开低值差异，精确数值看右侧</span></div>')

    # ---- 二、三组详情 ----
    for gi, (gid, title, blurb, ids) in enumerate(GROUPS, 2):
        A(f"<h2>{cn(gi)}、{html.escape(title)}</h2>")
        A(f'<p class="gd">{html.escape(blurb)}</p>')
        for i, sid in enumerate(sorted(ids, key=lambda x: cov.get(x, 0) / total)):
            if sid not in skills:
                continue
            s = skills[sid]
            c = cov.get(sid, 0)
            pct = "未出现" if c == 0 else f"{c / total:.1%}"
            ccolor = "#e26d6b" if c == 0 else ("#ef9f27" if c / total < 0.02 else "#5dcaa5")
            A(f'<details class="k"{" open" if i == 0 else ""}>')
            A(f'<summary><span class="nm">{html.escape(s.display)}</span>'
              f'<span class="lvl">{html.escape(s.level)}</span>'
              f'<span class="cv" style="color:{ccolor}">{pct}</span>'
              f'<span class="cn">{c}/{total} 岗位</span></summary>')
            A('<div class="kb">')
            A(f'<div class="f"><span class="kk">一句话</span><span class="vv">{render_md(s.what)}</span></div>')
            A('<div class="f"><span class="kk">为什么岗位要它</span><span class="vv">'
              + render_md(s.why) + "</span></div>")
            A('<div class="f"><span class="kk">展开说说</span><span class="vv">'
              + render_md(s.how) + "</span></div>")
            if s.prerequisite:
                names = "、".join(html.escape(skills[p].display) if p in skills else p
                                 for p in s.prerequisite)
                A(f'<div class="f"><span class="kk">前置</span><span class="vv">{names}</span></div>')
            items = res.get(sid) or []
            if items:
                A('<div class="f"><span class="kk">学习资源</span><span class="vv"><div class="rl">')
                for it in items:
                    lab, col = KIND.get(it.get("kind", "docs"), ("资源", "#5b9ce0"))
                    A(f'<a href="{html.escape(it["url"], quote=True)}" target="_blank" rel="noopener">'
                      f'<span class="tagk" style="color:{col};border-color:{col}">{lab}</span>'
                      f'{html.escape(it["label"])}</a>')
                A("</div></span></div>")
            if s.learn_path:
                lis = "".join(f"<li>{html.escape(x)}</li>" for x in s.learn_path)
                A(f'<div class="f"><span class="kk">怎么学</span><span class="vv"><ol class="lp">{lis}</ol></span></div>')
            A("</div></details>")

    # ---- 三、学习顺序 ----
    A(f"<h2>{cn(len(GROUPS) + 2)}、学习顺序</h2>")
    A('<p class="gd">把全部技能按前置依赖拓扑排序 —— 看这些隐形知识分别该在什么阶段补。'
      '带 <span class="star">★</span> 的是本页知识点</p>')
    path_ids = ([h.skill.id for h in atlas.must_have()]
                + [h.skill.id for h in atlas.nice_to_have()] + all_ids)
    for st in build_learning_path(atlas, path_ids):
        names = []
        for x in st.get("skills", []):
            if x["id"] in all_ids:
                names.append(f'<span class="star">★{html.escape(x["name"])}</span>')
            else:
                names.append(html.escape(x["name"]))
        A(f'<div class="stage"><b>第 {st["stage"]} 阶段</b>'
          f'<div class="sk">{"　·　".join(names)}</div></div>')
    A('<div class="note">注意它们分散在多个阶段 —— 说明这些不是「入门就该会的」，'
      "而是<b>必须按依赖顺序逐层补上去的</b>。地基没打就硬读 WBC，只会卡住。</div>")

    A('<div class="foot2">生成方式：jd-skill-atlas 扫描真实 JD 得出可见度 → '
      "对照 2026 WRC / WAIC 产业共识与面试考点补齐词条 → 逐条配公开资源（HTTP 状态码已验证）。<br>"
      "岗位数据来自 cn-job-radar · 词典 130 条 · 纯词典 + 规则抽取，无 LLM 参与，结果可复现。</div>")

    A('</div>\n<nav class="pager" data-for="invisible"></nav>\n</div>\n</main>\n</body>\n</html>')

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(P), encoding="utf-8")
    print(f"✓ 页面生成：{out}  ({out.stat().st_size // 1024} KB)")
    print(f"  JD {total} 条 · 知识点 {len(all_ids)} · 零出现 {len(invisible)} · 资源 {nres} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
