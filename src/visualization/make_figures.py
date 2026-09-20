from __future__ import annotations
import ast
import re
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager
import seaborn as sns

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data' / 'cleaned' / 'recruitment_jobs_cleaned.csv'
OUT = ROOT / 'outputs' / 'figures'
OUT.mkdir(parents=True, exist_ok=True)
df = pd.read_csv(DATA, encoding='utf-8-sig')
df['location_main'] = df['location'].fillna('').astype(str).str.split(',').str[0].str.split('，').str[0]

def category_group(value):
    """将海外来源的英文细分标签归并为中文职业大类。"""
    raw = '' if pd.isna(value) else str(value).strip()
    if not raw:
        return '未标注'
    try:
        labels = ast.literal_eval(raw) if raw.startswith('[') else [raw]
    except (ValueError, SyntaxError):
        labels = [raw]
    text_value = ' '.join(str(v).lower() for v in labels)
    rules = [
        ('数据与算法', ['data-', 'data ', 'analytics', 'machine-learning', 'artificial-intelligence', 'ai-', 'business-intelligence']),
        ('技术研发', ['software', 'developer', 'engineer', 'devops', 'frontend', 'backend', 'full-stack', 'web-', 'mobile-', 'qa-', 'testing', 'cloud-']),
        ('产品管理', ['product']),
        ('设计创意', ['design', 'ux-', 'graphic', 'creative']),
        ('销售与业务', ['sales', 'business-development', 'account-', 'marketing', 'partnership']),
        ('客户服务', ['customer', 'client-', 'support', 'success', 'call-centre', 'contact-centre']),
        ('财务会计', ['finance', 'financial', 'accounting', 'bookkeep', 'cpa']),
        ('人力资源', ['human-resource', 'hr-', 'recruit', 'talent', 'people-']),
        ('运营与管理', ['operation', 'strategy', 'management', 'administrative', 'assistant']),
        ('教育服务', ['education', 'admission', 'academic', 'student-service', 'counsel']),
        ('医疗健康', ['clinical', 'health', 'pharma', 'medical']),
        ('法务合规', ['legal', 'compliance']),
        ('内容与文案', ['content', 'copywriter', 'writing', 'editor']),
    ]
    for name, keywords in rules:
        if any(k in text_value for k in keywords):
            return name
    return '其他岗位'

df['category_main'] = df['category'].apply(category_group)
df['source_cn'] = df['source'].replace({'himalayas': '海外远程岗位', '国家大学生就业服务平台': '国家大学生就业服务平台'})
# 固定使用 Windows 自带微软雅黑，避免中文标题和坐标标签显示为方框。
CHINESE_FONT = Path(r'C:\Windows\Fonts\msyh.ttc')
if CHINESE_FONT.exists():
    font_manager.fontManager.addfont(str(CHINESE_FONT))
    chinese_name = font_manager.FontProperties(fname=str(CHINESE_FONT)).get_name()
else:
    chinese_name = 'Microsoft YaHei'
sns.set_theme(style='whitegrid', font=chinese_name)
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = [chinese_name, 'Microsoft YaHei', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False

def save(name):
    plt.tight_layout(); plt.savefig(OUT / name, dpi=180, bbox_inches='tight'); plt.close()

df['source_cn'].value_counts().sort_values().plot(kind='barh', color='#2878b5'); plt.title('岗位来源数量对比'); plt.xlabel('岗位数'); plt.ylabel('数据来源'); save('01_source_counts.png')
known_location = df[df['location_main'].ne('')].copy()
known_location['location_main'].value_counts().head(12).sort_values().plot(kind='barh', color='#4daf4a'); plt.title('已明确地区的岗位分布（前12）'); plt.xlabel('岗位数'); plt.ylabel('地区'); save('02_location_top12.png')
category_known = df[df['category_main'].ne('未标注')]
category_known['category_main'].value_counts().head(12).sort_values().plot(kind='barh', color='#984ea3'); plt.title('已标注岗位职业方向分布'); plt.xlabel('岗位数'); plt.ylabel('职业方向'); save('03_category_top12.png')
salary = df[df['salary_avg_k'].notna() & (df['salary_avg_k'] > 0) & (df['salary_avg_k'] < 100)].copy()
salary_bins = [0, 5, 10, 15, 20, 30, 50, 100]
salary_labels = ['5千元以下', '5-10千元', '10-15千元', '15-20千元', '20-30千元', '30-50千元', '50千元以上']
salary['salary_range'] = pd.cut(salary['salary_avg_k'], bins=salary_bins, labels=salary_labels, right=False)
salary_counts = salary['salary_range'].value_counts().reindex(salary_labels, fill_value=0)
ax = salary_counts.plot(kind='bar', color='#5b7db1', figsize=(8, 5))
plt.title('已公布薪资岗位的月薪区间分布')
plt.xlabel('月薪区间（千元/月）')
plt.ylabel('岗位数')
plt.xticks(rotation=0)
for i, value in enumerate(salary_counts):
    ax.text(i, value + max(salary_counts.max() * 0.015, 1), str(int(value)), ha='center', va='bottom', fontsize=9)
save('04_salary_boxplot.png')
edu_main = df['education'].replace('', '未说明')
edu = edu_main.value_counts().head(10).sort_values(); edu.plot(kind='barh', color='#ff7f00'); plt.title('学历要求分布'); plt.xlabel('岗位数'); plt.ylabel('学历要求'); save('05_education.png')
toploc = known_location['location_main'].value_counts().head(8).index; topedu = edu_main.loc[known_location.index].value_counts().head(6).index
heat_data = known_location[known_location['location_main'].isin(toploc)].copy()
heat_data['education_main'] = edu_main.loc[heat_data.index]
p = heat_data[heat_data['education_main'].isin(topedu)].pivot_table(index='location_main', columns='education_main', values='job_id', aggfunc='count', fill_value=0)
sns.heatmap(p, cmap='YlGnBu', annot=False); plt.title('地区与学历要求热力图'); plt.xlabel('学历要求'); plt.ylabel('地区'); save('06_location_category_heatmap.png')
skill_counts = {}
for val in df['skills'].fillna(''):
    for skill in str(val).split(','):
        if skill: skill_counts[skill] = skill_counts.get(skill, 0) + 1
skill_groups = {
    '编程语言': ['Python', 'Java', 'C++', 'Go', 'JavaScript', 'TypeScript'],
    '数据库': ['SQL', 'MySQL', 'PostgreSQL', 'Oracle'],
    '云计算': ['AWS', 'Azure'],
    '工程与运维': ['Docker', 'Kubernetes', 'Linux', 'Git'],
    '数据分析工具': ['Excel', 'Power BI', 'Tableau', 'Pandas', 'NumPy'],
    '大数据技术': ['Hadoop', 'Spark', 'Flink', 'Kafka'],
    '人工智能与算法': ['机器学习', '深度学习', '人工智能', 'TensorFlow', 'PyTorch', '数据挖掘', '算法'],
}
skill_to_group = {skill: group for group, skills in skill_groups.items() for skill in skills}
group_counts = {}
for skill, count in skill_counts.items():
    group = skill_to_group.get(skill, '其他技能')
    group_counts[group] = group_counts.get(group, 0) + count
pd.Series(group_counts).sort_values().plot(kind='barh', color='#e41a1c'); plt.title('技能类别频次'); plt.xlabel('岗位数'); plt.ylabel('技能类别'); save('07_skill_frequency.png')
location_salary = df[df['location_main'].ne('') & df['salary_avg_k'].notna() & (df['salary_avg_k'] > 0)].groupby('location_main').agg(job_count=('job_id','count'), salary_avg=('salary_avg_k','mean'))
agg = location_salary.sort_values('job_count', ascending=False).head(15).sort_values('job_count')
plt.figure(figsize=(9, 5.5))
plt.scatter(agg['job_count'], agg['salary_avg'], s=agg['job_count']*5, alpha=.65, c=range(len(agg)), cmap='viridis')
label_offsets = {'安徽': (7, -14), '湖北': (7, 8), '河北': (7, -10), '河南': (7, 8), '天津': (7, 10), '福建': (7, -12)}
for label, row in agg.iterrows():
    plt.annotate(label, (row['job_count'], row['salary_avg']), xytext=label_offsets.get(label, (5, 5)), textcoords='offset points', fontsize=10)
plt.xlabel('岗位数量'); plt.ylabel('平均薪资（千元/月）'); plt.title('地区岗位需求与平均薪资'); save('08_demand_salary_bubble.png')
print(f'生成 8 张图：{OUT}')
