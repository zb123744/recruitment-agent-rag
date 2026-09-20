"""招聘就业分析系统 API 三路径测试。

运行前先启动 src/agent/server.py。脚本只依赖 Python 标准库，结果写入
outputs/tables/api_test_results.csv 和 outputs/tables/api_test_summary.json。
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from urllib import error, request

ROOT = Path(__file__).resolve().parents[2]
BASE = "http://127.0.0.1:8765"
OUT = ROOT / "outputs" / "tables"


def call(method: str, path: str, payload=None, raw_body: bytes | None = None):
    body = raw_body
    headers = {}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(BASE + path, data=body, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            elapsed = (time.perf_counter() - started) * 1000
            try:
                parsed = json.loads(data.decode("utf-8"))
            except json.JSONDecodeError:
                parsed = {"raw": data.decode("utf-8", errors="replace")}
            return resp.status, parsed, round(elapsed, 2), ""
    except error.HTTPError as exc:
        data = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            parsed = {"raw": data}
        return exc.code, parsed, round((time.perf_counter() - started) * 1000, 2), "HTTPError"
    except Exception as exc:  # noqa: BLE001
        return None, {}, round((time.perf_counter() - started) * 1000, 2), str(exc)


CASES = [
    {
        "id": "N01",
        "path": "/api/health",
        "method": "GET",
        "kind": "正常",
        "expected": lambda s, d: s == 200 and d.get("ok") is True,
    },
    {
        "id": "N02",
        "path": "/api/match",
        "method": "POST",
        "payload": {
            "resume_text": "本科，3年经验，熟悉 Python、SQL、Pandas、机器学习，地点上海。",
            "job_text": "本科，要求3年经验，熟悉 Python、SQL、Pandas、Spark、机器学习，工作地点上海。",
            "resume_location": "上海",
            "job_location": "上海",
        },
        "kind": "正常",
        "expected": lambda s, d: s == 200 and 0 <= d.get("score", -1) <= 100 and "missing_skills" in d,
    },
    {
        "id": "N03",
        "path": "/api/rag",
        "method": "POST",
        "payload": {"question": "北京有哪些数据分析岗位？", "top_k": 3},
        "kind": "正常",
        "expected": lambda s, d: s == 200 and len(d.get("hits", [])) == 3,
    },
    {
        "id": "B01",
        "path": "/api/match",
        "method": "POST",
        "payload": {"resume_text": "", "job_text": "", "resume_location": "", "job_location": ""},
        "kind": "边界",
        "expected": lambda s, d: s == 200 and 0 <= d.get("score", -1) <= 100,
    },
    {
        "id": "B02",
        "path": "/api/rag",
        "method": "POST",
        "payload": {"question": "Python 岗位", "top_k": 0},
        "kind": "边界",
        "expected": lambda s, d: s == 200 and d.get("top_k") == 1 and len(d.get("hits", [])) == 1,
    },
    {
        "id": "B03",
        "path": "/api/rag",
        "method": "POST",
        "payload": {"question": "Python 岗位", "top_k": 99},
        "kind": "边界",
        "expected": lambda s, d: s == 200 and d.get("top_k") == 5 and len(d.get("hits", [])) == 5,
    },
    {
        "id": "B04",
        "path": "/api/agent",
        "method": "POST",
        "payload": {"message": ""},
        "kind": "边界",
        "expected": lambda s, d: s == 200 and "answer" in d,
    },
    {
        "id": "E01",
        "path": "/api/not-found",
        "method": "GET",
        "kind": "异常",
        "expected": lambda s, d: s == 404 and d.get("error") == "not found",
    },
    {
        "id": "E02",
        "path": "/api/match",
        "method": "POST",
        "raw_body": b"{bad-json",
        "kind": "异常",
        "expected": lambda s, d: s == 500 and "error" in d,
    },
    {
        "id": "E03",
        "path": "/api/rag",
        "method": "POST",
        "payload": {"top_k": 3},
        "kind": "异常",
        "expected": lambda s, d: s == 200 and "hits" in d,
    },
    {
        "id": "E04",
        "path": "/api/agent",
        "method": "POST",
        "payload": {"message": "请调用一个不存在的工具"},
        "kind": "异常",
        "expected": lambda s, d: s == 200 and "answer" in d,
    },
]


def main() -> None:
    rows = []
    for case in CASES:
        status, data, elapsed, err = call(
            case["method"], case["path"], case.get("payload"), case.get("raw_body")
        )
        try:
            passed = bool(case["expected"](status, data))
        except Exception:
            passed = False
        rows.append({
            "id": case["id"],
            "kind": case["kind"],
            "method": case["method"],
            "path": case["path"],
            "status": status if status is not None else "连接失败",
            "elapsed_ms": elapsed,
            "result": "通过" if passed else "失败",
            "error": err,
        })
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "api_test_results.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "total": len(rows),
        "passed": sum(r["result"] == "通过" for r in rows),
        "failed": sum(r["result"] == "失败" for r in rows),
        "pass_rate": round(sum(r["result"] == "通过" for r in rows) / len(rows), 4),
        "avg_elapsed_ms": round(sum(float(r["elapsed_ms"]) for r in rows) / len(rows), 2),
        "max_elapsed_ms": max(float(r["elapsed_ms"]) for r in rows),
        "by_kind": {
            kind: {
                "total": sum(r["kind"] == kind for r in rows),
                "passed": sum(r["kind"] == kind and r["result"] == "通过" for r in rows),
            }
            for kind in ("正常", "边界", "异常")
        },
    }
    (OUT / "api_test_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
