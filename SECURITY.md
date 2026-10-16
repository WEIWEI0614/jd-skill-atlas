# 安全与数据处理 / Security & Data Handling

## 这个工具会碰到什么数据

| 数据 | 存在哪 | 会不会离开这台机器 |
|---|---|---|
| 岗位 JD 正文 | `~/.jd-skill-atlas/reports/` | **否** |
| 技能图谱分析结果 | 同上 | 否 |
| 你的学习进度（勾选「已掌握」） | 浏览器 localStorage | 否 |
| 技能词典 | 随包分发 / `~/.jd-skill-atlas/skills/` | 否（本来就是要公开的） |

**没有账号、没有遥测、没有任何上传通路。** 全程离线可用。

## 什么情况下你的信息会离开本机

只有一种：**你自己**把 `reports/*.json` 提交到公开仓库或发给别人。

JD 正文本身是公开信息，但**它可能暴露你在找什么岗位、在看哪些公司** ——
如果这属于隐私，分享前先脱敏。

## 报告的漏洞形态

如果你发现：

- 本工具**上传**了任何用户数据（不应该发生）
- 分析结果里混入了非公开信息
- 学习平台的本地服务被非本机访问（它只监听 `127.0.0.1`，不应该）
- 其他让你在使用本工具后处于风险中的问题

请开一个 [issue](https://github.com/WEIWEI0614/jd-skill-atlas/issues)，标题标注 `[security]`。

## 关于本地 Web 服务

`atlas ui` 启动的是一个**只监听 127.0.0.1** 的本地服务，端口默认 8899。
它不对外网开放、没有鉴权（因为不需要——外网访问不到）。

如果你的机器有多用户或你想在服务器上跑，注意：**同一台机器上的其他用户理论上可以访问这个端口**。

---

# Security & Data Handling (English)

**Nothing leaves your machine.** No account, no telemetry, no upload path. Fully offline-capable.

Your JDs, the analysis, and your learning progress all stay local. The only way data can leak
is if *you* publish `reports/*.json` — and while JDs are public information, they do reveal
*what roles you're targeting and which companies you're looking at*.

`atlas ui` binds to `127.0.0.1` only. Note that other users on the same machine could
theoretically reach that port.

Report issues tagged `[security]`.
