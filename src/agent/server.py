"""本周演示用本地 Agent 服务（标准库 HTTP，无需额外框架）。"""
from __future__ import annotations

import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from agent.prompts import PROMPT_VERSIONS  # noqa: E402
from agent.tools import (  # noqa: E402
    get_cluster_summary,
    get_model_comparison,
    list_tools,
    load_rag_index,
    match_resume_to_job,
    rag_search_jobs,
)
from agent.workflow import run_agent  # noqa: E402

DASHBOARD_DIR = ROOT / "dashboard" / "agent"
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8765"))


def _json(handler: BaseHTTPRequestHandler, code: int, payload: dict):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0") or 0)
    raw = handler.rfile.read(length) if length else b"{}"
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path in ("/", "/index.html"):
                return self._file(DASHBOARD_DIR / "index.html", "text/html; charset=utf-8")
            if path == "/styles.css":
                return self._file(DASHBOARD_DIR / "styles.css", "text/css; charset=utf-8")
            if path == "/app.js":
                return self._file(DASHBOARD_DIR / "app.js", "application/javascript; charset=utf-8")
            if path == "/api/health":
                return _json(self, 200, {"ok": True, "service": "recruitment-agent-demo", "port": PORT})
            if path == "/api/tools":
                return _json(self, 200, {"tools": list_tools()})
            if path == "/api/prompts":
                return _json(self, 200, {"versions": PROMPT_VERSIONS})
            if path == "/api/cluster":
                return _json(self, 200, get_cluster_summary())
            if path == "/api/models":
                return _json(self, 200, get_model_comparison())
            return _json(self, 404, {"error": "not found", "path": path})
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            return _json(self, 500, {"error": str(exc)})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            data = _read_json(self)
            if path == "/api/match":
                result = match_resume_to_job(
                    resume_text=data.get("resume_text", ""),
                    job_text=data.get("job_text", ""),
                    resume_location=data.get("resume_location", ""),
                    job_location=data.get("job_location", ""),
                )
                return _json(self, 200, result)
            if path == "/api/rag":
                result = rag_search_jobs(question=data.get("question", ""), top_k=data.get("top_k", 3))
                return _json(self, 200, result)
            if path == "/api/agent":
                result = run_agent(
                    message=data.get("message", ""),
                    prompt_version=data.get("prompt_version", "v3"),
                )
                return _json(self, 200, result)
            return _json(self, 404, {"error": "not found", "path": path})
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            return _json(self, 500, {"error": str(exc)})

    def _file(self, file_path: Path, content_type: str):
        if not file_path.exists():
            return _json(self, 404, {"error": f"missing file: {file_path.name}"})
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def main():
    # 保留本文件作为原启动入口，但统一交给 Flask 应用运行，
    # 这样 PDF 提取和岗位推荐等新增接口与云端入口保持一致。
    from agent.flask_server import app

    print("正在加载岗位知识库索引，首次启动大约需要几秒...")
    load_rag_index()
    print(f"Flask 服务地址: http://{HOST}:{PORT}/")
    app.run(host=HOST, port=PORT, threaded=True)


if __name__ == "__main__":
    main()
