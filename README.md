# 招聘就业智能分析与人岗匹配系统

面向招聘就业场景的课程项目，集成岗位数据分析、人岗匹配、岗位聚类、评分模型、RAG 检索和 Agent 交互演示。

## 功能

- PDF 简历提取、简历文本匹配和岗位推荐
- TF-IDF + 余弦相似度人岗匹配
- 岗位知识库 Top-k 检索与来源溯源
- Agent 意图识别、Function Calling 和 Prompt 版本记录
- K-Means 聚类结果和岗位画像
- Logistic、SVM、RandomForest、XGBoost 指标对比

## Render 部署

仓库根目录提供 `render.yaml`。在 Render 中选择 **New → Blueprint**，连接本仓库并 Apply，即可创建服务。

部署完成后访问：

- 首页：`https://你的服务名.onrender.com/`
- 健康检查：`https://你的服务名.onrender.com/api/health`

免费实例首次启动会构建岗位 TF-IDF 检索索引，第一次请求可能需要等待几十秒。

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