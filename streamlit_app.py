"""Streamlit 免费云端演示入口。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("JOB_DATA_PATH", str(ROOT / "data" / "deploy" / "recruitment_jobs_deploy.csv.gz"))
os.environ.setdefault("RAG_CACHE_PATH", "/tmp/rag_runtime_cache.pkl")
os.environ.setdefault("RAG_MAX_FEATURES", "8000")
sys.path.insert(0, str(ROOT / "src"))

from agent.tools import get_cluster_summary, get_model_comparison, match_resume_to_job, rag_search_jobs  # noqa: E402
from agent.workflow import run_agent  # noqa: E402

st.set_page_config(page_title="招聘就业智能分析", page_icon="📊", layout="wide")
st.title("招聘就业智能分析与人岗匹配")
st.caption("Agent · RAG 检索 · 人岗匹配 · 岗位聚类 · 多模型对比")

tab_agent, tab_match, tab_rag, tab_analysis = st.tabs(["Agent 对话", "人岗匹配", "RAG 检索", "分析结果"])

with tab_agent:
    message = st.text_area("输入自然语言问题", value="请查询上海 Python 岗位", height=100)
    if st.button("运行 Agent", type="primary"):
        with st.spinner("正在调用工具并生成结果..."):
            result = run_agent(message)
        st.success(f"识别意图：{result['intent']}；Prompt：{result.get('prompt_version', 'v3')}")
        st.markdown(result["answer"].replace("\n", "  \n"))
        with st.expander("查看 Function Calling 工作流"):
            st.json({"steps": result["steps"], "tool_calls": result["tool_calls"], "triples": result["triples"]})

with tab_match:
    col1, col2 = st.columns(2)
    with col1:
        resume = st.text_area("简历文本", value="本科，3年经验，熟悉 Python、SQL、Pandas、机器学习，地点上海", height=180)
        resume_location = st.text_input("简历地点", value="上海")
    with col2:
        job = st.text_area("岗位文本", value="本科，要求3年经验，熟悉 Python、SQL、Pandas、Spark、机器学习，工作地点上海", height=180)
        job_location = st.text_input("岗位地点", value="上海")
    if st.button("计算匹配分"):
        result = match_resume_to_job(resume, job, resume_location, job_location)
        st.metric("综合匹配分", f"{result['score']} 分", result["level"])
        st.write("已匹配技能：", "、".join(result["skill_overlap"]) or "无")
        st.write("待补齐技能：", "、".join(result["missing_skills"]) or "无")
        st.json(result)

with tab_rag:
    question = st.text_input("检索问题", value="北京 Python 数据分析岗位的学历和薪资要求")
    top_k = st.slider("Top-k", min_value=1, max_value=5, value=3)
    if st.button("检索岗位"):
        with st.spinner("正在加载岗位知识库并检索..."):
            result = rag_search_jobs(question, top_k)
        for hit in result["hits"]:
            with st.container(border=True):
                st.markdown(f"**Top {hit['rank']}｜{hit['job_title']}**  相似度：{hit['similarity']}")
                st.write(hit["answer"])
                st.caption(f"来源：{hit['source']}")

with tab_analysis:
    st.subheader("岗位聚类")
    if st.button("加载聚类摘要"):
        st.json(get_cluster_summary())
    st.subheader("多模型评估")
    if st.button("加载模型对比"):
        st.json(get_model_comparison())
