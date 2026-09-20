"""Prompt 版本记录与模板。"""
from __future__ import annotations

PROMPT_VERSIONS = [
    {
        "version": "v1",
        "name": "基础问答",
        "goal": "根据岗位知识库回答用户问题",
        "template": (
            "你是招聘就业助手。请根据检索到的岗位信息回答用户问题。\n"
            "用户问题：{question}\n"
            "检索结果：{context}\n"
            "请给出简洁回答。"
        ),
        "changelog": "初版：仅做问答，不强制溯源。",
    },
    {
        "version": "v2",
        "name": "强制溯源问答",
        "goal": "回答必须附带问题-答案-来源三元组",
        "template": (
            "你是招聘就业助手。只能依据检索结果回答，并输出可溯源结构。\n"
            "用户问题：{question}\n"
            "检索结果：{context}\n"
            "请按以下格式输出：\n"
            "答案：...\n"
            "来源：岗位编号 | 岗位名称 | 平台\n"
            "若检索结果不足以回答，请明确说明。"
        ),
        "changelog": "增加强制溯源，要求输出问题-答案-来源。",
    },
    {
        "version": "v3",
        "name": "匹配解释增强",
        "goal": "结合人岗匹配结果给出缺失技能建议",
        "template": (
            "你是招聘就业助手。请综合岗位检索与人岗匹配结果给出可执行建议。\n"
            "用户问题：{question}\n"
            "检索结果：{context}\n"
            "匹配结果：{match_result}\n"
            "请输出：\n"
            "1) 结论\n"
            "2) 推荐岗位与来源\n"
            "3) 已匹配技能与缺失技能\n"
            "4) 下一步学习/投递建议"
        ),
        "changelog": "加入匹配解释与缺失技能建议，适合现场演示。",
    },
]


def get_prompt(version: str = "v3") -> dict:
    for item in PROMPT_VERSIONS:
        if item["version"] == version:
            return item
    return PROMPT_VERSIONS[-1]


def render_prompt(version: str, question: str, context: str, match_result: str = "") -> str:
    prompt = get_prompt(version)
    return prompt["template"].format(
        question=question,
        context=context or "无检索结果",
        match_result=match_result or "未执行匹配",
    )
