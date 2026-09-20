"""Agent 工作流编排：意图识别 + Function Calling + Prompt 渲染。"""
from __future__ import annotations

import json
import re
from typing import Any

from .prompts import PROMPT_VERSIONS, get_prompt, render_prompt
from .tools import call_tool, list_tools


def detect_intent(message: str) -> str:
    text = message.lower()
    if any(k in message for k in ["匹配", "简历", "缺失技能", "适合我吗"]):
        return "match"
    if any(k in message for k in ["聚类", "分群", "画像", "k-means", "KMeans"]):
        return "cluster"
    if any(k in message for k in ["模型", "对比", "xgboost", "准确率", "f1", "roc"]):
        return "model"
    if any(k in message for k in ["岗位", "招聘", "薪资", "python", "java", "北京", "上海", "应届", "五险一金"]):
        return "rag"
    if "工具" in message or "function" in text:
        return "tools"
    return "rag"


def _extract_resume_job(message: str) -> tuple[str, str]:
    resume = ""
    job = ""
    m1 = re.search(r"简历[:：](.+?)(?:岗位[:：]|$)", message, flags=re.S)
    m2 = re.search(r"岗位[:：](.+)$", message, flags=re.S)
    if m1:
        resume = m1.group(1).strip()
    if m2:
        job = m2.group(1).strip()
    if not resume and not job:
        # fallback demo texts
        resume = "本科，3年经验。熟悉 Python、SQL、Pandas、机器学习。地点上海。"
        job = "本科，要求3年经验，熟悉Python、SQL、Pandas、Spark、机器学习。工作地点上海。"
    return resume, job


def run_agent(message: str, prompt_version: str = "v3") -> dict[str, Any]:
    intent = detect_intent(message)
    steps: list[dict[str, Any]] = []
    tool_results: list[dict[str, Any]] = []

    steps.append({"stage": "intent", "detail": f"识别意图为 {intent}"})

    if intent == "tools":
        tools = list_tools()
        steps.append({"stage": "function_calling", "detail": "返回可调用工具清单"})
        answer = "当前 Agent 已注册以下工具：\n" + "\n".join(
            f"- {t['name']}：{t['description']}" for t in tools
        )
        return {
            "intent": intent,
            "prompt_version": prompt_version,
            "steps": steps,
            "tool_calls": [],
            "tool_results": [],
            "prompt_preview": "",
            "answer": answer,
            "triples": [],
        }

    tool_calls: list[dict[str, Any]] = []

    if intent == "match":
        resume, job = _extract_resume_job(message)
        args = {
            "resume_text": resume,
            "job_text": job,
            "resume_location": "上海" if "上海" in resume else "",
            "job_location": "上海" if "上海" in job else "",
        }
        tool_calls.append({"name": "match_resume_to_job", "arguments": args})
        # also retrieve similar jobs for recommendation
        tool_calls.append({"name": "rag_search_jobs", "arguments": {"question": job or message, "top_k": 3}})
    elif intent == "cluster":
        tool_calls.append({"name": "get_cluster_summary", "arguments": {}})
    elif intent == "model":
        tool_calls.append({"name": "get_model_comparison", "arguments": {}})
    else:
        tool_calls.append({"name": "rag_search_jobs", "arguments": {"question": message, "top_k": 3}})

    for call in tool_calls:
        steps.append({
            "stage": "function_calling",
            "detail": f"调用工具 {call['name']}",
            "arguments": call["arguments"],
        })
        result = call_tool(call["name"], call["arguments"])
        tool_results.append(result)
        steps.append({
            "stage": "tool_result",
            "detail": f"工具 {call['name']} 返回成功" if result.get("ok") else f"工具失败：{result.get('error')}",
        })

    context_parts = []
    triples = []
    match_summary = ""

    for item in tool_results:
        if not item.get("ok"):
            continue
        name = item["tool"]
        result = item["result"]
        if name == "rag_search_jobs":
            for hit in result.get("hits", []):
                context_parts.append(f"[{hit['rank']}] {hit['answer']} | 来源：{hit['source']} | 相似度：{hit['similarity']}")
                triples.append({
                    "question": result.get("question", message),
                    "answer": hit["answer"],
                    "source": hit["source"],
                    "similarity": hit["similarity"],
                })
        elif name == "match_resume_to_job":
            match_summary = (
                f"匹配分 {result['score']}，等级 {result['level']}；"
                f"已匹配：{'、'.join(result['skill_overlap']) or '无'}；"
                f"缺失：{'、'.join(result['missing_skills']) or '无'}"
            )
            context_parts.append(match_summary)
        elif name == "get_cluster_summary":
            context_parts.append(
                f"最优K={result['best_k']}，轮廓系数={result['best_silhouette']}，PCA解释方差={result['pca_variance_explained']}"
            )
            for c in result["clusters"]:
                context_parts.append(
                    f"{c['name']}：{c['count']}条，均薪{c['avg_salary_k']}千，质量分{c['avg_quality']}"
                )
        elif name == "get_model_comparison":
            for m in result["models"]:
                context_parts.append(
                    f"{m['model']}：准确率{m['accuracy']}% / F1 {m['f1']}% / AUC {m['roc_auc']}%"
                )
            context_parts.append(result["conclusion"])

    context = "\n".join(context_parts)
    prompt_preview = render_prompt(prompt_version, message, context, match_summary)
    prompt_meta = get_prompt(prompt_version)
    steps.append({"stage": "prompt", "detail": f"使用 Prompt {prompt_meta['version']}（{prompt_meta['name']}）生成回答"})

    # 本地可演示的规则生成，不依赖外部大模型 API
    if intent == "match" and match_summary:
        answer = (
            f"结论：{match_summary}。\n"
            f"建议：优先补齐缺失技能，并结合下方检索岗位核对职责与薪资。\n"
            f"检索参考：\n" + "\n".join(context_parts[:4])
        )
    elif intent == "cluster":
        answer = "聚类摘要如下：\n" + "\n".join(context_parts)
    elif intent == "model":
        answer = "多模型对比结果：\n" + "\n".join(context_parts)
    else:
        if triples:
            top = triples[0]
            answer = (
                f"答案：{top['answer']}\n"
                f"来源：{top['source']}\n"
                f"说明：已按 Top-k 召回并完成溯源。完整候选见三元组列表。"
            )
        else:
            answer = "未检索到足够相关的岗位信息，请换个更具体的问题。"

    steps.append({"stage": "response", "detail": "完成工作流编排并输出可演示结果"})

    return {
        "intent": intent,
        "prompt_version": prompt_version,
        "prompt_name": prompt_meta["name"],
        "steps": steps,
        "tool_calls": tool_calls,
        "tool_results": tool_results,
        "prompt_preview": prompt_preview,
        "answer": answer,
        "triples": triples,
        "prompt_versions": PROMPT_VERSIONS,
    }
