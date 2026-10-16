"""本地学习平台。零额外依赖，只用标准库 http.server。

    atlas ui          # 打开 http://127.0.0.1:8899
"""
from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..core import Atlas, HOME, REPORT_DIR, load_jds, load_jd_dir
from ..extract import extract, gap_analysis
from ..report import write_report

STATIC = Path(__file__).resolve().parent / "static"

STATE: dict = {
    "atlas": None,       # 当前分析的 Atlas
    "title": "技能图谱",
    "source": "",        # 数据来源说明
    "have": [],          # 用户标记「已掌握」的技能
}


def _latest_json() -> dict | None:
    """读最近一次的报告 JSON。

    报告里只存了覆盖率，没有分级 id —— 服务重启后要在这里按阈值反推出来，
    否则前端拿不到 tiers，筛选按钮会全空。
    """
    files = sorted(REPORT_DIR.glob("*.json"))
    if not files:
        return None
    try:
        d = json.loads(files[-1].read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    skills = d.get("skills") or []
    if "tiers" not in d:
        d["tiers"] = {
            "must": [s["id"] for s in skills if s.get("coverage", 0) >= Atlas.MUST],
            "nice": [s["id"] for s in skills
                     if Atlas.NICE_LO <= s.get("coverage", 0) < Atlas.MUST],
            "rare": [s["id"] for s in skills
                     if s.get("coverage", 0) < Atlas.NICE_LO and s.get("count", 0) >= Atlas.RARE_MAX],
        }
    d.setdefault("have", [])
    return d


def _analyze(path_str: str, title: str = "技能图谱") -> dict:
    p = Path(path_str).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"找不到：{p}")
    jds = load_jd_dir(p) if p.is_dir() else load_jds(p)
    if not jds:
        raise ValueError(f"{p} 里没有解析出任何 JD")
    atlas = extract(jds)
    STATE["atlas"] = atlas
    STATE["title"] = title
    STATE["source"] = str(p)
    write_report(atlas, title=title, owner_have=STATE["have"])
    return _payload(atlas)


def _payload(atlas: Atlas) -> dict:
    d = atlas.to_dict()
    total = atlas.total_jds
    d.update({
        "title": STATE.get("title", "技能图谱"),
        "source": STATE.get("source", ""),
        "have": STATE.get("have", []),
        "tiers": {
            "must": [h.skill.id for h in atlas.must_have()],
            "nice": [h.skill.id for h in atlas.nice_to_have()],
            "rare": [h.skill.id for h in atlas.rare()],
        },
        "gap": gap_analysis(atlas, STATE.get("have", [])) if STATE.get("have") else None,
    })
    return d


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a) -> None:
        pass

    def _json(self, data, code: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def do_GET(self) -> None:  # noqa: N802
        p = self.path.split("?")[0]
        if p in ("/", "/index.html"):
            f = STATIC / "index.html"
            if not f.exists():
                return self.send_error(500, "index.html missing")
            body = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if p == "/api/atlas":
            if STATE["atlas"] is not None:
                return self._json(_payload(STATE["atlas"]))
            cached = _latest_json()
            if cached:
                return self._json(cached)
            return self._json({"empty": True, "home": str(HOME)})

        return self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        p = self.path.split("?")[0]
        data = self._body()

        if p == "/api/analyze":
            try:
                return self._json(_analyze(data.get("path") or "", data.get("title") or "技能图谱"))
            except (FileNotFoundError, ValueError) as exc:
                return self._json({"error": str(exc)}, 400)

        if p == "/api/have":
            have = data.get("have")
            if not isinstance(have, list):
                return self._json({"error": "have 必须是数组"}, 400)
            STATE["have"] = [str(x) for x in have]
            if STATE["atlas"] is not None:
                return self._json(_payload(STATE["atlas"]))
            return self._json({"ok": True})

        return self.send_error(404)


def serve(port: int = 8899, open_browser: bool = True) -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"\n  🧭 JD 技能图谱 · 学习平台")
    print(f"     {url}")
    print(f"     本地数据目录：{HOME}")
    if STATE["atlas"] is None and _latest_json() is None:
        print(f"     ⚠️ 还没有分析结果 —— 先跑 `atlas analyze <JD文件>`")
    print(f"     Ctrl+C 退出\n")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  已停止。")
    finally:
        httpd.server_close()
