from pathlib import Path
import shutil
import pandas as pd
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = Path(r"D:\行业大数据分析实践_RAG知识库构建与检索召回测试实验_RAG知识库构建与检索召回测试实验报告模板.docx")
OUT = ROOT / "outputs" / "reports" / "RAG知识库构建与检索召回测试实验报告_模板填写版.docx"
TRIPLES = ROOT / "outputs" / "tables" / "rag_question_answer_source.csv"

QUERIES = [
    "北京有哪些数据分析岗位？", "学历要求为本科的Java开发岗位有哪些？", "上海地区的人工智能岗位有哪些？",
    "有哪些岗位要求Python技能？", "月薪8千以上的岗位有哪些？", "有哪些岗位提供五险一金或补充福利？",
    "应届生可以申请哪些岗位？", "有哪些岗位属于国有企业？", "产品经理岗位主要分布在哪些城市？",
    "有哪些岗位同时要求机器学习和深度学习？",
]
# Manual review: the returned text itself must satisfy the business condition;
# query-word overlap alone is not counted as a hit.
HITS = [0, 1, 0, 1, 0, 1, 1, 0, 1, 0]

def set_text(p, text):
    p.text = str(text)
    for r in p.runs:
        r.font.name = "Microsoft YaHei"
        r.font.size = Pt(10.5)

def cell_text(cell, text):
    cell.text = str(text)
    for p in cell.paragraphs:
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for r in p.runs:
            r.font.name = "Microsoft YaHei"
            r.font.size = Pt(9)

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TEMPLATE, OUT)
    doc = Document(OUT)
    p = doc.paragraphs
    # Basic information (identity left blank deliberately)
    set_text(p[5], "实验日期：2026年9月13日")
    set_text(p[6], "实验环境：Python 3.12、scikit-learn、Pandas；FAISS式本地稀疏向量索引；Windows 11")
    set_text(p[36], "数据总量：11,821条岗位数据")
    set_text(p[38], "数据预处理操作：去重；空值统一为空字符串；连续空白压缩；去除无效字符；岗位字段标准化；将岗位、公司、地点、学历、经验、福利、技能、职责、类别拼接为结构化文本块；保留job_id、岗位名称、来源平台、来源链接和chunk_id等溯源元数据。")
    # Parameter table
    t0 = doc.tables[0]
    vals = [
        "FAISS式本地向量索引（稀疏矩阵检索）",
        "TF-IDF字符2-4 gram（余弦相似度）",
        "约800字；本实验按每个岗位生成1个结构化文本块",
        "0（岗位字段保持完整，不重叠切分）",
        "3",
    ]
    for i, v in enumerate(vals, 1): cell_text(t0.rows[i].cells[1], v)
    # Test questions paragraphs
    for i, q in enumerate(QUERIES, 51): set_text(p[i], f"{i-50}. {q}")
    # Triple result table: retain header, replace sample rows, add rows to 10
    df = pd.read_csv(TRIPLES, encoding="utf-8-sig")
    top1 = df.sort_values(["query_id", "相似度"], ascending=[True, False]).groupby("query_id", as_index=False).first()
    t1 = doc.tables[1]
    while len(t1.rows) < 11: t1.add_row()
    for i, (_, r) in enumerate(top1.sort_values("query_id").iterrows(), 1):
        answer = str(r["答案"])
        source = str(r["来源"])
        vals = [i, r["问题"], answer, source, "是" if HITS[i-1] else "否"]
        for j, v in enumerate(vals): cell_text(t1.rows[i].cells[j], v)
    # Metrics and narrative
    set_text(p[64], "总测试问题数：10条")
    set_text(p[65], "召回命中数量：5条")
    set_text(p[66], "召回命中率：50%")
    set_text(p[70], "1. 整体实验效果总结：知识库包含11,821条岗位记录并生成11,821个结构化文本块。固定Top-k=3进行10条测试，按召回文本是否真正满足问题核心条件人工复核，Top-1命中5条，命中率50%。结果表明，岗位名称、技能和经验类查询较容易召回；地域和薪资阈值类查询仅靠文本相似度容易出现误召回。")
    set_text(p[71], "2. 召回成功案例分析：Python技能问题召回了包含Java、Python和爬虫技能的全栈岗位；福利问题召回了标题直接包含“五险一金”的岗位；产品经理问题召回了多个同名岗位。成功原因是核心词出现在岗位标题或结构化字段中，字符n-gram能够保持中英文混合词的匹配能力。")
    set_text(p[72], "3. 召回失败案例分析：北京数据分析问题返回了安徽岗位，上海人工智能问题返回了浙江岗位，说明地域约束未被严格执行；月薪8千以上问题返回了无薪资标注的外文岗位，说明数值阈值不能由相似度代替；国企问题也未召回可验证的企业性质。")
    set_text(p[73], "4. 核心实验洞察：每岗位一块避免了岗位名称、地点和技能被切散，但对长职责文本的细粒度语义不足；TF-IDF透明、速度快、便于复现，但同义词和条件约束能力有限；本地索引适合课程原型，生产场景应采用向量检索与结构化过滤混合方案。")
    set_text(p[75], "1. 实验过程遇到的问题：部分公开岗位缺少地点、薪资、福利或职责字段；不同平台字段格式不一致；单一文本相似度对“北京”“上海”“8千以上”等硬条件约束不足；FAISS原生索引不负责业务元数据，因此采用索引位置与CSV元数据手动映射。")
    set_text(p[76], "2. 针对性优化方案：先做城市、学历、薪资和企业性质的结构化过滤，再进行向量排序；将TF-IDF替换为中文句向量Embedding并保留关键词检索；对长职责按段落切分并设置适度重叠；补充人工相关性标注，计算Recall@3、MRR和nDCG；在生成回答中强制输出岗位编号和来源链接。")
    set_text(p[78], "本实验完成了岗位数据清洗、结构化文本块构建、TF-IDF向量化、Top-k召回、元数据溯源和问题—答案—来源三元组整理。实验掌握了RAG知识库的基本链路，也认识到文本相似度不等于业务条件满足。后续通过混合检索、中文Embedding和更完整的人工评估，可提升真实招聘场景的可靠性。")
    set_text(p[80], "1. 完整可运行Python实验代码：src/rag/build_rag_report.py、src/rag/fill_rag_template.py")
    set_text(p[81], "2. 「问题—答案—来源」三元组CSV数据集：outputs/tables/rag_question_answer_source.csv；文本块元数据：outputs/tables/rag_chunk_metadata.csv；评估指标：outputs/tables/rag_retrieval_metrics.csv")
    doc.save(OUT)
    print(OUT)

if __name__ == "__main__": main()
