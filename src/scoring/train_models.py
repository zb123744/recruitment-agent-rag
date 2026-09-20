from __future__ import annotations
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix, ConfusionMatrixDisplay, roc_curve
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[2]; DATA = ROOT/'data/cleaned/recruitment_jobs_cleaned.csv'; OUT = ROOT/'outputs'; (OUT/'tables').mkdir(parents=True, exist_ok=True); (OUT/'predictions').mkdir(parents=True, exist_ok=True); (OUT/'figures').mkdir(parents=True, exist_ok=True)
CHINESE_FONT = Path(r'C:\Windows\Fonts\msyh.ttc')
if CHINESE_FONT.exists():
    font_manager.fontManager.addfont(str(CHINESE_FONT))
    chinese_name = font_manager.FontProperties(fname=str(CHINESE_FONT)).get_name()
else:
    chinese_name = 'Microsoft YaHei'
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = [chinese_name, 'Microsoft YaHei', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False
df = pd.read_csv(DATA)
features = ['salary_avg_k','benefit_count','description_length','skill_count','salary_known','source','education','company_scale','company_property']
X, y = df[features], df['quality_label']
num = ['salary_avg_k','benefit_count','description_length','skill_count','salary_known']; cat = ['source','education','company_scale','company_property']
prep = ColumnTransformer([('num', Pipeline([('impute',SimpleImputer(strategy='median')),('scale',StandardScaler())]), num), ('cat', Pipeline([('impute',SimpleImputer(strategy='most_frequent')),('onehot',OneHotEncoder(handle_unknown='ignore'))]), cat)])
models = {'Logistic': LogisticRegression(max_iter=1000), 'SVM': SVC(probability=True, random_state=42), 'RandomForest': RandomForestClassifier(n_estimators=250, random_state=42, class_weight='balanced'), 'XGBoost': XGBClassifier(n_estimators=250, max_depth=4, learning_rate=.05, subsample=.85, colsample_bytree=.85, eval_metric='logloss', random_state=42)}
model_cn = {'Logistic': '逻辑回归', 'SVM': '支持向量机', 'RandomForest': '随机森林', 'XGBoost': 'XGBoost'}
Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=.25,random_state=42,stratify=y); results=[]
for name, model in models.items():
    pipe=Pipeline([('prep',prep),('model',model)]); pipe.fit(Xtr,ytr); pred=pipe.predict(Xte); prob=pipe.predict_proba(Xte)[:,1]
    results.append({'model':name,'accuracy':accuracy_score(yte,pred),'precision':precision_score(yte,pred,zero_division=0),'recall':recall_score(yte,pred,zero_division=0),'f1':f1_score(yte,pred,zero_division=0),'roc_auc':roc_auc_score(yte,prob)})
    display_name = model_cn[name]
    ConfusionMatrixDisplay(confusion_matrix(yte,pred), display_labels=['普通岗位','高质量岗位']).plot(cmap='Blues', values_format='d')
    plt.title(f'{display_name}混淆矩阵')
    plt.xlabel('预测类别')
    plt.ylabel('真实类别')
    plt.tight_layout()
    plt.savefig(OUT/'figures'/f'cm_{name}.png', dpi=160)
    plt.close()
    fpr, tpr, _ = roc_curve(yte, prob)
    auc_value = roc_auc_score(yte, prob)
    plt.figure(figsize=(8, 6))
    plt.plot(fpr, tpr, linewidth=2, label=f'{display_name}（AUC = {auc_value:.2f}）')
    plt.plot([0, 1], [0, 1], '--', color='gray', label='随机猜测基线')
    plt.xlabel('假阳性率')
    plt.ylabel('真正率')
    plt.title(f'{display_name} ROC曲线')
    plt.legend(loc='lower right')
    plt.tight_layout()
    plt.savefig(OUT/'figures'/f'roc_{name}.png', dpi=160)
    plt.close()
    pd.DataFrame({'actual':yte,'predicted':pred,'probability':prob}).to_csv(OUT/'predictions'/f'{name}_predictions.csv',index=False)
res=pd.DataFrame(results); res.to_csv(OUT/'tables/model_metrics.csv',index=False); print(res.to_string(index=False))
