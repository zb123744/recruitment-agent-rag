from __future__ import annotations

import ast
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "data" / "cleaned" / "recruitment_jobs_cleaned.csv"
METRICS_PATH = ROOT / "outputs" / "tables" / "model_metrics.csv"
OUT_PATH = ROOT / "dashboard" / "dashboard-data.js"


def category_group(value: object) -> str:
    raw = "" if pd.isna(value) else str(value).strip()
    if not raw:
        return "未标注"
    try:
        labels = ast.literal_eval(raw) if raw.startswith("[") else [raw]
    except (ValueError, SyntaxError):
        labels = [raw]
    text = " ".join(str(item).lower() for item in labels)
    rules = [
        ("数据与算法", ["data-", "analytics", "machine-learning", "artificial-intelligence", "business-intelligence"]),
        ("技术研发", ["software", "developer", "engineer", "devops", "frontend", "backend", "full-stack", "mobile-", "cloud-"]),
        ("产品管理", ["product"]),
        ("设计创意", ["design", "ux-", "graphic", "creative"]),
        ("销售与业务", ["sales", "business-development", "account-", "marketing", "partnership"]),
        ("客户服务", ["customer", "client-", "support", "success"]),
        ("财务会计", ["finance", "financial", "accounting", "bookkeep"]),
        ("人力资源", ["human-resource", "hr-", "recruit", "talent", "people-"]),
        ("运营与管理", ["operation", "strategy", "management", "administrative", "assistant"]),
        ("教育服务", ["education", "academic", "student-service"]),
        ("医疗健康", ["clinical", "health", "pharma", "medical"]),
    ]
    for name, keywords in rules:
        if any(keyword in text for keyword in keywords):
            return name
    return "其他岗位"


def clean_text(value: object, fallback: str = "未说明") -> str:
    if pd.isna(value) or not str(value).strip():
        return fallback
    return str(value).strip()


def main() -> None:
    df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
    jobs = []
    for row in df.itertuples(index=False):
        location = clean_text(row.location, "未说明").split(",")[0].split("，")[0]
        source = "海外远程岗位" if str(row.source).lower() == "himalayas" else "国家大学生就业服务平台"
        jobs.append({
            "title": clean_text(row.job_title, "未命名岗位"),
            "company": clean_text(row.company_name),
            "source": source,
            "location": location,
            "education": clean_text(row.education),
            "category": category_group(row.category),
            "salary": None if pd.isna(row.salary_avg_k) else round(float(row.salary_avg_k), 2),
            "quality": round(float(row.quality_score), 2),
            "label": int(row.quality_label),
            "skills": clean_text(row.skills, ""),
        })

    metrics_df = pd.read_csv(METRICS_PATH)
    model_names = {"Logistic": "逻辑回归", "SVM": "支持向量机", "RandomForest": "随机森林", "XGBoost": "XGBoost"}
    metrics = [{
        "model": model_names.get(row.model, row.model),
        "accuracy": round(float(row.accuracy), 4),
        "precision": round(float(row.precision), 4),
        "recall": round(float(row.recall), 4),
        "f1": round(float(row.f1), 4),
        "auc": round(float(row.roc_auc), 4),
    } for row in metrics_df.itertuples(index=False)]

    payload = {"generatedAt": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), "jobs": jobs, "metrics": metrics}
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("window.DASHBOARD_DATA = " + json.dumps(payload, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(f"Generated {len(jobs)} jobs: {OUT_PATH}")


if __name__ == "__main__":
    main()
