"""简历与岗位的人岗匹配算法。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

SKILLS = ["Python", "Java", "C++", "SQL", "Excel", "Tableau", "Power BI", "Pandas", "NumPy", "Spark", "Hadoop", "机器学习", "深度学习", "TensorFlow", "PyTorch", "Docker", "Kubernetes", "Linux", "Git", "数据分析", "数据挖掘", "人工智能"]
EDU_LEVELS = {"不限": 0, "高中": 1, "大专": 2, "本科": 3, "硕士": 4, "博士": 5}


def extract_pdf(path: str | Path | object) -> str:
    from pypdf import PdfReader
    # 同时支持本地路径和 Flask 上传产生的二进制文件对象。
    reader = PdfReader(path if hasattr(path, "read") else str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _skills(text: str) -> list[str]:
    return [skill for skill in SKILLS if re.search(rf"(?i)(?<!\w){re.escape(skill)}(?!\w)", text)]


def _education(text: str) -> int:
    for name, level in sorted(EDU_LEVELS.items(), key=lambda x: -len(x[0])):
        if name in text:
            return level
    return 0


def _experience(text: str) -> int:
    matches = re.findall(r"(\d+)\s*[到至-]\s*(\d+)\s*年", text)
    if matches:
        return max(int(pair[1]) for pair in matches)
    matches = re.findall(r"(\d+)\s*年", text)
    return max((int(v) for v in matches), default=0)


def _dimension(actual: int, required: int) -> float:
    if required <= 0:
        return 1.0
    return min(actual / required, 1.0)


def match_resume(resume_text: str, job_text: str, resume_location: str = "", job_location: str = "") -> dict[str, Any]:
    resume_skills, job_skills = _skills(resume_text), _skills(job_text)
    corpus = [" ".join(resume_skills) or "无技能", " ".join(job_skills) or "无技能"]
    vectors = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b").fit_transform(corpus)
    skill_similarity = float(cosine_similarity(vectors[0], vectors[1])[0, 0])
    overlap = sorted(set(resume_skills) & set(job_skills))
    missing = sorted(set(job_skills) - set(resume_skills))
    education = _dimension(_education(resume_text), _education(job_text))
    experience = _dimension(_experience(resume_text), _experience(job_text))
    location = 1.0 if not job_location or not resume_location or job_location in resume_location or resume_location in job_location else 0.0
    responsibility = min(len(set(re.findall(r"[\u4e00-\u9fffA-Za-z]+", resume_text)) & set(re.findall(r"[\u4e00-\u9fffA-Za-z]+", job_text))) / 20, 1.0)
    score = 100 * (0.50 * skill_similarity + 0.20 * experience + 0.15 * education + 0.10 * location + 0.05 * responsibility)
    level = "高度匹配" if score >= 80 else "较为匹配" if score >= 60 else "部分匹配" if score >= 40 else "匹配度较低"
    return {"score": round(score, 2), "level": level, "skill_similarity": round(skill_similarity, 4), "skill_overlap": overlap, "missing_skills": missing, "experience_score": round(experience, 4), "education_score": round(education, 4), "location_score": location, "responsibility_score": round(responsibility, 4)}


if __name__ == "__main__":
    result = match_resume("本科，3年经验。熟悉 Python、SQL、Pandas、机器学习。", "本科，要求3年经验，熟悉Python、SQL、Pandas、Spark、机器学习。", "上海", "上海")
    print(result)
