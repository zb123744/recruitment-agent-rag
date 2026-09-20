"""招聘岗位数据清洗与特征工程。"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import jieba
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data" / "raw" / "recruitment_jobs_merged.csv"
OUTPUT = ROOT / "data" / "cleaned" / "recruitment_jobs_cleaned.csv"

SKILLS = [
    "Python", "Java", "C++", "Go", "JavaScript", "TypeScript", "SQL", "MySQL", "PostgreSQL", "Oracle",
    "Excel", "Power BI", "Tableau", "Hadoop", "Spark", "Flink", "Kafka", "Pandas", "NumPy", "机器学习",
    "深度学习", "人工智能", "TensorFlow", "PyTorch", "Docker", "Kubernetes", "Linux", "Git", "AWS", "Azure",
    "产品设计", "项目管理", "数据分析", "数据挖掘", "算法", "英语", "销售", "运营", "财务", "招聘",
]


def text(value: object) -> str:
    raw = "" if pd.isna(value) else str(value)
    if "<" in raw and ">" in raw:
        raw = BeautifulSoup(raw, "lxml").get_text(" ")
    return re.sub(r"\s+", " ", raw).strip()


def number(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def skills_for(row: pd.Series) -> str:
    corpus = " ".join(text(row.get(c, "")) for c in ["job_title", "major", "category", "description", "job_type"])
    found = [skill for skill in SKILLS if re.search(rf"(?i)(?<!\w){re.escape(skill)}(?!\w)", corpus)]
    return ",".join(found)


def jieba_tokens(row: pd.Series) -> str:
    """对岗位文本做中文分词，保留有意义的中文/英文词项。"""
    corpus = " ".join(text(row.get(c, "")) for c in ["job_title", "major", "category", "description", "job_type"])
    tokens = []
    for token in jieba.lcut(corpus, cut_all=False):
        token = token.strip()
        if len(token) >= 2 and re.search(r"[\u4e00-\u9fffA-Za-z0-9]", token):
            tokens.append(token)
    return " ".join(tokens)


def main() -> None:
    df = pd.read_csv(INPUT)
    before = len(df)
    for col in df.columns:
        df[col] = df[col].map(text)
    df["record_url"] = df["source_url"].where(df["source_url"].ne(""), df["job_url"])
    df["record_url"] = df["record_url"].fillna("")
    df = df.drop_duplicates(subset=["source", "record_url"], keep="first")
    df = df[df["job_title"].str.len() >= 2].copy()
    df["salary_min_k"] = df["salary_min_k"].map(number)
    df["salary_max_k"] = df["salary_max_k"].map(number)
    df["salary_avg_k"] = df[["salary_min_k", "salary_max_k"]].mean(axis=1)
    df["salary_known"] = df["salary_avg_k"].notna().astype(int)
    df["description_length"] = df["description"].str.len()
    df["benefit_count"] = df["benefits"].apply(lambda x: len([v for v in re.split(r"[,，、|]", x) if v.strip()]))
    df["skills"] = df.apply(skills_for, axis=1)
    df["skill_count"] = df["skills"].apply(lambda x: len([v for v in x.split(",") if v]))
    df["jieba_tokens"] = df.apply(jieba_tokens, axis=1)
    df["is_domestic"] = (df["source"] != "himalayas").astype(int)
    df["quality_score"] = (
        df["salary_avg_k"].fillna(df["salary_avg_k"].median()).rank(pct=True) * 45
        + df["benefit_count"].rank(pct=True) * 20
        + df["description_length"].rank(pct=True) * 20
        + df["skill_count"].rank(pct=True) * 15
    ).round(2)
    df["quality_label"] = (df["quality_score"] >= df["quality_score"].median()).astype(int)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT, index=False, encoding="utf-8-sig")
    print(f"清洗前：{before}；清洗后：{len(df)}；输出：{OUTPUT}")
    print(df["source"].value_counts().to_dict())


if __name__ == "__main__":
    main()
