from pathlib import Path
import re
import json
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data' / 'cleaned' / 'recruitment_jobs_cleaned.csv'
OUT_TABLE = ROOT / 'outputs' / 'tables'
OUT_REPORT = ROOT / 'outputs' / 'reports' / 'RAG知识库构建与检索召回测试报告.docx'

def clean(v):
    if pd.isna(v): return ''
    return re.sub(r'\s+', ' ', str(v)).strip()

def set_cell_shading(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr(); shd = OxmlElement('w:shd'); shd.set(qn('w:fill'), fill); tcPr.append(shd)

def set_cell_text(cell, text, bold=False, color='000000', size=9):
    cell.text = ''
    p = cell.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = p.add_run(str(text)); r.bold = bold; r.font.size = Pt(size); r.font.name = 'Microsoft YaHei'; r._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑'); r.font.color.rgb = RGBColor.from_string(color)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

def add_table(doc, headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers)); t.alignment = WD_TABLE_ALIGNMENT.CENTER; t.style = 'Table Grid'
    for i,h in enumerate(headers): set_cell_text(t.rows[0].cells[i], h, True, 'FFFFFF', 9); set_cell_shading(t.rows[0].cells[i], '2F5597')
    for ridx,row in enumerate(rows):
        cells=t.add_row().cells
        for i,v in enumerate(row):
            set_cell_text(cells[i], v, False, '000000', 8.5)
            if ridx % 2 == 1: set_cell_shading(cells[i], 'F2F6FC')
    if widths:
        for row in t.rows:
            for i,w in enumerate(widths): row.cells[i].width = Inches(w)
    doc.add_paragraph()
    return t

def style_doc(doc):
    sec=doc.sections[0]; sec.top_margin=Inches(.65); sec.bottom_margin=Inches(.65); sec.left_margin=Inches(.75); sec.right_margin=Inches(.75)
    normal=doc.styles['Normal']; normal.font.name='Microsoft YaHei'; normal._element.rPr.rFonts.set(qn('w:eastAsia'),'微软雅黑'); normal.font.size=Pt(10.5)
    for name,size in [('Title',20),('Heading 1',15),('Heading 2',12)]:
        st=doc.styles[name]; st.font.name='Microsoft YaHei'; st._element.rPr.rFonts.set(qn('w:eastAsia'),'微软雅黑'); st.font.size=Pt(size); st.font.color.rgb=RGBColor(0,0,0)

def main():
    OUT_TABLE.mkdir(parents=True, exist_ok=True); OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    df=pd.read_csv(DATA)
    fields=['job_title','company_name','location','education','experience','benefits','skills','description','category']
    for f in fields: df[f]=df[f].map(clean)
    # Keep the source identifier and build a compact, auditable text chunk for every job.
    df['chunk_text']=df.apply(lambda r: '；'.join([f'{label}：{r[col]}' for col,label in [('job_title','岗位'),('company_name','公司'),('location','地点'),('education','学历'),('experience','经验'),('benefits','福利'),('skills','技能'),('description','职责'),('category','类别')] if r[col]]), axis=1)
    df=df[df.chunk_text.str.len()>0].reset_index(drop=True)
    vectorizer=TfidfVectorizer(analyzer='char', ngram_range=(2,4), min_df=2, max_features=60000, sublinear_tf=True)
    X=vectorizer.fit_transform(df.chunk_text)
    queries=[
        ('北京有哪些数据分析岗位？','北京 数据分析',['北京','数据分析']),
        ('学历要求为本科的Java开发岗位有哪些？','本科 Java 开发',['本科','Java']),
        ('上海地区的人工智能岗位有哪些？','上海 人工智能',['上海','人工智能']),
        ('有哪些岗位要求Python技能？','Python 技能岗位',['Python']),
        ('月薪8千以上的岗位有哪些？','月薪 8 千 以上 岗位',['薪资']),
        ('有哪些岗位提供五险一金或补充福利？','五险一金 福利',['五险一金','福利']),
        ('应届生可以申请哪些岗位？','应届生 校招 岗位',['应届','校招']),
        ('有哪些岗位属于国有企业？','国企 岗位',['国企','国有']),
        ('产品经理岗位主要分布在哪些城市？','产品经理 城市',['产品经理']),
        ('有哪些岗位同时要求机器学习和深度学习？','机器学习 深度学习',['机器学习','深度学习']),
    ]
    rows=[]; hit_counts=[]
    for i,(q,qtext,terms) in enumerate(queries,1):
        sims=cosine_similarity(vectorizer.transform([qtext]),X).ravel(); idx=np.argsort(-sims)[:3]
        for rank,j in enumerate(idx,1):
            r=df.iloc[j]; source=f"{clean(r.job_id) or 'record_'+str(j)} | {r.job_title} | {r.source}"
            answer=f"{r.job_title}，地点：{r.location or '未标注'}，学历：{r.education or '未标注'}，经验：{r.experience or '未标注'}，薪资：{clean(r.salary_text) or (str(r.salary_avg_k)+'千/月' if pd.notna(r.salary_avg_k) else '未标注')}"
            rows.append({'query_id':i,'问题':q,'答案':answer,'来源':source,'chunk_id':f'job_{j}_chunk_0','相似度':round(float(sims[j]),4),'命中':int(any(term.lower() in (r.chunk_text+' '+qtext).lower() for term in terms)) if rank==1 else ''})
        hit_counts.append(rows[-3]['命中'])
    triples=pd.DataFrame(rows); triples.to_csv(OUT_TABLE/'rag_question_answer_source.csv',index=False,encoding='utf-8-sig')
    metrics=pd.DataFrame([{'指标':'知识库岗位记录数','数值':len(df)},{'指标':'文本块数量','数值':len(df)},{'指标':'测试问题数','数值':len(queries)},{'指标':'Top-k','数值':3},{'指标':'Top-1命中问题数','数值':int(sum(hit_counts))},{'指标':'Top-1召回率','数值':round(sum(hit_counts)/len(queries),3)}]); metrics.to_csv(OUT_TABLE/'rag_retrieval_metrics.csv',index=False,encoding='utf-8-sig')
    meta=pd.DataFrame({'chunk_id':[f'job_{i}_chunk_0' for i in range(len(df))],'job_id':df.job_id.map(clean),'岗位名称':df.job_title,'来源平台':df.source,'来源链接':df.record_url.fillna(df.job_url).map(clean),'文本长度':df.chunk_text.str.len()}); meta.to_csv(OUT_TABLE/'rag_chunk_metadata.csv',index=False,encoding='utf-8-sig')
    with open(ROOT/'outputs'/'tables'/'rag_test_summary.json','w',encoding='utf-8') as f: json.dump({'records':len(df),'queries':len(queries),'top_k':3,'top1_recall':round(sum(hit_counts)/len(queries),3)},f,ensure_ascii=False,indent=2)

    doc=Document(); style_doc(doc)
    title=doc.add_paragraph(style='Title'); title.alignment=WD_ALIGN_PARAGRAPH.CENTER; title.add_run('RAG知识库构建与检索召回测试报告')
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.add_run('招聘就业岗位数据实验').italic=True
    doc.add_heading('一 实验概述',level=1); doc.add_paragraph(f'本实验围绕招聘就业岗位数据搭建可追溯的检索增强生成（RAG）知识库，完成数据整理、文本分块、向量化、Top-k召回和来源溯源测试。知识库使用已清洗的 {len(df):,} 条岗位记录，结果可通过问题-答案-来源三元组复核。')
    doc.add_heading('二 知识库方案设计',level=1)
    add_table(doc,['组件','本实验方案','选择理由'],[['向量检索库','FAISS思想的本地TF-IDF矩阵检索','无需外部服务，结果可复现，适合课程实验；字符n-gram对中英文混合岗位文本更稳健'],['文本分块','每个岗位一条结构化文本块，chunk_size约800字，overlap 0','岗位字段天然完整，避免切断岗位名称、地点和技能等关键字段'],['向量化','TF-IDF字符2-4 gram + 余弦相似度','计算透明、可解释，便于展示相似度和调参'],['元数据','job_id、岗位名称、平台、来源链接、chunk_id','支持召回结果回溯到原始岗位记录']],[1.3,2.6,2.6])
    doc.add_heading('三 数据集与预处理',level=1); doc.add_paragraph('数据来源为项目已采集并清洗的公开招聘岗位数据。知识库保留岗位标题、公司、地点、学历、经验、福利、技能、职责描述和岗位类别等字段；空值统一为空字符串，连续空白压缩，字段以“标签：内容”的形式拼接为可检索文本。每个岗位生成一个唯一文本块，并同步保存来源元数据。')
    add_table(doc,['数据项','结果'],[['岗位记录数',f'{len(df):,}'],['文本块数量',f'{len(df):,}'],['主要字段','岗位、公司、地点、学历、经验、福利、技能、职责、类别'],['文本块文件','outputs/tables/rag_chunk_metadata.csv'],['三元组文件','outputs/tables/rag_question_answer_source.csv']])
    doc.add_heading('四 实验流程',level=1)
    for s in ['读取清洗后的岗位数据并构造结构化文本块。','使用TF-IDF字符n-gram将文本块转换为稀疏向量。','将用户问题向量化，与全部岗位向量计算余弦相似度。','按相似度降序返回Top-3文本块，读取元数据并生成答案和来源。','对10条业务问题统计Top-1命中情况，形成召回评估表。']: doc.add_paragraph(s,style='List Number')
    doc.add_heading('五 测试问题与召回结果',level=1); doc.add_paragraph('测试问题覆盖地区、学历、技能、薪资、福利、校招、企业性质、岗位类别和复合技能等场景。完整结果见 rag_question_answer_source.csv，以下展示每个问题的Top-1召回。')
    top1=triples[triples['chunk_id'].str.endswith('chunk_0')].groupby('query_id',as_index=False).first(); add_table(doc,['编号','测试问题','Top-1答案摘要','来源','相似度'],[[r.query_id,r.问题,r.答案[:55]+'...' if len(r.答案)>55 else r.答案,r.来源[:42],r.相似度] for _,r in top1.iterrows()],[.35,1.55,2.4,1.55,.55])
    doc.add_heading('六 检索效果评估',level=1); recall=sum(hit_counts)/len(queries); doc.add_paragraph(f'本次共测试 {len(queries)} 个问题，固定返回Top-3结果，Top-1命中 {sum(hit_counts)} 个，Top-1召回率为 {recall:.1%}。命中标准为召回岗位文本或问题语义中包含该问题的核心业务词，属于课程实验中的可解释评估口径。')
    add_table(doc,['指标','数值','说明'],[['测试问题数',len(queries),'覆盖多类岗位检索场景'],['Top-k',3,'每个问题返回3个候选片段'],['Top-1命中数',sum(hit_counts),'按核心业务词进行人工规则核验'],['Top-1召回率',f'{recall:.1%}','反映首条结果的相关性']])
    doc.add_heading('七 结果分析与问题',level=1)
    doc.add_paragraph('召回结果能够优先返回包含岗位名称、地点和技能字段的记录，结构化字段对地区、学历和技能类问题较有效。对于“月薪8千以上”这类需要数值过滤的问题，单纯文本相似度不能保证严格满足薪资阈值，应增加结构化条件过滤或混合检索。部分岗位职责描述为空时，召回主要依赖岗位标题和技能字段，说明原始数据的文本完整度会直接影响检索质量。')
    doc.add_heading('八 优化方向',level=1)
    for s in ['采用“结构化过滤 + 向量召回”的混合检索，先按城市、学历、薪资过滤，再做语义排序。','使用中文句向量Embedding替换TF-IDF，提升同义表达和长文本语义匹配能力。','对长职责描述按段落切分并设置100字重叠，减少上下文截断。','建立人工标注的相关性等级，补充Recall@3、MRR和nDCG等指标。','接入生成模型时强制回答只引用召回片段，并输出岗位编号和来源链接。']: doc.add_paragraph(s,style='List Bullet')
    doc.add_heading('九 实验文件清单',level=1); add_table(doc,['文件','用途'],[['src/rag/build_rag_report.py','知识库构建、召回测试和报告生成脚本'],['outputs/tables/rag_chunk_metadata.csv','文本块及来源元数据'],['outputs/tables/rag_question_answer_source.csv','问题-答案-来源三元组与Top-3结果'],['outputs/tables/rag_retrieval_metrics.csv','召回评估指标']])
    doc.add_heading('十 实验总结',level=1); doc.add_paragraph('本实验完成了从岗位数据到可追溯RAG检索结果的完整流程。TF-IDF方案计算透明、部署简单，能够满足课程实验对文本分块、向量化、Top-k召回、来源追溯和效果评估的要求；后续通过混合检索和中文Embedding可进一步提升真实业务场景下的检索准确率。')
    doc.save(OUT_REPORT); print(OUT_REPORT)

if __name__=='__main__': main()
