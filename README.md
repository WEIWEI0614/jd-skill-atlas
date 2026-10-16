<div align="center">

# 🧭 jd-skill-atlas

**Turn a pile of job descriptions into a ranked skill map — then explain every term.**
Scans all your target JDs, extracts what the industry actually asks for, groups it into
must-have / nice-to-have / differentiator, and builds an offline study platform with learning paths.

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![No LLM required](https://img.shields.io/badge/LLM-not%20required-success)]()

[English](README.md) · [简体中文](README.zh-CN.md)

</div>

---

## The problem

You scan 300 job postings and get a list. Now what?

The postings are full of terms you half-recognise — *VLA*, *Sim2Real*, *KV Cache*, *DPI*, *返投*.
You can't tell which ones are **entry tickets** (everyone requires them) and which are
**differentiators** (rare, but decisive). And even when you know a term, you don't know
what to learn first.

Keyword extractors don't solve this. They give you a word cloud.

**jd-skill-atlas gives you a curriculum.**

---

## What it does

```
   380 JDs  ──▶  extract  ──▶  rank by coverage  ──▶  explain  ──▶  study platform
                    │                                    │
              matched against a                    every term gets:
              curated skill dictionary              what / why / how
              (93 skills, 7 domains)                + prerequisites
                                                    + learning steps
                                                    + real JD evidence
```

| Output | What it is |
|---|---|
| 🔴 **Must-have** | ≥25% of postings require it. These are entry tickets — without them you're filtered out. |
| 🟡 **Nice-to-have** | 8–25%. Moves you up the shortlist. |
| 🟢 **Differentiator** | <8%, but rare enough that having it stands out. |
| 📖 **Glossary** | Every term explained in three layers: what it is → why this role needs it → how it actually works (including the common traps). |
| 🗺 **Learning path** | Topologically sorted by prerequisites. Python → LLM → Agent, not alphabetically. |
| ❓ **Dictionary gaps** | High-frequency terms the dictionary doesn't cover yet — a to-do list for improving accuracy. |

---

## Quick start

```bash
pip install jd-skill-atlas      # or: pip install -e .

# point it at your JD pile (cn-job-radar output works out of the box)
atlas analyze ~/.cn-job-radar/data/scored

atlas ui                        # open the study platform at 127.0.0.1:8899
```

![study platform](docs/screenshot.png)

<sub>Everything is colour-coded by tier. Click a skill to expand the full explanation; tick it off as you learn it and the progress bar tracks your coverage of the must-haves.</sub>

**Look up a single term:**

```bash
$ atlas explain VLA

  VLA（视觉-语言-动作模型）
  ══════════════════════════════════════════════════
  领域：机器人 / 具身智能   熟练度：进阶

  【一句话】
  把「看到的画面 + 听到的指令」直接映射成「机器人该做的动作」的端到端模型。

  【为什么这个岗位要它】
  这是当前具身智能最核心的技术路线。过去机器人靠人工写规则（看到红色就抓），
  现在靠一个大模型直接从视觉和语言生成动作……
  【怎么学】
   1. 先搞懂 Transformer 和注意力机制 —— VLA 的骨架就是它
   2. 读 RT-1 / RT-2 / OpenVLA 三篇论文，重点理解「动作离散化」
   …
```

---

## Why no LLM

Every other skill-gap tool calls an LLM per job description. That means an API key, a
per-run cost, non-deterministic output you can't diff, and your job history leaving your machine.

jd-skill-atlas does extraction with a **curated dictionary + rules**:

- **Zero cost, zero API key** — runs on a plane
- **Deterministic** — same JDs in, same result out. You can diff two runs.
- **Local** — your job search never leaves your machine
- **Fast** — 380 JDs in well under a second

The trade-off is honesty about coverage: the dictionary knows 93 skills, not everything.
That's what the **dictionary-gap list** is for — it tells you exactly which high-frequency
terms aren't covered yet, so you extend the dictionary instead of guessing. An LLM is
optional for filling those gaps; it is never on the critical path.

---

## The skill dictionary

93 skills across 7 domains, and this is the part worth contributing to.

| File | Domain | Examples |
|---|---|---|
| `robotics.yaml` | 机器人 · 具身智能 | VLA, SLAM, 运控, 灵巧手, Sim2Real, 力控, 世界模型 |
| `ai.yaml` | 人工智能 | Transformer, MoE, KV Cache, RLHF, RAG, Agent, 推理优化 |
| `investment.yaml` | 投资 · 金融 | IRR, DPI/TVPI, 尽调, Term Sheet, 募投管退, 引导基金 |
| `tools.yaml` | 工具 · 工程 | Python, PyTorch, CUDA, ROS, Docker, Git, SQL |
| `common.yaml` | 通用能力 | 项目管理, 需求分析, 商业分析, 行业研究 |

Every entry requires three layers — a definition alone is not accepted:

```yaml
- id: vla
  name: VLA
  zh: 视觉-语言-动作模型
  what: 把「看到的画面 + 听到的指令」直接映射成「机器人该做的动作」的端到端模型。
  why:  |
    这是当前具身智能最核心的技术路线…… JD 里出现 VLA，
    基本意味着这家公司在做通用机器人的「大脑」，而不是专用设备。
  how:  |
    典型 VLA 把三块拼起来：视觉编码器、语言模型、动作头。
    三个常见坑：动作空间不统一、真机数据太少、推理延迟跟不上控制频率。
  prerequisite: [transformer, imitation-learning]
  learn_path:
    - 先搞懂 Transformer 和注意力机制
    - 读 RT-1 / RT-2 / OpenVLA，重点理解「动作离散化」
    - 跑通一个开源 VLA
```

Override or extend any file by dropping a same-named YAML into `~/.jd-skill-atlas/skills/`.

---

## Commands

```bash
atlas analyze <文件或目录> [--title T] [--have "Python,SQL"]
atlas ui [--port 8899]          # 学习平台
atlas explain <技能>            # 查一个术语（中英模糊匹配）
atlas skills [--domain ai]      # 列出词典
atlas path --jd <目录>          # 按前置依赖排序的学习路径
```

### Input format

Anything shaped like a job posting works. [`cn-job-radar`](https://github.com/WEIWEI0614/cn-job-radar)
output is supported out of the box:

```json
[{"title": "具身智能产品经理", "company": "某公司",
  "location": "北京", "url": "https://…",
  "jd": "岗位职责…任职要求…"}]
```

A single file, a directory of files, or a bare array — all accepted.

---

## How the ranking works

Coverage = (number of JDs mentioning the skill) / (total JDs analysed).

Thresholds are calibrated for a **mixed** posting pool. If you scan robotics engineer roles
plus investment roles together, no single skill will hit 80% — the roles are too different.
25% is what actually separates the tickets from the rest in practice. Change `Atlas.MUST`
in `core.py` if your pool is homogeneous.

---

## Contributing

**The highest-value contribution is a dictionary entry.** Terms move fast in AI and robotics,
and the dictionary is what makes this tool useful rather than a word cloud.

Also welcome: new domain dictionaries, coverage improvements, and bug reports from
real job hunts.

---

## Privacy

Everything runs locally. Your JDs, your skill list, and your progress marks never leave
your machine. There is no account, no telemetry, and no upload path.

See [SECURITY.md](SECURITY.md).

## License

MIT — see [LICENSE](LICENSE).
