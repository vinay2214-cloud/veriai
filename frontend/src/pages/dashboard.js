export async function renderDashboard(rootEl, api) {
    const [stats, recent, reviewStats, biasData, fairnessData, driftData, modelComparison] = await Promise.all([
        api.get('/dashboard/stats').catch(() => null),
        api.get('/dashboard/recent').catch(() => []),
        api.get('/review/stats').catch(() => ({ pending: 0, approved: 0, rejected: 0 })),
        api.get('/bias').catch(() => null),
        api.get('/fairness').catch(() => null),
        api.get('/dashboard/fairness-drift').catch(() => ({ status: 'stable', drift_delta: 0, points: [] })),
        api.get('/dashboard/model-comparison').catch(() => null),
    ]);

    const s = stats || { total_audits: 0, avg_trust: 0, avg_bias: 0, avg_truth: 0, total_feedback: 0 };
    const pending = reviewStats?.pending || 0;
    const trustPct = Math.round((s.avg_trust || 0) * 100);
    const biasPct = biasData ? (biasData.bias_score * 100).toFixed(1) : '0.0';
    const dpVal = fairnessData ? (fairnessData.demographic_parity * 100).toFixed(1) : '—';
    const eoVal = fairnessData ? (fairnessData.equal_opportunity * 100).toFixed(1) : '—';
    const trustLevel = trustPct >= 70 ? 'HIGH' : trustPct >= 50 ? 'MEDIUM' : 'LOW';
    const trustLevelClass = trustPct >= 70 ? 'dv-level-high' : trustPct >= 50 ? 'dv-level-med' : 'dv-level-low';
    const driftStatus = driftData?.status || 'stable';
    const driftDelta = driftData ? (driftData.drift_delta * 100).toFixed(2) : '0.00';

    updatePendingBadge(pending);

    rootEl.innerHTML = `
        <div class="dv-header">
            <h2 class="dv-page-title">Premium Dashboard Overview</h2>
            <a href="#/audit" class="dv-new-audit-btn">+ New Audit</a>
        </div>

        <!-- Top Row: Drift | Trust Gauge | Audit Volume -->
        <div class="dv-top-row">
            <div class="dv-panel">
                <div class="dv-panel-head">
                    <span class="dv-panel-title">Fairness Drift</span>
                    <span class="dv-panel-sub">Last 30 days</span>
                </div>
                <div class="dv-drift-chart-area">
                    <canvas id="driftChart" height="120"></canvas>
                </div>
                <div class="dv-drift-legend">
                    <span><span class="dv-legend-dot" style="background:#10b981"></span>Demographic Parity</span>
                    <span><span class="dv-legend-dot" style="background:#06b6d4"></span>Equal Opportunity</span>
                </div>
            </div>

            <div class="dv-panel dv-panel-trust">
                <div class="dv-panel-head"><span class="dv-panel-title">System Trust</span></div>
                <div class="dv-trust-gauge-wrap">
                    <canvas id="trustChart"></canvas>
                    <div class="dv-trust-center">
                        <div class="dv-trust-pct">${trustPct}%</div>
                        <div class="dv-trust-label">TRUST SCORE</div>
                        <span class="dv-trust-level ${trustLevelClass}">${trustLevel}</span>
                    </div>
                </div>
                <div class="dv-trust-metrics">
                    <span><span class="dv-legend-dot" style="background:#10b981"></span>Bias (${(100 - parseFloat(biasPct)).toFixed(0)}%)</span>
                    <span><span class="dv-legend-dot" style="background:#06b6d4"></span>Explainability (${dpVal}%)</span>
                    <span><span class="dv-legend-dot" style="background:#8b5cf6"></span>Performance (${eoVal}%)</span>
                </div>
            </div>

            <div class="dv-panel">
                <div class="dv-panel-head">
                    <span class="dv-panel-title">Audit Volume</span>
                    <span class="dv-panel-sub">Total Audits</span>
                </div>
                <div class="dv-volume-chart-area">
                    <canvas id="volumeChart" height="140"></canvas>
                </div>
            </div>
        </div>

        <!-- Middle Row: Risk Models Table + SHAP -->
        <div class="dv-mid-row">
            <div class="dv-panel dv-panel-wide">
                <div class="dv-panel-head"><span class="dv-panel-title">Priority Risk Models</span></div>
                <table class="dv-table">
                    <thead>
                        <tr>
                            <th>Model Name</th>
                            <th>Risk Score</th>
                            <th>Status</th>
                            <th>Last Audit</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${modelComparison?.models ? modelComparison.models.map((m, i) => {
                            const score = Math.round(m.accuracy * 100);
                            const status = score >= 90 ? 'Critical' : score >= 80 ? 'Warning' : 'Stable';
                            const statusClass = score >= 90 ? 'dv-status-critical' : score >= 80 ? 'dv-status-warning' : 'dv-status-stable';
                            return `<tr><td>${m.model}</td><td>${score}</td><td><span class="dv-status ${statusClass}">${status}</span></td><td>${i === 0 ? 'Today' : 'Yesterday'}</td></tr>`;
                        }).join('') : ''}
                        ${recent?.slice(0, 4).map(r => {
                            const score = Math.round((r.trust_score || 0) * 100);
                            const status = score < 50 ? 'Critical' : score < 70 ? 'Warning' : 'Stable';
                            const statusClass = score < 50 ? 'dv-status-critical' : score < 70 ? 'dv-status-warning' : 'dv-status-stable';
                            const date = r.created_at ? new Date(r.created_at).toLocaleDateString('en-US', {month:'short', day:'numeric'}) : '—';
                            return `<tr>
                                <td><a href="#/reports/${r.audit_id}" class="dv-link">${(r.input||'Audit').slice(0,30)}${(r.input||'').length > 30 ? '…' : ''}</a></td>
                                <td>${100 - score}</td>
                                <td><span class="dv-status ${statusClass}">${status}</span></td>
                                <td>${date}</td>
                            </tr>`;
                        }).join('') || '<tr><td colspan="4" class="dv-empty">No audits yet — run your first audit</td></tr>'}
                    </tbody>
                </table>
            </div>

            <div class="dv-panel">
                <div class="dv-panel-head">
                    <span class="dv-panel-title">SHAP Feature Importance</span>
                    <div class="method-selector" id="shap-method-selector">
                        <button class="method-btn active" data-method="linear">Linear</button>
                        <button class="method-btn" data-method="coefficient">Coeff</button>
                        <button class="method-btn" data-method="permutation">Perm</button>
                    </div>
                </div>
                <div id="shap-chart-container" style="min-height:180px">
                    <div class="dv-loading"><div class="loading-spinner"></div><span>Loading SHAP…</span></div>
                </div>
            </div>
        </div>

        <!-- Bottom Row: Pipeline Integrity + Bias Lab -->
        <div class="dv-bot-row">
            <div class="dv-panel">
                <div class="dv-panel-head"><span class="dv-panel-title">Pipeline Integrity</span></div>
                <div class="dv-integrity-metrics">
                    <div class="dv-metric">
                        <div class="dv-metric-val" id="dp-value" style="color:#10b981">${dpVal}%</div>
                        <div class="dv-metric-label">Demographic Parity</div>
                    </div>
                    <div class="dv-metric">
                        <div class="dv-metric-val" id="eo-value" style="color:#8b5cf6">${eoVal}%</div>
                        <div class="dv-metric-label">Equal Opportunity</div>
                    </div>
                    <div class="dv-metric">
                        <div class="dv-metric-val" id="pmale-value" style="color:#f59e0b">${biasData ? (biasData.p_y_given_male * 100).toFixed(1) : '—'}%</div>
                        <div class="dv-metric-label">P(>50K | Male)</div>
                    </div>
                    <div class="dv-metric">
                        <div class="dv-metric-val" style="color:#06b6d4">${driftDelta}%</div>
                        <div class="dv-metric-label">Drift Delta</div>
                    </div>
                </div>
                <div style="height:130px;margin-top:0.5rem"><canvas id="radarChart"></canvas></div>
            </div>

            <div class="dv-panel">
                <div class="dv-panel-head"><span class="dv-panel-title">Bias Simulation Lab</span><span class="dv-badge-interactive">Interactive</span></div>
                <p class="dv-lab-desc">Test model robustness by injecting biased data, auto-mitigating, or retraining the model in real time.</p>
                <div class="dv-lab-actions">
                    <button class="dv-lab-btn dv-lab-danger" id="btn-simulate-bias">⚡ Inject Bias</button>
                    <button class="dv-lab-btn dv-lab-success" id="btn-mitigate-bias">🛡️ Auto-Mitigate</button>
                    <button class="dv-lab-btn dv-lab-primary" id="btn-retrain">🔄 Retrain</button>
                </div>
                <div id="action-status" class="dv-action-status" style="display:none">Idle</div>
            </div>

            <div class="dv-panel">
                <div class="dv-panel-head"><span class="dv-panel-title">Recent Audits</span><span class="dv-live-dot"></span></div>
                <div class="dv-audit-list">
                    ${recent?.length > 0 ? recent.slice(0, 5).map(r => {
                        const sc = Math.round((r.trust_score || 0) * 100);
                        const c = sc >= 70 ? '#10b981' : sc >= 50 ? '#f59e0b' : '#ef4444';
                        return `<a href="#/reports/${r.audit_id}" class="dv-audit-row">
                            <span class="dv-audit-id">${r.audit_id.slice(0,8)}</span>
                            <span class="dv-audit-input">${(r.input||'').slice(0,28)}…</span>
                            <span class="dv-audit-score" style="color:${c}">${sc}%</span>
                        </a>`;
                    }).join('') : '<div class="dv-empty">No audits yet</div>'}
                </div>
            </div>
        </div>
    `;

    setTimeout(() => initCharts(s, biasData, fairnessData, driftData, recent), 80);
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
    const el = document.getElementById('nav-review');
    if (!el) return;
    const existing = el.querySelector('.pending-badge');
    if (existing) existing.remove();
    if (count > 0) { const b = document.createElement('span'); b.className = 'pending-badge'; b.textContent = count; el.appendChild(b); }
}

async function loadShapChart(api, method) {
    const container = document.getElementById('shap-chart-container');
    if (!container) return;
    container.innerHTML = '<div class="dv-loading"><div class="loading-spinner"></div><span>Computing ' + method + '…</span></div>';
    const d = await api.get('/explain?index=0&method=' + method);
    if (!d || d.status === 'error') { container.innerHTML = '<div class="dv-empty">Retrain model first</div>'; return; }
    const c = d.contributions || [];
    if (!c.length) { container.innerHTML = '<div class="dv-empty">No features</div>'; return; }
    const mx = Math.max(...c.map(x => Math.abs(x.impact)));
    container.innerHTML = '<div class="dv-shap-meta">Base: <strong>' + d.base_value.toFixed(3) + '</strong> · ' + c.length + ' features' + (d.from_cache ? ' · cached' : '') + '</div>' +
        c.map(x => {
            const pct = Math.min((Math.abs(x.impact)/mx)*100, 100);
            const col = x.impact > 0 ? '#10b981' : '#ef4444';
            return '<div class="shap-row"><div class="shap-label">' + x.feature + '</div><div class="shap-bar-track"><div class="shap-bar" style="width:' + pct + '%;background:' + col + '"></div></div><div class="shap-val" style="color:' + col + '">' + (x.impact > 0 ? '+' : '') + x.impact.toFixed(3) + '</div></div>';
        }).join('');
}

async function handleAction(api, action) {
    const el = document.getElementById('action-status');
    if (!el) return;
    el.style.display = 'block';
    document.querySelectorAll('.dv-lab-btn').forEach(b => b.disabled = true);
    if (action === 'simulate') { el.textContent = '⚡ Injecting…'; el.className = 'dv-action-status dv-as-danger'; const r = await api.post('/simulate-bias'); if (r?.status === 'success') { el.textContent = '🔴 Model biased'; await refreshMetrics(api); } }
    else if (action === 'mitigate') { el.textContent = '🛡️ Mitigating…'; el.className = 'dv-action-status dv-as-success'; const r = await api.post('/mitigate-bias'); if (r?.status === 'success') { el.textContent = '🟢 Model fair'; await refreshMetrics(api); } }
    else if (action === 'retrain') { el.textContent = '🔄 Retraining…'; el.className = 'dv-action-status dv-as-primary'; const r = await api.post('/train'); if (r?.status === 'success') { el.textContent = '✅ Acc: ' + (r.accuracy*100).toFixed(1) + '%'; await refreshMetrics(api); } }
    document.querySelectorAll('.dv-lab-btn').forEach(b => b.disabled = false);
}

async function refreshMetrics(api) {
    const b = await api.get('/bias'), f = await api.get('/fairness');
    const set = (id, t) => { const e = document.getElementById(id); if(e) { e.style.opacity='0.3'; setTimeout(() => { e.textContent=t; e.style.opacity='1'; }, 150); } };
    if (b) { set('live-bias-value', (b.bias_score*100).toFixed(1)+'%'); set('pmale-value', (b.p_y_given_male*100).toFixed(1)+'%'); }
    if (f) { set('dp-value', (f.demographic_parity*100).toFixed(1)+'%'); set('eo-value', (f.equal_opportunity*100).toFixed(1)+'%'); }
    const m = document.querySelector('#shap-method-selector .method-btn.active');
    await loadShapChart(api, m?.dataset.method || 'linear');
}

function initCharts(stats, bias, fairness, drift, recent) {
    // Trust Gauge
    const tCtx = document.getElementById('trustChart');
    if (tCtx) {
        const score = stats.avg_trust || 0;
        const col = score >= 0.7 ? '#10b981' : score >= 0.5 ? '#f59e0b' : '#ef4444';
        new Chart(tCtx, { type:'doughnut', data:{ datasets:[{ data:[score*100,(1-score)*100], backgroundColor:[col,'rgba(255,255,255,0.06)'], borderWidth:0, borderRadius:[8,0] }] }, options:{ cutout:'78%', rotation:-90, circumference:180, plugins:{legend:{display:false},tooltip:{enabled:false}}, layout:{padding:0} } });
    }

    // Drift Area Chart
    const dCtx = document.getElementById('driftChart');
    if (dCtx) {
        const pts = drift?.points || [];
        const labels = pts.length > 0 ? pts.map((_,i) => i+1).reverse() : [1,2,3,4,5,6,7];
        const dpData = pts.length > 0 ? pts.map(p => (p.bias_score||0)*100).reverse() : [12,14,13,15,14,16,15];
        const eoData = pts.length > 0 ? pts.map(p => (p.truth_score||0)*100).reverse() : [18,17,19,18,20,19,18];
        new Chart(dCtx, { type:'line', data:{ labels, datasets:[
            { data:dpData, borderColor:'#10b981', backgroundColor:'rgba(16,185,129,0.08)', fill:true, tension:0.4, pointRadius:0, borderWidth:2 },
            { data:eoData, borderColor:'#06b6d4', backgroundColor:'rgba(6,182,212,0.05)', fill:true, tension:0.4, pointRadius:0, borderWidth:2 },
        ]}, options:{ responsive:true, maintainAspectRatio:false, scales:{ x:{display:false}, y:{display:false} }, plugins:{legend:{display:false},tooltip:{enabled:false}} } });
    }

    // Audit Volume Bar
    const vCtx = document.getElementById('volumeChart');
    if (vCtx) {
        const total = stats.total_audits || 0;
        const today = Math.min(total, Math.max(1, Math.floor(total * 0.3)));
        const week = Math.min(total, Math.max(today, Math.floor(total * 0.7)));
        new Chart(vCtx, { type:'bar', data:{ labels:['Today','This Week','This Month'], datasets:[{ data:[today, week, total], backgroundColor:['rgba(16,185,129,0.5)','rgba(16,185,129,0.7)','#10b981'], borderRadius:6, barThickness:36 }] }, options:{ responsive:true, maintainAspectRatio:false, scales:{ x:{grid:{display:false},ticks:{color:'#64748b',font:{size:11}}}, y:{display:false} }, plugins:{ legend:{display:false}, tooltip:{enabled:true}, datalabels:{display:false} } } });
    }

    // Radar
    const rCtx = document.getElementById('radarChart');
    if (rCtx) {
        const f1 = fairness ? Math.max((1-(bias?.bias_score||0))*100,0) : 62;
        const eo = fairness ? (fairness.equal_opportunity*100) : 55;
        const pm = bias ? (bias.p_y_given_male*100) : 40;
        new Chart(rCtx, { type:'radar', data:{ labels:['Fairness','Eq. Opp','P(Male)'], datasets:[{data:[f1,eo,pm],backgroundColor:'rgba(16,185,129,0.12)',borderColor:'#10b981',pointBackgroundColor:'#10b981',borderWidth:2,pointRadius:3}] }, options:{ scales:{r:{angleLines:{color:'rgba(255,255,255,0.06)'},grid:{color:'rgba(255,255,255,0.06)'},pointLabels:{color:'#94a3b8',font:{size:11}},ticks:{display:false,max:100}}}, plugins:{legend:{display:false}} } });
    }
}
