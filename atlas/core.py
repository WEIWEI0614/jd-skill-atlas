"""数据模型与技能词典加载。

设计原则：
  1. 技能词典（data/skills/*.yaml）是资产，代码只是读它。加技能 = 加一条 YAML。
  2. 术语解释是这个项目的核心价值 —— 每一条都要求「是什么 / 为什么重要 / 怎么学」三层齐全。
  3. 不依赖任何 LLM 也能跑完整流程；LLM 只用来补充词典没收录的词。
"""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PKG_DIR = Path(__file__).resolve().parent
BUILTIN_SKILLS_DIR = PKG_DIR / "data" / "skills"

# 用户目录：默认 ~/.jd-skill-atlas，可用环境变量覆盖
HOME = Path(os.environ.get("ATLAS_HOME") or (Path.home() / ".jd-skill-atlas"))
USER_SKILLS_DIR = HOME / "skills"
REPORT_DIR = HOME / "reports"
DATA_DIR = HOME / "data"

# 领域显示名
DOMAIN_LABELS = {
    "ai": "人工智能",
    "robotics": "机器人 / 具身智能",
    "investment": "投资 / 金融",
    "data": "数据 / 工程",
    "product": "产品 / 商业",
    "soft": "通用职场能力",
}

# 熟练度分级
LEVEL_ORDER = ["入门", "进阶", "高级", "专家"]


def ensure_dirs() -> None:
    for d in (USER_SKILLS_DIR, REPORT_DIR, DATA_DIR):
        d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
#  技能条目
# ---------------------------------------------------------------------------

@dataclass
class Skill:
    """一个技能的完整档案。"""
    id: str
    name: str
    domain: str = "soft"
    zh: str = ""
    full_name: str = ""
    aliases: list[str] = field(default_factory=list)
    level: str = "进阶"
    what: str = ""          # 一句话定义
    why: str = ""           # 为什么这个岗位要它
    how: str = ""           # 展开解释：怎么落地、常见坑
    prerequisite: list[str] = field(default_factory=list)
    learn_path: list[str] = field(default_factory=list)
    jd_phrases: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    _pattern: re.Pattern | None = None

    @property
    def display(self) -> str:
        if self.zh and self.full_name:
            return f"{self.name}（{self.zh}）"
        return self.name

    @property
    def level_index(self) -> int:
        try:
            return LEVEL_ORDER.index(self.level)
        except ValueError:
            return 1

    def matches(self) -> re.Pattern:
        """所有别名 + 名称编译成一个正则（懒加载）。"""
        if self._pattern is None:
            terms = {self.name, self.full_name, self.zh, *self.aliases}
            terms = {t.strip() for t in terms if t and t.strip()}
            # 长的排前面，避免「机器学习」先匹配掉「机器学习工程」
            parts = []
            for t in sorted(terms, key=len, reverse=True):
                esc = re.escape(t)
                # 纯英文/数字的术语加词边界，避免 hit 命中了 within
                if re.fullmatch(r"[A-Za-z0-9+#.\- ]+", t):
                    esc = rf"(?<![A-Za-z0-9]){esc}(?![A-Za-z0-9])"
                parts.append(esc)
            self._pattern = re.compile("|".join(parts), re.IGNORECASE) if parts else re.compile(r"(?!)")
        return self._pattern

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "zh": self.zh, "full_name": self.full_name,
            "domain": self.domain, "domain_label": DOMAIN_LABELS.get(self.domain, self.domain),
            "level": self.level, "what": self.what, "why": self.why, "how": self.how,
            "prerequisite": self.prerequisite, "learn_path": self.learn_path,
            "tags": self.tags, "aliases": self.aliases,
        }


def _skill_from_dict(raw: dict, fallback_id: str = "") -> Skill | None:
    sid = str(raw.get("id") or fallback_id).strip()
    name = str(raw.get("name") or "").strip()
    if not sid or not name:
        return None
    return Skill(
        id=sid,
        name=name,
        domain=str(raw.get("domain") or "soft").strip(),
        zh=str(raw.get("zh") or "").strip(),
        full_name=str(raw.get("full_name") or "").strip(),
        aliases=[str(a) for a in (raw.get("aliases") or [])],
        level=str(raw.get("level") or "进阶").strip(),
        what=str(raw.get("what") or "").strip(),
        why=str(raw.get("why") or "").strip(),
        how=str(raw.get("how") or "").strip(),
        prerequisite=[str(p) for p in (raw.get("prerequisite") or [])],
        learn_path=[str(p) for p in (raw.get("learn_path") or [])],
        jd_phrases=[str(p) for p in (raw.get("jd_phrases") or [])],
        tags=[str(t) for t in (raw.get("tags") or [])],
    )


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_skills(domain: str | None = None) -> dict[str, Skill]:
    """加载技能词典。用户目录同名文件会覆盖内置版本（方便自己扩充/修正）。"""
    found: dict[str, Path] = {}
    for d in (BUILTIN_SKILLS_DIR, USER_SKILLS_DIR):
        if not d.exists():
            continue
        for p in sorted(d.glob("*.yaml")):
            found[p.stem] = p          # 用户目录后扫，同名覆盖

    skills: dict[str, Skill] = {}
    for stem, path in found.items():
        if domain and stem != domain:
            continue
        data = load_yaml(path)
        for i, raw in enumerate(data.get("skills") or []):
            s = _skill_from_dict(raw, f"{stem}-{i}")
            if s:
                skills[s.id] = s
    return skills


def list_skill_files() -> list[dict]:
    """列出可用的技能词典文件（给 CLI 展示）。"""
    out = []
    seen = set()
    for d in (BUILTIN_SKILLS_DIR, USER_SKILLS_DIR):
        if not d.exists():
            continue
        for p in sorted(d.glob("*.yaml")):
            data = load_yaml(p)
            is_user = d == USER_SKILLS_DIR
            if is_user and p.stem in seen:
                out = [o for o in out if o["domain"] != p.stem]   # 用户版覆盖内置版
            seen.add(p.stem)
            out.append({
                "domain": p.stem,
                "label": DOMAIN_LABELS.get(p.stem, data.get("label") or p.stem),
                "count": len(data.get("skills") or []),
                "source": "user" if is_user else "builtin",
                "path": str(p),
            })
    return sorted(out, key=lambda x: x["domain"])


# ---------------------------------------------------------------------------
#  JD
# ---------------------------------------------------------------------------

@dataclass
class JD:
    title: str
    company: str = ""
    text: str = ""
    url: str = ""
    location: str = ""
    salary: str = ""
    source: str = ""
    score: float = 0.0

    @classmethod
    def from_dict(cls, d: dict) -> "JD":
        def s(k: str) -> str:
            v = d.get(k)
            return "" if v is None else str(v).strip()
        return cls(
            title=s("title"), company=s("company"),
            text=s("jd") or s("text") or s("description"),
            url=s("url"), location=s("location"), salary=s("salary"),
            source=s("source"), score=float(d.get("score") or 0),
        )


def load_jds(path: Path) -> list[JD]:
    """读 JD 集合。兼容几种常见形态：

    - cn-job-radar 的 `data/scored/<date>.json`（顶层有 jobs）
    - 裸数组的 JD 列表
    - `{"jobs": [...]}`
    """
    if not path.exists():
        raise FileNotFoundError(f"找不到 JD 文件：{path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    records = raw if isinstance(raw, list) else (raw.get("jobs") or raw.get("items") or [])
    jds = []
    for r in records:
        if not isinstance(r, dict):
            continue
        jd = JD.from_dict(r)
        if jd.title or jd.text:
            jds.append(jd)
    return jds


def load_jd_dir(path: Path) -> list[JD]:
    """读一个目录下所有 json，合并。"""
    out: list[JD] = []
    for p in sorted(path.glob("*.json")):
        try:
            out.extend(load_jds(p))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  [!] 跳过 {p.name}：{exc}")
    return out


# ---------------------------------------------------------------------------
#  分析结果
# ---------------------------------------------------------------------------

@dataclass
class SkillHit:
    """某个技能在一批 JD 里的命中情况。"""
    skill: Skill
    count: int = 0                                  # 出现在多少个 JD 里
    jobs: list[str] = field(default_factory=list)   # 出现它的岗位名（去重）
    samples: list[str] = field(default_factory=list)  # JD 里的原文片段

    @property
    def coverage(self) -> float:
        return 0.0

    def to_dict(self, total: int) -> dict:
        d = self.skill.to_dict()
        d.update({
            "count": self.count,
            "coverage": round(self.count / total, 4) if total else 0.0,
            "jobs": self.jobs[:12],
            "samples": self.samples[:3],
        })
        return d


@dataclass
class Atlas:
    """一次分析的全部结果。"""
    total_jds: int = 0
    hits: list[SkillHit] = field(default_factory=list)
    unknown_terms: list[tuple[str, int]] = field(default_factory=list)  # 词典没收录但高频出现的词
    by_domain: dict[str, int] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    # ---- 分级 ----
    # 阈值是对**混合岗位池**标定的：一次分析里往往同时有技术岗、产品岗、
    # 投资岗，各岗位类型的技能差异大，所以单个技能的覆盖率不会很高。
    # 把 must 定在 35% 会只筛出一两个；25% 更实用。
    MUST = 0.25
    NICE_LO = 0.08
    RARE_MAX = 3          # 差异化技能至少出现这么多次，避免偶然命中

    def must_have(self, threshold: float | None = None) -> list[SkillHit]:
        t = self.MUST if threshold is None else threshold
        return [h for h in self.hits if self.total_jds and h.count / self.total_jds >= t]

    def nice_to_have(self, lo: float | None = None, hi: float | None = None) -> list[SkillHit]:
        lo = self.NICE_LO if lo is None else lo
        hi = self.MUST if hi is None else hi
        return [h for h in self.hits
                if self.total_jds and lo <= h.count / self.total_jds < hi]

    def rare(self, threshold: float | None = None) -> list[SkillHit]:
        t = self.NICE_LO if threshold is None else threshold
        return [h for h in self.hits
                if self.total_jds and h.count / self.total_jds < t and h.count >= self.RARE_MAX]

    def get(self, skill_id: str) -> SkillHit | None:
        return next((h for h in self.hits if h.skill.id == skill_id), None)

    def to_dict(self) -> dict:
        return {
            "total_jds": self.total_jds,
            "meta": self.meta,
            "by_domain": self.by_domain,
            "skills": [h.to_dict(self.total_jds) for h in self.hits],
            "unknown_terms": [{"term": t, "count": c} for t, c in self.unknown_terms[:60]],
        }
