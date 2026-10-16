"""冒烟测试。全部离线，不联网。

    pytest -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    for m in [k for k in list(sys.modules) if k.startswith("atlas")]:
        del sys.modules[m]
    import atlas.core as core
    core.HOME = tmp_path
    core.USER_SKILLS_DIR = tmp_path / "skills"
    core.REPORT_DIR = tmp_path / "reports"
    core.DATA_DIR = tmp_path / "data"
    core.ensure_dirs()
    return core


# ---------------------------------------------------------------------------
#  技能词典
# ---------------------------------------------------------------------------

def test_dictionary_loads():
    from atlas.core import load_skills, list_skill_files
    skills = load_skills()
    assert len(skills) >= 40, f"词典太小：{len(skills)}"
    files = list_skill_files()
    domains = {f["domain"] for f in files}
    assert {"robotics", "ai", "investment", "tools", "common"} <= domains


def test_every_skill_has_three_layers():
    """每个词条都必须有 what / why / how —— 只写定义是不合格的。"""
    from atlas.core import load_skills
    bad = []
    for s in load_skills().values():
        missing = [k for k in ("what", "why", "how") if not getattr(s, k).strip()]
        if missing:
            bad.append((s.id, missing))
    assert not bad, f"这些词条三层不全：{bad}"


def test_skill_ids_unique():
    from atlas.core import load_skills
    skills = load_skills()
    # load_skills 用 id 做 key，重复会被覆盖 —— 所以这里比对文件里的原始条数
    from atlas.core import BUILTIN_SKILLS_DIR, load_yaml
    total = 0
    for p in BUILTIN_SKILLS_DIR.glob("*.yaml"):
        total += len(load_yaml(p).get("skills") or [])
    assert len(skills) == total, f"有重复 id：文件里 {total} 条，去重后只剩 {len(skills)}"


def test_no_bare_overgeneric_alias():
    """别名不能是「协同」这种到处都有的词 —— 会造成大面积误判。"""
    from atlas.core import load_skills
    TOO_GENERIC = {"协同", "沟通", "管理", "研究", "分析", "开发", "设计", "系统"}
    bad = [(s.id, a) for s in load_skills().values() for a in s.aliases if a in TOO_GENERIC]
    assert not bad, f"这些别名太泛会误判：{bad}"


# ---------------------------------------------------------------------------
#  抽取
# ---------------------------------------------------------------------------

def _mk_jd(title: str, text: str, company: str = "", pad: bool = True):
    """造一条 JD。

    pad=True 时补足正文长度 —— 否则会被 extract 的 min_jd_chars 过滤掉
    （真实 JD 都远超 80 字，过滤的是抓取残缺的那种）。
    """
    from atlas.core import JD
    if pad:
        text = text + "。" + "岗位要求候选人具备良好的沟通能力与团队协作精神，能够独立推进工作。" * 4
    return JD(title=title, text=text, company=company)


def test_extract_basic():
    from atlas.extract import extract
    jds = [
        _mk_jd("算法工程师", "熟悉 PyTorch 和 Python，有强化学习经验，了解 SLAM 定位建图。"),
        _mk_jd("产品经理", "负责需求分析，熟悉 Python 数据分析，具备跨部门协作能力。"),
        _mk_jd("投资经理", "负责尽职调查和估值分析，熟悉 IRR 计算。"),
    ]
    atlas = extract(jds)
    assert atlas.total_jds == 3
    ids = {h.skill.id for h in atlas.hits}
    assert "python" in ids
    assert "irr" in ids or "dd" in ids


def test_coverage_and_tiers():
    from atlas.extract import extract
    # Python 出现在 3/3，IRR 只出现在 1/3
    jds = [
        _mk_jd("A", "Python Python Python 数据分析"),
        _mk_jd("B", "Python 机器学习"),
        _mk_jd("C", "Python IRR 尽职调查"),
    ]
    atlas = extract(jds)
    py = atlas.get("python")
    assert py is not None and py.count == 3
    assert py.count / atlas.total_jds == 1.0
    assert py.skill.id in {h.skill.id for h in atlas.must_have()}


def test_english_alias_respects_word_boundary():
    """英文别名要加词边界，否则 hit 会命中 within。"""
    from atlas.extract import extract
    jds = [_mk_jd("测试岗位", "This is a git repository. Nothing else here to see.")]
    atlas = extract(jds)
    # 「git」不应被当作命中（这里确实有 git，所以换个词验证边界逻辑）
    jds2 = [_mk_jd("测试岗位", "The within function has nothing to do with this sentence at all.")]
    atlas2 = extract(jds2)
    ids2 = {h.skill.id for h in atlas2.hits}
    assert "python" not in ids2, "英文别名边界失效"


def test_company_names_not_treated_as_skills():
    """JD 里的公司名不该被当成待补技能。"""
    from atlas.extract import extract
    jds = [_mk_jd("工程师", "我们是一家优秀公司。", company="某某机器人科技有限公司")] * 3
    atlas = extract(jds)
    terms = {t for t, _ in atlas.unknown_terms}
    assert "某某机器人科技有限公司" not in terms


def test_short_jds_skipped():
    from atlas.extract import extract
    jds = [_mk_jd("A", "x" * 300), _mk_jd("B", "短", pad=False)]
    atlas = extract(jds, min_jd_chars=80)
    assert atlas.total_jds == 1, "过短的 JD 应被跳过"


# ---------------------------------------------------------------------------
#  缺口与学习路径
# ---------------------------------------------------------------------------

def test_gap_analysis():
    from atlas.extract import extract, gap_analysis
    jds = [
        _mk_jd("A", "需要 Python 和 SQL，熟悉机器学习。"),
        _mk_jd("B", "需要 Python，了解 SQL 和深度学习。"),
        _mk_jd("C", "需要 Python 与 SQL。"),
    ]
    atlas = extract(jds)
    g = gap_analysis(atlas, ["Python"])
    assert g["required_count"] > 0
    owned_ids = {x["id"] for x in g["owned"]}
    assert "python" in owned_ids
    assert 0 < g["coverage"] <= 1
    # 没掌握的
    assert all(x["id"] != "python" for x in g["missing"])


def test_learning_path_is_topologically_sorted():
    """前置技能必须排在依赖它的技能之前 —— 这是学习路径的核心价值。"""
    from atlas.extract import extract, build_learning_path
    jds = [_mk_jd("A", "Transformer 和 LLM 和 Agent 和 Python。")] * 3
    atlas = extract(jds)
    stages = build_learning_path(atlas, [h.skill.id for h in atlas.hits])
    assert stages, "应该排出阶段"

    pos: dict[str, int] = {}
    for st in stages:
        for s in st["skills"]:
            pos[s["id"]] = st["stage"]

    from atlas.core import load_skills
    skills = load_skills()
    checked = 0
    for st in stages:
        for s in st["skills"]:
            sk = skills.get(s["id"])
            if not sk:
                continue
            for p in sk.prerequisite:
                if p in pos:
                    assert pos[p] <= pos[s["id"]], \
                        f"前置 {p} 排在 {s['id']} 之后了"
                    checked += 1
    assert checked > 0, "测试用例里没有形成依赖关系，检查一下"


def test_prerequisite_closure_expansion():
    """只选 Agent，也应该把它的前置（Transformer / LLM）拉进路径。"""
    from atlas.extract import extract, build_learning_path
    jds = [_mk_jd("A", "Agent 智能体 Transformer LLM 大模型 Python")] * 3
    atlas = extract(jds)
    stages = build_learning_path(atlas, ["agent"])
    all_ids = {s["id"] for st in stages for s in st["skills"]}
    assert "agent" in all_ids
    assert len(all_ids) > 1, "前置技能没有被展开进来"


# ---------------------------------------------------------------------------
#  端到端
# ---------------------------------------------------------------------------

def test_end_to_end_report(sandbox, tmp_path):
    from atlas.core import load_jds
    from atlas.extract import extract
    from atlas.report import write_report

    src = tmp_path / "scored.json"
    src.write_text(json.dumps({"jobs": [
        {"title": "算法工程师", "company": "甲", "score": 80,
         "jd": "熟悉 Python、PyTorch，有强化学习与 SLAM 经验，具备跨部门协作能力。"},
        {"title": "产品经理", "company": "乙", "score": 75,
         "jd": "负责需求分析与项目管理，熟悉 Python 数据分析。"},
        {"title": "投资经理", "company": "丙", "score": 70,
         "jd": "负责尽职调查、估值分析，熟悉 IRR 与 DPI。"},
    ]}, ensure_ascii=False), encoding="utf-8")

    jds = load_jds(src)
    assert len(jds) == 3
    atlas = extract(jds)

    paths = write_report(atlas, out_dir=tmp_path / "reports", title="测试图谱")
    md = paths["md"].read_text(encoding="utf-8")
    assert "测试图谱" in md
    assert "必备" in md or "加分" in md
    assert "{total}" not in md, "Markdown 里有未渲染的占位符"

    data = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert data["total_jds"] == 3
    assert data["skills"]
    s0 = data["skills"][0]
    for k in ("id", "name", "coverage", "count", "what", "why", "how", "learn_path", "samples"):
        assert k in s0, f"缺字段 {k}"
