"""Agent 可调用工具：匹配、RAG、聚类、模型指标。"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("JOB_DATA_PATH", ROOT / "data" / "cleaned" / "recruitment_jobs_cleaned.csv"))
MODEL_METRICS = ROOT / "outputs" / "tables" / "model_metrics.csv"
CLUSTER_PROFILES = ROOT / "outputs" / "tables" / "cluster_profiles.csv"
CLUSTER_K = ROOT / "outputs" / "tables" / "clustering_k_selection.csv"
RAG_CACHE = Path(os.environ.get("RAG_CACHE_PATH", ROOT / "outputs" / "tables" / "rag_runtime_cache.pkl"))
RAG_MAX_FEATURES = int(os.environ.get("RAG_MAX_FEATURES", "20000"))

import sys
sys.path.insert(0, str(ROOT / "src"))
from matching.matching import match_resume  # noqa: E402


def _clean(v: Any) -> str:
    if pd.isna(v):
        return ""
    return re.sub(r"\s+", " ", str(v)).strip()


@lru_cache(maxsize=1)
def load_jobs() -> pd.DataFrame:
    df = pd.read_csv(DATA)
    fields = [
        "job_title", "company_name", "location", "education", "experience",
        "benefits", "skills", "description", "category", "source",
    ]
    for f in fields:
        if f in df.columns:
            df[f] = df[f].map(_clean)
    df["job_id"] = df["job_id"].map(_clean) if "job_id" in df.columns else [f"job_{i}" for i in range(len(df))]
    def _row_chunk(r):
        parts = []
        for col, label in [
            ("job_title", "岗位"), ("company_name", "公司"), ("location", "地点"),
            ("education", "学历"), ("experience", "经验"), ("benefits", "福利"),
            ("skills", "技能"), ("description", "职责"), ("category", "类别"),
        ]:
            if col in df.columns and r[col]:
                parts.append(f"{label}：{r[col]}")
        tokens = _clean(r["jieba_tokens"]) if "jieba_tokens" in df.columns else ""
        if tokens:
            parts.append(f"分词：{tokens}")
        return "；".join(parts)

    df["chunk_text"] = df.apply(_row_chunk, axis=1)
    return df.reset_index(drop=True)


@lru_cache(maxsize=1)
def load_rag_index():
    import pickle
    df = load_jobs()
    if RAG_CACHE.exists():
        with open(RAG_CACHE, "rb") as f:
            payload = pickle.load(f)
        if payload.get("n_rows") == len(df):
            return df, payload["vectorizer"], payload["matrix"]
    vectorizer = TfidfVectorizer(
        analyzer="char", ngram_range=(2, 3), min_df=3, max_features=RAG_MAX_FEATURES, sublinear_tf=True
    )
    matrix = vectorizer.fit_transform(df["chunk_text"].fillna(""))
    RAG_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(RAG_CACHE, "wb") as f:
        pickle.dump({"n_rows": len(df), "vectorizer": vectorizer, "matrix": matrix}, f)
    return df, vectorizer, matrix


TOOL_SPECS = [
    {
        "name": "match_resume_to_job",
        "description": "计算简历与岗位的人岗匹配分、匹配等级、已匹配/缺失技能。",
        "parameters": ["resume_text", "job_text", "resume_location", "job_location"],
    },
    {
        "name": "rag_search_jobs",
        "description": "在岗位知识库中做 Top-k 检索，返回答案片段和来源元数据。",
        "parameters": ["question", "top_k"],
    },
    {
        "name": "get_cluster_summary",
        "description": "返回 K-Means 聚类定K结果与四类岗位画像摘要。",
        "parameters": [],
    },
    {
        "name": "get_model_comparison",
        "description": "返回 Logistic/SVM/RandomForest/XGBoost 模型评估指标。",
        "parameters": [],
    },
]


def match_resume_to_job(
    resume_text: str,
    job_text: str,
    resume_location: str = "",
    job_location: str = "",
) -> dict[str, Any]:
    return match_resume(resume_text, job_text, resume_location, job_location)


def rag_search_jobs(question: str, top_k: int = 3) -> dict[str, Any]:
    df, vectorizer, matrix = load_rag_index()
    # 0 是明确的边界输入，不能用 ``top_k or 3`` 静默改成默认值。
    # 只有缺省值 None 才使用默认 Top-k=3，随后统一限制在 1 到 5。
    top_k = 3 if top_k is None else int(top_k)
    top_k = max(1, min(top_k, 5))
    sims = cosine_similarity(vectorizer.transform([question]), matrix).ravel()
    idx = np.argsort(-sims)[:top_k]
    hits = []
    for rank, j in enumerate(idx, 1):
        row = df.iloc[j]
        salary = _clean(row.get("salary_text", ""))
        if not salary and pd.notna(row.get("salary_avg_k")):
            salary = f"{row['salary_avg_k']}千/月"
        answer = (
            f"{row['job_title']}，地点：{row['location'] or '未标注'}，"
            f"学历：{row['education'] or '未标注'}，经验：{row['experience'] or '未标注'}，"
            f"薪资：{salary or '未标注'}"
        )
        source = f"{row['job_id']} | {row['job_title']} | {row['source']}"
        hits.append(
            {
                "rank": rank,
                "answer": answer,
                "source": source,
                "chunk_id": f"job_{j}_chunk_0",
                "similarity": round(float(sims[j]), 4),
                "job_title": row["job_title"],
                "location": row["location"],
                "url": _clean(row.get("record_url") or row.get("job_url") or ""),
            }
        )
    return {"question": question, "top_k": top_k, "hits": hits}


def get_cluster_summary() -> dict[str, Any]:
    profiles = pd.read_csv(CLUSTER_PROFILES)
    ksel = pd.read_csv(CLUSTER_K)
    best = ksel.sort_values("silhouette", ascending=False).iloc[0]
    naming = {
        1: "中等质量成长岗位",
        2: "低信息基础岗位",
        3: "高质量综合岗位",
        4: "高技能成长岗位",
    }
    rows = []
    for _, r in profiles.iterrows():
        cid = int(r["cluster"])
        rows.append(
            {
                "cluster": cid,
                "name": naming.get(cid, f"类别{cid}"),
                "count": int(r["岗位数"]),
                "avg_salary_k": float(r["平均月薪"]),
                "avg_skills": float(r["平均技能数"]),
                "avg_quality": float(r["平均质量分"]),
            }
        )
    return {
        "best_k": int(best["k"]),
        "best_silhouette": round(float(best["silhouette"]), 3),
        "pca_variance_explained": 0.696,
        "clusters": rows,
    }


def get_model_comparison() -> dict[str, Any]:
    df = pd.read_csv(MODEL_METRICS)
    rows = []
    for _, r in df.iterrows():
        rows.append(
            {
                "model": r["model"],
                "accuracy": round(float(r["accuracy"]) * 100, 2),
                "precision": round(float(r["precision"]) * 100, 2),
                "recall": round(float(r["recall"]) * 100, 2),
                "f1": round(float(r["f1"]) * 100, 2),
                "roc_auc": round(float(r["roc_auc"]) * 100, 2),
            }
        )
    return {
        "models": rows,
        "conclusion": "XGBoost 作主模型，逻辑回归作可解释基线，聚类用于岗位分群展示。",
    }


TOOL_IMPL = {
    "match_resume_to_job": match_resume_to_job,
    "rag_search_jobs": rag_search_jobs,
    "get_cluster_summary": get_cluster_summary,
    "get_model_comparison": get_model_comparison,
}


def call_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    if name not in TOOL_IMPL:
        return {"error": f"未知工具：{name}"}
    arguments = arguments or {}
    try:
        result = TOOL_IMPL[name](**arguments)
        return {"tool": name, "ok": True, "result": result}
    except TypeError as exc:
        return {"tool": name, "ok": False, "error": f"参数错误：{exc}"}
    except Exception as exc:  # noqa: BLE001
        return {"tool": name, "ok": False, "error": str(exc)}


def list_tools() -> list[dict[str, Any]]:
    return TOOL_SPECS


if __name__ == "__main__":
    print(json.dumps(get_model_comparison(), ensure_ascii=False, indent=2))
