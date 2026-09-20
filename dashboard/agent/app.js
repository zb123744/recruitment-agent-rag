const $ = (id) => document.getElementById(id);
const api = async (url, options) => {
  const res = await fetch(url, options);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || '请求失败');
  return data;
};

document.querySelectorAll('.tab').forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach((x) => x.classList.remove('active'));
    document.querySelectorAll('.panel').forEach((x) => x.classList.remove('active'));
    btn.classList.add('active');
    $(btn.dataset.tab).classList.add('active');
  });
});

document.querySelectorAll('[data-demo]').forEach((btn) => {
  btn.addEventListener('click', () => {
    if (btn.dataset.demo === 'python') {
      $('agentMessage').value = '有哪些岗位要求Python技能？';
    } else {
      $('agentMessage').value = '简历：本科，3年经验。熟悉 Python、SQL、Pandas、机器学习。地点上海。岗位：本科，要求3年经验，熟悉Python、SQL、Pandas、Spark、机器学习。工作地点上海。';
    }
  });
});

function table(rows, headers) {
  if (!rows.length) return '<p>暂无数据</p>';
  return '<table><thead><tr>' + headers.map((h) => '<th>' + h + '</th>').join('') + '</tr></thead><tbody>' +
    rows.map((r) => '<tr>' + r.map((c) => '<td>' + c + '</td>').join('') + '</tr>').join('') + '</tbody></table>';
}

async function init() {
  try {
    await api('/api/health');
    $('health').textContent = '服务已连接';
  } catch (e) {
    $('health').textContent = '服务未连接';
    $('health').style.color = '#b75d52';
  }

  const prompts = await api('/api/prompts');
  $('promptBox').innerHTML = table(
    prompts.versions.map((v) => [v.version, v.name, v.goal, v.changelog]),
    ['版本', '名称', '目标', '变更说明']
  );

  const cluster = await api('/api/cluster');
  $('clusterBox').textContent =
    '最优K = ' + cluster.best_k + '\n轮廓系数 = ' + cluster.best_silhouette +
    '\nPCA解释方差 = ' + cluster.pca_variance_explained + '\n\n' +
    cluster.clusters.map((c) => c.name + '：' + c.count + '条，均薪' + c.avg_salary_k + '千，技能' + c.avg_skills + '，质量分' + c.avg_quality).join('\n');

  const models = await api('/api/models');
  $('modelBox').innerHTML = table(
    models.models.map((m) => [m.model, m.accuracy + '%', m.f1 + '%', m.roc_auc + '%']),
    ['模型', '准确率', 'F1', 'AUC']
  ) + '<p style="margin-top:10px;color:#5d726b">' + models.conclusion + '</p>';
}

$('askAgent').addEventListener('click', async () => {
  $('askAgent').disabled = true;
  $('agentAnswer').textContent = '工作流执行中...';
  try {
    const data = await api('/api/agent', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: $('agentMessage').value.trim(),
        prompt_version: $('promptVersion').value,
      }),
    });
    $('agentAnswer').textContent = data.answer;
    $('agentSteps').innerHTML = data.steps.map((s) => '<li><strong>' + s.stage + '</strong>：' + s.detail + '</li>').join('');
    $('agentTools').textContent = JSON.stringify(data.tool_calls, null, 2);
    $('agentTriples').innerHTML = table(
      (data.triples || []).map((t) => [t.question, t.answer, t.source, t.similarity]),
      ['问题', '答案', '来源', '相似度']
    );
    $('promptPreview').textContent = data.prompt_preview || '';
  } catch (e) {
    $('agentAnswer').textContent = '出错：' + e.message;
  } finally {
    $('askAgent').disabled = false;
  }
});

$('runMatch').addEventListener('click', async () => {
  try {
    const data = await api('/api/match', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        resume_text: $('resumeText').value,
        job_text: $('jobText').value,
        resume_location: '上海',
        job_location: '上海',
      }),
    });
    $('matchResult').innerHTML =
      '<div><span>综合匹配分</span><strong>' + data.score + '</strong></div>' +
      '<div><span>匹配等级</span><strong>' + data.level + '</strong></div>' +
      '<div><span>已匹配技能</span><strong>' + (data.skill_overlap.join('、') || '无') + '</strong></div>' +
      '<div><span>缺失技能</span><strong>' + (data.missing_skills.join('、') || '无') + '</strong></div>';
    $('matchRaw').textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    $('matchRaw').textContent = '出错：' + e.message;
  }
});

$('extractResume').addEventListener('click', async () => {
  const file = $('resumeFile').files[0];
  if (!file) { $('resumeStatus').textContent = '请先选择 PDF 文件'; return; }
  const form = new FormData();
  form.append('file', file);
  $('resumeStatus').textContent = '正在提取...';
  try {
    const data = await api('/api/resume/extract', { method: 'POST', body: form });
    $('resumeText').value = data.text;
    $('resumeStatus').textContent = `已提取 ${data.characters} 个字符`;
  } catch (e) { $('resumeStatus').textContent = '提取失败：' + e.message; }
});

$('recommendJobs').addEventListener('click', async () => {
  const resume = $('resumeText').value.trim();
  if (!resume) { $('recommendResult').textContent = '请先粘贴或提取简历文本'; return; }
  $('recommendResult').textContent = '推荐计算中...';
  try {
    const data = await api('/api/recommend', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resume_text: resume, top_k: 5 })
    });
    $('recommendResult').innerHTML = table(
      data.recommendations.map((r) => [r.job_title, r.company_name, r.location, r.match_score, r.level, r.missing_skills.join('、') || '无']),
      ['岗位', '公司', '地点', '匹配分', '等级', '待补技能']
    );
  } catch (e) { $('recommendResult').textContent = '推荐失败：' + e.message; }
});

$('runRag').addEventListener('click', async () => {
  try {
    const data = await api('/api/rag', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: $('ragQuestion').value,
        top_k: Number($('ragTopK').value),
      }),
    });
    $('ragResult').innerHTML = table(
      data.hits.map((h) => [h.rank, h.answer, h.source, h.similarity]),
      ['排名', '答案片段', '来源', '相似度']
    );
  } catch (e) {
    $('ragResult').innerHTML = '<p>出错：' + e.message + '</p>';
  }
});

init();
