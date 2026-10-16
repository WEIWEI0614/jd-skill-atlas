"""技能抽取：从一批 JD 里找出「这个行业要什么能力」。

纯词典 + 规则实现，不依赖 LLM —— 好处是快、可复现、零成本、离线可用。
LLM 只用来补充词典没收录的新词（见 unknown_terms）。
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from .core import Atlas, JD, Skill, SkillHit, load_skills

# 词典没收录时，用这些模式捞「看起来像术语」的词，提示用户补充词典
TERM_PATTERNS = [
    # 英文技术词/缩写：ROS、MPC、Isaac Sim、C++
    re.compile(r"\b[A-Z][A-Za-z0-9]{1,14}(?:\s[A-Z][A-Za-z0-9]{1,14})?\b"),
    # 中文技术短语：××算法、××模型、××平台…
    re.compile(r"[\u4e00-\u9fa5]{2,7}(?:算法|模型|系统|平台|框架|引擎|协议|接口|架构|方案|流程)"),
    # 工具/框架名：PyTorch、MuJoCo
    re.compile(r"\b[A-Z][a-z]+[A-Z][A-Za-z]+\b"),
]

# 这些词太泛，当术语提出来没意义
STOPWORDS = {
    "JD", "AI", "IT", "HR", "OK", "ID", "PDF", "URL", "API", "CEO", "CTO", "KPI",
    "PPT", "Excel", "Word", "OKR", "B端", "C端", "SOP", "ROI", "GDP", "PR", "IP",
    "年", "月", "日", "岗位职责", "任职要求", "职位描述", "工作内容", "加分项",
    "本科", "硕士", "博士", "全职", "兼职", "实习", "北京", "上海", "深圳",
}

# 一个 JD 里同一个技能最多记这么多字符的原文片段
SNIPPET_RADIUS = 30


def _snippet(text: str, start: int, end: int) -> str:
    """截取命中位置周围的上下文，作为「JD 里怎么说的」证据。"""
    a = max(0, start - SNIPPET_RADIUS)
    b = min(len(text), end + SNIPPET_RADIUS)
    s = re.sub(r"\s+", " ", text[a:b]).strip()
    return ("…" if a > 0 else "") + s + ("…" if b < len(text) else "")


def extract(jds: list[JD], skills: dict[str, Skill] | None = None,
            min_jd_chars: int = 80) -> Atlas:
    """从 JD 集合里抽取技能图谱。

    min_jd_chars: 正文短于这个长度的 JD 会被跳过（多半是抓取残缺）。
    """
    skills = skills if skills is not None else load_skills()
    usable = [j for j in jds if len(j.text) >= min_jd_chars or len(j.title) >= 4]

    # JD 里出现的公司名要排除掉 —— 它们是招聘方，不是技能。
    company_tokens: set[str] = set()
    for j in jds:
        for part in re.split(r"[\s,，、()（）]+", j.company or ""):
            if len(part) >= 2:
                company_tokens.add(part.lower())

    hits: dict[str, SkillHit] = {}
    term_counter: Counter[str] = Counter()
    by_domain: Counter[str] = Counter()

    for jd in usable:
        haystack = f"{jd.title}\n{jd.text}"
        matched_here: set[str] = set()

        for sid, skill in skills.items():
            m = skill.matches().search(haystack)
            if not m:
                continue
            h = hits.get(sid)
            if h is None:
                h = hits[sid] = SkillHit(skill=skill)
            h.count += 1
            label = f"{jd.title}" + (f" @ {jd.company}" if jd.company else "")
            if label not in h.jobs:
                h.jobs.append(label)
            if len(h.samples) < 3:
                h.samples.append(_snippet(haystack, m.start(), m.end()))
            matched_here.add(sid)
            by_domain[skill.domain] += 1

        # 找词典没收录的候选术语
        for pat in TERM_PATTERNS:
            for m in pat.finditer(jd.text):
                term = m.group(0).strip()
                if len(term) < 2 or term in STOPWORDS:
                    continue
                if term.lower() in company_tokens:
                    continue
                # 已被词典覆盖的（作为别名出现的）就不再作为新词提
                if any(term.lower() in {a.lower() for a in ([s.name, s.zh, s.full_name, *s.aliases]) if a}
                       for s in skills.values()):
                    continue
                term_counter[term] += 1

    ranked = sorted(hits.values(), key=lambda h: (-h.count, h.skill.name))
    # 候选新词里，被词典里已有技能包含或反向包含的过滤掉，减少噪音
    known = {s.name.lower() for s in skills.values()}
    unknown = [(t, c) for t, c in term_counter.most_common(400)
               if c >= 2 and t.lower() not in known
               and t.lower() not in company_tokens
               and not any(t.lower() in k or k in t.lower() for k in known)]

    return Atlas(
        total_jds=len(usable),
        hits=ranked,
        unknown_terms=unknown[:80],
        by_domain=dict(by_domain.most_common()),
        meta={
            "skills_in_dict": len(skills),
            "jds_input": len(jds),
            "jds_used": len(usable),
            "domains_in_dict": sorted({s.domain for s in skills.values()}),
        },
    )


# ---------------------------------------------------------------------------
#  缺口分析：我的技能 vs JD 要求
# ---------------------------------------------------------------------------

def gap_analysis(atlas: Atlas, have: list[str], threshold: float | None = None) -> dict:
    """对比「我有的技能」和「JD 要求的技能」。

    have 传技能 id 或名称（中英均可）。
    """
    have_norm = {h.strip().lower() for h in have if h and h.strip()}

    def owns(skill: Skill) -> bool:
        candidates = {skill.id.lower(), skill.name.lower(), skill.zh.lower(), skill.full_name.lower()}
        candidates |= {a.lower() for a in skill.aliases}
        return bool(candidates & have_norm)

    t = Atlas.MUST if threshold is None else threshold
    required = [h for h in atlas.hits
                if atlas.total_jds and h.count / atlas.total_jds >= t]

    owned, missing = [], []
    for h in required:
        (owned if owns(h.skill) else missing).append(h)

    # 学习顺序：按前置依赖拓扑排序（前置没掌握的排前面）
    def sort_key(h: SkillHit):
        unmet = [p for p in h.skill.prerequisite if p not in {x.skill.id for x in owned}]
        lvl = h.skill.level_index
        return (-h.count, len(unmet), lvl)

    missing.sort(key=sort_key)

    return {
        "required_count": len(required),
        "owned": [h.to_dict(atlas.total_jds) for h in owned],
        "missing": [h.to_dict(atlas.total_jds) for h in missing],
        "coverage": round(len(owned) / len(required), 3) if required else 0.0,
    }


# ---------------------------------------------------------------------------
#  学习路径：按前置依赖排出「先学什么后学什么」
# ---------------------------------------------------------------------------

def build_learning_path(atlas: Atlas, skill_ids: list[str]) -> list[dict]:
    """给一组技能，按前置依赖拓扑排序，输出分阶段的学习顺序。

    关键点：必须先把**前置技能的闭包**展开进来。
    否则当选中集合里全是「必备技能」时，它们彼此之间很少有依赖关系，
    结果会全挤在阶段 1 —— 那样就等于没排序。
    """
    all_skills = {h.skill.id: h.skill for h in atlas.hits}
    by_id = {h.skill.id: h for h in atlas.hits}

    chosen_ids = {sid for sid in skill_ids if sid in by_id}
    if not chosen_ids:
        return []

    # 展开依赖闭包：前置技能也要拉进来参与排序
    closure = set(chosen_ids)
    stack = list(chosen_ids)
    while stack:
        sid = stack.pop()
        sk = all_skills.get(sid)
        if sk is None:
            continue
        for p in sk.prerequisite:
            if p in all_skills and p not in closure:
                closure.add(p)
                stack.append(p)

    depth_of: dict[str, int] = {}

    def depth(sid: str) -> int:
        """一个技能的阶段 = 它所有前置技能的阶段 + 1（取最大值）。带环保护。"""
        if sid in depth_of:
            return depth_of[sid]
        depth_of[sid] = 0                      # 先占位，防环
        sk = all_skills.get(sid)
        if sk is None:
            return 0
        d = 0
        for p in sk.prerequisite:
            if p in closure and p != sid:
                d = max(d, depth(p) + 1)
        depth_of[sid] = d
        return d

    stages: dict[int, list[SkillHit]] = defaultdict(list)
    for sid in closure:
        h = by_id.get(sid)
        if h is not None:
            stages[depth(sid)].append(h)

    out = []
    for i in sorted(stages):
        stage = stages[i]
        if not stage:
            continue
        out.append({
            "stage": len(out) + 1,
            "skills": [h.to_dict(atlas.total_jds) for h in
                       sorted(stage, key=lambda x: (-x.count, x.skill.level_index))],
        })
    return out
