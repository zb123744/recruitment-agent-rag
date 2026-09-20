---
title: 招聘就业智能分析与人岗匹配系统
emoji: briefcase
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8765
---

# 招聘就业智能分析与人岗匹配系统

面向招聘就业场景的课程项目，集成岗位数据分析、人岗匹配、岗位聚类、评分模型、RAG 检索和 Agent 交互演示。

## 功能

- PDF 简历提取、简历文本匹配和岗位推荐
- TF-IDF + 余弦相似度人岗匹配
- 岗位知识库 Top-k 检索与来源溯源
- Agent 意图识别、Function Calling 和 Prompt 版本记录
- K-Means 聚类结果和岗位画像
- Logistic、SVM、RandomForest、XGBoost 指标对比

## 部署说明

本仓库同时支持 Hugging Face Spaces Docker 部署，不需要绑定银行卡。创建 Space 时选择 Docker，上传本仓库文件即可。Space 会按照 `Dockerfile` 启动 Flask 服务，端口为 8765。

部署完成后访问 Space 页面，健康检查路径为 `/api/health`。

## 本地启动

```powershell
pip install -r requirements-deploy.txt
python src/agent/server.py
```

浏览器打开 `http://127.0.0.1:8765/`。

## 接口

| 路径 | 方法 | 功能 |
| --- | --- | --- |
| `/api/health` | GET | 健康检查 |
| `/api/match` | POST | 人岗匹配 |
| `/api/recommend` | POST | 简历岗位推荐 |
| `/api/resume/extract` | POST | PDF 简历提取 |
| `/api/rag` | POST | RAG Top-k 检索 |
| `/api/agent` | POST | Agent 对话与工具调用 |
| `/api/cluster` | GET | 岗位聚类摘要 |
| `/api/models` | GET | 多模型对比 |

部署包使用 `data/deploy/recruitment_jobs_deploy.csv.gz`，用户上传的简历只在请求内存中处理，不保存到仓库。