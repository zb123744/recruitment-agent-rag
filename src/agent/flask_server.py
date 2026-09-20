"""Flask 版招聘就业演示服务。

保留与本地标准库服务相同的 API 路径，便于课程要求中的 Flask 封装、Docker
和云平台部署。文件上传接口只在内存中读取 PDF，不保存用户简历。
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

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
from matching.matching import extract_pdf  # noqa: E402

DASHBOARD_DIR = ROOT / "dashboard" / "agent"
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8765"))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024


@app.after_request
def cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.get("/")
@app.get("/index.html")
def index():
    return send_from_directory(DASHBOARD_DIR, "index.html")


@app.get("/<path:filename>")
def static_files(filename: str):
    if filename in {"styles.css", "app.js"}:
        return send_from_directory(DASHBOARD_DIR, filename)
    return jsonify(error="not found", path=f"/{filename}"), 404


@app.get("/api/health")
def health():
    return jsonify(ok=True, service="recruitment-agent-demo", framework="Flask", port=PORT)


@app.get("/api/tools")
def tools():
    return jsonify(tools=list_tools())


@app.get("/api/prompts")
def prompts():
    return jsonify(versions=PROMPT_VERSIONS)


@app.get("/api/cluster")
def cluster():
    return jsonify(get_cluster_summary())


@app.get("/api/models")
def models():
    return jsonify(get_model_comparison())


@app.post("/api/match")
def match():
    data = request.get_json(silent=True) or {}
    return jsonify(match_resume_to_job(
        resume_text=data.get("resume_text", ""),
        job_text=data.get("job_text", ""),
        resume_location=data.get("resume_location", ""),
        job_location=data.get("job_location", ""),
    ))


@app.post("/api/rag")
def rag():
    data = request.get_json(silent=True) or {}
    return jsonify(rag_search_jobs(data.get("question", ""), data.get("top_k", 3)))


@app.post("/api/agent")
def agent():
    data = request.get_json(silent=True) or {}
    return jsonify(run_agent(data.get("message", ""), data.get("prompt_version", "v3")))


@app.post("/api/resume/extract")
def resume_extract():
    """上传 PDF 简历并提取文本，供前端填入匹配框。"""
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify(error="请上传 PDF 简历"), 400
    if not uploaded.filename.lower().endswith(".pdf"):
        return jsonify(error="仅支持 PDF 文件"), 400
    try:
        text = extract_pdf(io.BytesIO(uploaded.read()))
    except Exception as exc:  # noqa: BLE001
        return jsonify(error=f"PDF 提取失败：{exc}"), 400
    if not text.strip():
        return jsonify(error="PDF 未提取到可读文本"), 422
    return jsonify(filename=uploaded.filename, text=text, characters=len(text))


@app.post("/api/recommend")
def recommend():
    """按简历文本返回匹配度最高的岗位，形成上传简历后的推荐环节。"""
    data = request.get_json(silent=True) or {}
    resume_text = str(data.get("resume_text", "")).strip()
    if not resume_text:
        return jsonify(error="resume_text 不能为空"), 400
    top_k = max(1, min(int(data.get("top_k", 5)), 10))
    df, vectorizer, matrix = load_rag_index()
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity

    sims = cosine_similarity(vectorizer.transform([resume_text]), matrix).ravel()
    candidates = np.argsort(-sims)[: max(top_k * 3, 10)]
    rows: list[dict[str, Any]] = []
    for j in candidates:
        row = df.iloc[int(j)]
        job_text = str(row.get("chunk_text", ""))
        score = match_resume_to_job(resume_text, job_text)
        rows.append({
            "rank_score": round(float(sims[j]) * 100, 2),
            "match_score": score["score"],
            "level": score["level"],
            "job_id": str(row.get("job_id", "")),
            "job_title": str(row.get("job_title", "")),
            "company_name": str(row.get("company_name", "")),
            "location": str(row.get("location", "")),
            "salary": str(row.get("salary_text", "")),
            "source": str(row.get("source", "")),
            "url": str(row.get("record_url", "") or row.get("job_url", "")),
            "missing_skills": score["missing_skills"],
        })
    rows.sort(key=lambda x: (x["match_score"], x["rank_score"]), reverse=True)
    return jsonify(resume_characters=len(resume_text), recommendations=rows[:top_k])


@app.errorhandler(413)
def too_large(_error):
    return jsonify(error="上传文件不能超过 8 MB"), 413


if __name__ == "__main__":
    print("正在加载岗位知识库索引，首次启动大约需要几秒...")
    load_rag_index()
    print(f"Flask 服务地址: http://{HOST}:{PORT}/")
    app.run(host=HOST, port=PORT, threaded=True)
