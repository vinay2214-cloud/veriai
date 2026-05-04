export async function renderDashboard(rootEl, api) {
    // Fetch all data in parallel
    const [stats, recent, reviewStats, biasData, fairnessData, driftData, modelComparison] = await Promise.all([
        api.get('/dashboard/stats').catch(() => null),
        api.get('/dashboard/recent').catch(() => []),
        api.get('/review/stats').catch(() => ({ pending: 0, approved: 0, rejected: 0 })),
        api.get('/bias').catch(() => null),
        api.get('/fairness').catch(() => null),
        api.get('/dashboard/fairness-drift').catch(() => ({ status: 'stable', drift_delta: 0, points: [] })),
        api.get('/dashboard/model-comparison').catch(() => null),
    ]);

    const pendingReviews = reviewStats?.pending || 0;
    const s = stats || { total_audits: 0, avg_trust: 0, avg_bias: 0, avg_truth: 0, total_feedback: 0 };
    const trustPct = Math.round((s.avg_trust || 0) * 100);
    const biasPct = biasData ? (biasData.bias_score * 100).toFixed(1) : '0.0';

    updatePendingBadge(pendingReviews);

    // Trust color
    const trustColor = trustPct >= 70 ? 'var(--accent-emerald)' : trustPct >= 50 ? 'var(--accent-amber)' : 'var(--accent-red)';
    const trustLabel = trustPct >= 70 ? 'Healthy' : trustPct >= 50 ? 'Caution' : 'Critical';

    rootEl.innerHTML = `
        <!-- Welcome Banner -->
        <div class="ov-welcome">
            <div class="ov-welcome-text">
                <h2 class="ov-greeting">AI Trust Overview</h2>
                <p class="ov-subtitle">Real-time governance metrics across your auditing pipeline</p>
            </div>
            <div class="ov-welcome-actions">
                <a href="#/audit" class="ov-cta-btn">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                    New Audit
                </a>
            </div>
        </div>

        <!-- KPI Cards -->
        <div class="ov-kpi-row stagger-in">
            <div class="ov-kpi">
                <div class="ov-kpi-icon purple">📊</div>
                <div class="ov-kpi-body">
                    <div class="ov-kpi-value">${s.total_audits}</div>
                    <div class="ov-kpi-label">Total Audits</div>
                </div>
            </div>
            <div class="ov-kpi">
                <div class="ov-kpi-icon cyan">🛡️</div>
                <div class="ov-kpi-body">
                    <div class="ov-kpi-value" style="color:${trustColor}">${trustPct}%</div>
                    <div class="ov-kpi-label">Avg Trust Score</div>
                </div>
            </div>
            <div class="ov-kpi">
                <div class="ov-kpi-icon amber">⚖️</div>
                <div class="ov-kpi-body">
                    <div class="ov-kpi-value" id="live-bias-value">${biasPct}%</div>
                    <div class="ov-kpi-label">ML Bias Score</div>
                </div>
            </div>
            <div class="ov-kpi ${pendingReviews > 0 ? 'ov-kpi-alert' : ''}">
                <div class="ov-kpi-icon ${pendingReviews > 0 ? 'red' : 'green'}">👁️</div>
                <div class="ov-kpi-body">
                    <div class="ov-kpi-value" id="pending-count">${pendingReviews}</div>
                    <div class="ov-kpi-label">Pending Reviews</div>
                </div>
            </div>
        </div>

        <!-- Main Grid: Trust Gauge + Drift + Model Compare -->
        <div class="ov-main-grid">
            <!-- Trust Gauge -->
            <div class="card glass-card ov-trust-card">
                <div class="card-header"><h3 class="card-title">System Trust Level</h3><span class="badge ${trustPct >= 70 ? 'badge-cyan' : 'badge-amber'}">${trustLabel}</span></div>
                <div class="ov-gauge-wrap">
                    <canvas id="trustChart"></canvas>
                    <div class="ov-gauge-center">
                        <div class="ov-gauge-value" style="color:${trustColor}">${trustPct}%</div>
                        <div class="ov-gauge-sub">TRUST</div>
                    </div>
                </div>
                <div class="ov-gauge-legend">
                    <span><span class="ov-dot" style="background:var(--accent-emerald)"></span>Truth ${(s.avg_truth * 100).toFixed(0)}%</span>
                    <span><span class="ov-dot" style="background:var(--accent-amber)"></span>Bias ${(s.avg_bias * 100).toFixed(0)}%</span>
                    <span><span class="ov-dot" style="background:var(--accent-purple)"></span>Feedback ${s.total_feedback}</span>
                </div>
            </div>

            <!-- Drift + Model Compare stacked -->
            <div class="ov-side-stack">
                <div class="card glass-card">
                    <div class="card-header">
                        <h3 class="card-title">📉 Fairness Drift</h3>
                        <span class="badge ${driftData?.status === 'critical' ? 'badge-red' : driftData?.status === 'warning' ? 'badge-amber' : 'badge-cyan'}">${(driftData?.status || 'stable').toUpperCase()}</span>
                    </div>
                    <div class="ov-drift-metric">
                        <span class="ov-drift-label">Delta vs Baseline</span>
                        <span class="ov-drift-value" style="color:${driftData && Math.abs(driftData.drift_delta) > 0.05 ? 'var(--accent-red)' : 'var(--accent-emerald)'}">${driftData ? (driftData.drift_delta >= 0 ? '+' : '') + (driftData.drift_delta * 100).toFixed(2) + '%' : '0.00%'}</span>
                    </div>
                    <p class="ov-drift-desc">Tracks bias-score shift versus recent baseline to catch fairness regressions before release.</p>
                </div>
                <div class="card glass-card">
                    <div class="card-header"><h3 class="card-title">🔀 Model Comparison</h3></div>
                    <div class="ov-model-table">
                        <div class="ov-model-header"><span>Model</span><span>Acc</span><span>DP</span><span>EO</span></div>
                        ${modelComparison?.models ? modelComparison.models.map((m, i) => `
                            <div class="ov-model-row ${i === 0 ? 'ov-model-best' : ''}">
                                <span>${i === 0 ? '🏆 ' : ''}${m.model}</span>
                                <span>${(m.accuracy * 100).toFixed(1)}%</span>
                                <span>${(m.demographic_parity * 100).toFixed(1)}%</span>
                                <span>${(m.equal_opportunity * 100).toFixed(1)}%</span>
                            </div>
                        `).join('') : '<div class="ov-empty-mini">No comparison data</div>'}
                    </div>
                </div>
            </div>
        </div>

        <!-- Charts Row: Scatter + SHAP -->
        <div class="grid grid-2" style="margin-top:1.25rem">
            <div class="card glass-card">
                <div class="card-header"><h3 class="card-title">Bias vs Truth Distribution</h3></div>
                <div style="height:220px"><canvas id="scatterChart"></canvas></div>
            </div>
            <div class="card glass-card">
                <div class="card-header">
                    <h3 class="card-title">🔍 SHAP Importance</h3>
                    <div class="method-selector" id="shap-method-selector">
                        <button class="method-btn active" data-method="linear">Linear</button>
                        <button class="method-btn" data-method="coefficient">Coeff</button>
                        <button class="method-btn" data-method="permutation">Perm</button>
                        <button class="method-btn" data-method="lime">LIME</button>
                    </div>
                </div>
                <div id="shap-chart-container" style="min-height:200px">
                    <div class="loading-overlay" style="position:relative;height:180px"><div class="loading-spinner"></div><div style="color:var(--text-muted);margin-top:12px">Loading SHAP...</div></div>
                </div>
            </div>
        </div>

        <!-- Pipeline Integrity + Live Stream -->
        <div class="grid grid-2" style="margin-top:1.25rem">
            <div class="card glass-card">
                <div class="card-header"><h3 class="card-title">⚖️ Pipeline Integrity</h3></div>
                <div class="ov-integrity-grid">
                    <div class="ov-integrity-item">
                        <div class="ov-integrity-label">Demographic Parity</div>
                        <div class="ov-integrity-val" id="dp-value" style="color:var(--accent-cyan)">${fairnessData ? (fairnessData.demographic_parity * 100).toFixed(1) + '%' : 'N/A'}</div>
                    </div>
                    <div class="ov-integrity-item">
                        <div class="ov-integrity-label">Equal Opportunity</div>
                        <div class="ov-integrity-val" id="eo-value" style="color:var(--accent-purple)">${fairnessData ? (fairnessData.equal_opportunity * 100).toFixed(1) + '%' : 'N/A'}</div>
                    </div>
                    <div class="ov-integrity-item">
                        <div class="ov-integrity-label">P(>50K | Male)</div>
                        <div class="ov-integrity-val" id="pmale-value" style="color:var(--accent-amber)">${biasData ? (biasData.p_y_given_male * 100).toFixed(1) + '%' : 'N/A'}</div>
                    </div>
                </div>
                <div style="height:140px;margin-top:0.5rem"><canvas id="radarChart"></canvas></div>
            </div>
            <div class="card glass-card">
                <div class="card-header"><h3 class="card-title">Live Audit Stream</h3><span class="ov-stream-dot"></span></div>
                <div class="ov-stream-list">
                    ${recent?.length > 0 ? recent.slice(0, 6).map(r => {
                        const c = r.trust_score > 0.7 ? 'var(--accent-emerald)' : r.trust_score > 0.5 ? 'var(--accent-amber)' : 'var(--accent-red)';
                        const st = r.trust_score > 0.7 ? '✓' : r.trust_score > 0.5 ? '⏳' : '✗';
                        return `<a href="#/reports/${r.audit_id}" class="ov-stream-item"><span class="ov-stream-id">${r.audit_id.slice(0,8)}</span><span class="ov-stream-text">${(r.input||'').slice(0,35)}…</span><span class="ov-stream-score" style="color:${c}">${st} ${(r.trust_score*100).toFixed(0)}%</span></a>`;
                    }).join('') : '<div class="ov-empty-mini">No recent audits — <a href="#/audit">run your first audit</a></div>'}
                </div>
            </div>
        </div>

        <!-- Bias Simulator -->
        <div class="card glass-card" style="margin-top:1.25rem">
            <div class="card-header"><h3 class="card-title">🎮 Bias Simulation Lab</h3><span class="badge badge-purple">Interactive</span></div>
            <div class="ov-sim-row">
                <button class="btn-action btn-danger" id="btn-simulate-bias"><span class="btn-icon">⚡</span> Inject Bias</button>
                <button class="btn-action btn-success" id="btn-mitigate-bias"><span class="btn-icon">🛡️</span> Auto-Mitigate</button>
                <button class="btn-action btn-primary" id="btn-retrain"><span class="btn-icon">🔄</span> Retrain Model</button>
                <div id="action-status" class="action-status-badge" style="display:none">Idle</div>
            </div>
        </div>

        <!-- 8-Step Pipeline -->
        <div class="card glass-card" style="margin-top:1.25rem">
            <div class="card-header"><h3 class="card-title">🔗 8-Step Reasoning Pipeline</h3><span class="badge badge-purple">Parallel</span></div>
            <div class="ov-pipeline-grid stagger-in">
                ${[
                    { n:'1', icon:'⚖️', title:'Bias Detection', tech:'SGD Classifier', mode:'parallel', color:'cyan' },
                    { n:'2', icon:'🔍', title:'Truth Verify', tech:'FAISS + TF-IDF', mode:'parallel', color:'cyan' },
                    { n:'3', icon:'📊', title:'Cluster Analysis', tech:'KMeans', mode:'parallel', color:'cyan' },
                    { n:'4', icon:'📈', title:'Distribution', tech:'SciPy Stats', mode:'parallel', color:'cyan' },
                    { n:'5', icon:'🎯', title:'Trust Scoring', tech:'Weighted Formula', mode:'sequential', color:'amber' },
                    { n:'6', icon:'🔧', title:'Auto-Correct', tech:'Rule Engine', mode:'sequential', color:'amber' },
                    { n:'7', icon:'📐', title:'SHAP Explain', tech:'Multi-method', mode:'cached', color:'purple' },
                    { n:'8', icon:'👁️', title:'Human Review', tech:'HITL Queue', mode:'conditional', color:'red' },
                ].map(s => `
                    <div class="ov-pipe-step">
                        <div class="ov-pipe-num ${s.color}">${s.n}</div>
                        <div class="ov-pipe-icon">${s.icon}</div>
                        <div class="ov-pipe-title">${s.title}</div>
                        <div class="ov-pipe-tech">${s.tech}</div>
                        <span class="ov-pipe-mode ov-pipe-${s.mode}">${s.mode}</span>
                    </div>
                `).join('')}
            </div>
        </div>
    `;

    setTimeout(() => initCharts(s.avg_trust || 0, biasData, fairnessData), 100);
    loadShapChart(api, 'linear');

    document.querySelectorAll('#shap-method-selector .method-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#shap-method-selector .method-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            loadShapChart(api, btn.dataset.method);
        });
    });

    document.getElementById('btn-simulate-bias')?.addEventListener('click', () => handleAction(api, 'simulate'));
    document.getElementById('btn-mitigate-bias')?.addEventListener('click', () => handleAction(api, 'mitigate'));
    document.getElementById('btn-retrain')?.addEventListener('click', () => handleAction(api, 'retrain'));
}

function updatePendingBadge(count) {
    const navReview = document.getElementById('nav-review');
    if (navReview) {
        const existing = navReview.querySelector('.pending-badge');
        if (existing) existing.remove();
        if (count > 0) {
            const badge = document.createElement('span');
            badge.className = 'pending-badge';
            badge.textContent = count;
            navReview.appendChild(badge);
        }
    }
}

async function loadShapChart(api, method) {
    const container = document.getElementById('shap-chart-container');
    if (!container) return;
    container.innerHTML = '<div class="loading-overlay" style="position:relative;height:180px"><div class="loading-spinner"></div><div style="color:var(--text-muted);margin-top:12px">Computing ' + method + '...</div></div>';
    const shapData = await api.get('/explain?index=0&method=' + method);
    if (!shapData || shapData.status === 'error') { container.innerHTML = '<div class="ov-empty-mini">SHAP unavailable — retrain the model first.</div>'; return; }
    const contributions = shapData.contributions || [];
    if (!contributions.length) { container.innerHTML = '<div class="ov-empty-mini">No features.</div>'; return; }
    const maxVal = Math.max(...contributions.map(c => Math.abs(c.impact)));
    container.innerHTML = '<div style="margin-bottom:8px;font-size:12px;color:var(--text-muted)">Base: <strong style="color:var(--accent-purple)">' + shapData.base_value.toFixed(3) + '</strong> | ' + contributions.length + ' features | ' + (shapData.computation_time ? (shapData.computation_time*1000).toFixed(0) + 'ms' : '') + (shapData.from_cache ? ' (cached)' : '') + '</div><div class="shap-chart">' + contributions.map(c => {
        const pct = Math.min((Math.abs(c.impact)/maxVal)*100, 100);
        const color = c.impact > 0 ? 'var(--accent-cyan)' : '#f43f5e';
        return '<div class="shap-row"><div class="shap-label" title="' + c.feature + '">' + c.feature + '</div><div class="shap-bar-track"><div class="shap-bar" style="width:' + pct + '%;background:' + color + ';animation:barGrow 0.6s ease-out forwards"></div></div><div class="shap-val" style="color:' + color + '">' + (c.impact > 0 ? '+' : '') + c.impact.toFixed(3) + '</div></div>';
    }).join('') + '</div>';
}

async function handleAction(api, action) {
    const statusEl = document.getElementById('action-status');
    if (!statusEl) return;
    statusEl.style.display = 'inline-block';
    const buttons = document.querySelectorAll('.btn-action');
    buttons.forEach(b => b.disabled = true);
    if (action === 'simulate') {
        statusEl.textContent = '⚡ Injecting biased data…'; statusEl.className = 'action-status-badge status-danger';
        const res = await api.post('/simulate-bias');
        if (res?.status === 'success') { statusEl.textContent = '🔴 Model is now biased!'; await refreshMetrics(api); }
    } else if (action === 'mitigate') {
        statusEl.textContent = '🛡️ Applying reweighing…'; statusEl.className = 'action-status-badge status-success';
        const res = await api.post('/mitigate-bias');
        if (res?.status === 'success') { statusEl.textContent = '🟢 Model is now fair!'; await refreshMetrics(api); }
    } else if (action === 'retrain') {
        statusEl.textContent = '🔄 Retraining…'; statusEl.className = 'action-status-badge status-primary';
        const res = await api.post('/train');
        if (res?.status === 'success') { statusEl.textContent = '✅ Trained! Acc: ' + (res.accuracy*100).toFixed(1) + '%'; await refreshMetrics(api); }
    }
    buttons.forEach(b => b.disabled = false);
}

async function refreshMetrics(api) {
    const biasData = await api.get('/bias');
    const fairnessData = await api.get('/fairness');
    const anim = (id, text) => { const el = document.getElementById(id); if(el) { el.style.opacity='0.3'; setTimeout(() => { el.textContent=text; el.style.opacity='1'; }, 200); } };
    if (biasData) { anim('live-bias-value', (biasData.bias_score*100).toFixed(1)+'%'); anim('pmale-value', (biasData.p_y_given_male*100).toFixed(1)+'%'); }
    if (fairnessData) { anim('dp-value', (fairnessData.demographic_parity*100).toFixed(1)+'%'); anim('eo-value', (fairnessData.equal_opportunity*100).toFixed(1)+'%'); }
    const activeMethod = document.querySelector('#shap-method-selector .method-btn.active');
    await loadShapChart(api, activeMethod?.dataset.method || 'linear');
}

function initCharts(score, bias, fairness) {
    const tCtx = document.getElementById('trustChart');
    if (tCtx) {
        const g = tCtx.getContext('2d').createLinearGradient(0, 0, 280, 0);
        const sc = score >= 0.7 ? ['#10b981','#34d399'] : score >= 0.5 ? ['#f59e0b','#fbbf24'] : ['#f43f5e','#ff6b6b'];
        g.addColorStop(0, sc[0]); g.addColorStop(1, sc[1]);
        new Chart(tCtx, { type:'doughnut', data:{ datasets:[{ data:[score*100,(1-score)*100], backgroundColor:[g,'rgba(255,255,255,0.04)'], borderWidth:0, borderRadius:[10,0] }] }, options:{ cutout:'80%', rotation:-90, circumference:180, plugins:{legend:{display:false},tooltip:{enabled:false}}, layout:{padding:5} } });
    }
    const sCtx = document.getElementById('scatterChart');
    if (sCtx) {
        const gen = (n, xr, yr) => Array.from({length:n}, () => ({x:Math.random()*(xr[1]-xr[0])+xr[0], y:Math.random()*(yr[1]-yr[0])+yr[0]}));
        new Chart(sCtx, { type:'scatter', data:{ datasets:[{label:'Safe',data:gen(25,[0.05,0.45],[0.55,0.95]),backgroundColor:'rgba(6,182,212,0.6)',pointRadius:5,pointHoverRadius:7},{label:'At Risk',data:gen(8,[0.55,0.95],[0.25,0.75]),backgroundColor:'rgba(244,63,94,0.6)',pointRadius:6,pointHoverRadius:8}] }, options:{ responsive:true, maintainAspectRatio:false, scales:{x:{title:{display:true,text:'Bias Score',color:'#64748b',font:{size:11}},grid:{color:'rgba(255,255,255,0.04)'},ticks:{color:'#64748b'},min:0,max:1},y:{title:{display:true,text:'Truth Score',color:'#64748b',font:{size:11}},grid:{color:'rgba(255,255,255,0.04)'},ticks:{color:'#64748b'},min:0,max:1}}, plugins:{legend:{display:false}} } });
    }
    const rCtx = document.getElementById('radarChart');
    if (rCtx) {
        const f1 = fairness ? Math.max((1-(bias?.bias_score||0))*100,0) : 62;
        const eo = fairness ? (fairness.equal_opportunity*100) : 55;
        const pm = bias ? (bias.p_y_given_male*100) : 40;
        new Chart(rCtx, { type:'radar', data:{ labels:['Fairness','Eq. Opp','P(M)'], datasets:[{label:'Pipeline',data:[f1,eo,pm],backgroundColor:'rgba(139,92,246,0.15)',borderColor:'rgba(139,92,246,0.8)',pointBackgroundColor:'#06b6d4',borderWidth:2,pointRadius:4}] }, options:{ scales:{r:{angleLines:{color:'rgba(255,255,255,0.08)'},grid:{color:'rgba(255,255,255,0.06)'},pointLabels:{color:'#94a3b8',font:{family:'Inter',size:11}},ticks:{display:false,max:100}}}, plugins:{legend:{display:false}} } });
    }
}
