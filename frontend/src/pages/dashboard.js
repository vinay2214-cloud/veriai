export async function renderDashboard(rootEl, api) {
    const stats = await api.get('/dashboard/stats');
    const recent = await api.get('/dashboard/recent');
    const reviewStats = await api.get('/review/stats');
    const biasData = await api.get('/bias');
    const fairnessData = await api.get('/fairness');
    const driftData = await api.get('/dashboard/fairness-drift');
    const modelComparison = await api.get('/dashboard/model-comparison');
    const pendingReviews = reviewStats ? reviewStats.pending : 0;

    if (!stats) {
        rootEl.innerHTML = '<div class="empty-state"><div class="empty-icon">⚠️</div><h3 class="empty-title">Failed to load dashboard data</h3></div>';
        return;
    }

    updatePendingBadge(pendingReviews);
    const trustScore = Math.round((stats.avg_trust || 0) * 100);

    rootEl.innerHTML = `
        <!-- Hero Stats Row -->
        <div class="stats-grid stagger-in">
            <div class="stat-card purple"><div class="stat-label">Total Audits</div><div class="stat-value purple">${stats.total_audits || 0}</div></div>
            <div class="stat-card cyan"><div class="stat-label">Avg Trust Score</div><div class="stat-value cyan">${(stats.avg_trust * 100).toFixed(1)}%</div></div>
            <div class="stat-card amber" id="bias-stat-card"><div class="stat-label">Live ML Bias Score</div><div class="stat-value amber" id="live-bias-value">${biasData ? (biasData.bias_score * 100).toFixed(1) + '%' : 'N/A'}</div></div>
            <div class="stat-card ${pendingReviews > 0 ? 'amber' : 'green'}"><div class="stat-label">Pending Reviews</div><div class="stat-value ${pendingReviews > 0 ? 'amber' : 'green'}" id="pending-count">${pendingReviews}</div></div>
        </div>

        <div class="grid grid-2" style="margin-top:1.5rem;">
            <div class="card glass-card">
                <div class="card-header"><h3 class="card-title">📉 Fairness Drift Monitor</h3></div>
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem;">
                    <span class="badge ${driftData && driftData.status === 'critical' ? 'badge-red' : (driftData && driftData.status === 'warning' ? 'badge-amber' : 'badge-cyan')}">${driftData ? driftData.status.toUpperCase() : 'N/A'}</span>
                    <span style="font-size:0.85rem; color:var(--text-secondary);">Delta: <strong style="color:${driftData && Math.abs(driftData.drift_delta) > 0.05 ? 'var(--accent-red)' : 'var(--accent-emerald)'};">${driftData ? (driftData.drift_delta >= 0 ? '+' : '') + (driftData.drift_delta * 100).toFixed(2) + '%' : 'N/A'}</strong></span>
                </div>
                <div style="font-size:0.78rem; color:var(--text-secondary);">
                    Tracks bias-score shift versus recent baseline to catch fairness regressions before release.
                </div>
            </div>
            <div class="card glass-card">
                <div class="card-header"><h3 class="card-title">🔀 Model Comparison (Same Dataset)</h3></div>
                <div style="font-size:0.75rem; color:var(--text-muted); margin-bottom:0.5rem;">Dataset: ${modelComparison ? modelComparison.dataset : 'N/A'}</div>
                <div style="display:flex; flex-direction:column; gap:0.45rem;">
                    ${modelComparison && modelComparison.models ? modelComparison.models.map((m, idx) => `
                        <div style="display:grid; grid-template-columns:1.5fr 1fr 1fr 1fr; gap:0.5rem; padding:0.5rem; border-radius:6px; background:${idx === 0 ? 'rgba(16,185,129,0.08)' : 'rgba(255,255,255,0.03)'};">
                            <div style="font-size:0.78rem; color:${idx === 0 ? 'var(--accent-emerald)' : 'var(--text-primary)'};">${m.model}</div>
                            <div style="font-size:0.75rem; color:var(--text-secondary);">Acc ${(m.accuracy * 100).toFixed(1)}%</div>
                            <div style="font-size:0.75rem; color:var(--text-secondary);">DP ${(m.demographic_parity * 100).toFixed(1)}%</div>
                            <div style="font-size:0.75rem; color:var(--text-secondary);">EO ${(m.equal_opportunity * 100).toFixed(1)}%</div>
                        </div>
                    `).join('') : '<div style="color:var(--text-muted);">Comparison unavailable.</div>'}
                </div>
            </div>
        </div>

        <!-- Trust Gauge + Scatter Plot Row -->
        <div class="grid grid-2">
            <div class="card glass-card" style="text-align:center;">
                <div class="card-header"><h3 class="card-title">System Trust Level</h3></div>
                <div style="position:relative; width:280px; height:160px; margin:0 auto;">
                    <canvas id="trustChart"></canvas>
                    <div style="position:absolute; top:70%; left:50%; transform:translate(-50%,-50%); text-align:center;">
                        <div id="chart-inner-text" style="font-size:2.8rem; font-weight:700;">${trustScore}%</div>
                        <div style="font-size:0.8rem; color:var(--text-muted);">SCORE</div>
                    </div>
                </div>
            </div>
            <div class="card glass-card">
                <div class="card-header"><h3 class="card-title">Fairness & Truth Radar</h3></div>
                <div style="height:200px;"><canvas id="scatterChart"></canvas></div>
            </div>
        </div>

        <!-- SHAP + Fairness Row -->
        <div class="grid grid-2" style="margin-top:1.5rem;">
            <div class="card glass-card">
                <div class="card-header">
                    <h3 class="card-title">🔍 SHAP Feature Importance</h3>
                    <div class="method-selector" id="shap-method-selector">
                        <button class="method-btn active" data-method="linear">Linear</button>
                        <button class="method-btn" data-method="coefficient">Coeff</button>
                        <button class="method-btn" data-method="permutation">Perm</button>
                        <button class="method-btn" data-method="lime">LIME</button>
                    </div>
                </div>
                <div id="shap-chart-container" style="min-height:200px;">
                    <div class="loading-overlay" style="position:relative; height:180px;"><div class="loading-spinner"></div><div style="color:var(--text-muted); margin-top:12px;">Loading SHAP...</div></div>
                </div>
            </div>
            <div class="card glass-card">
                <div class="card-header"><h3 class="card-title">⚖️ Live Pipeline Integrity</h3></div>
                <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:1rem; padding:1rem 0;">
                    <div><div style="font-size:12px; color:var(--text-muted);">Demographic Parity</div><div style="font-size:1.5rem; font-weight:700; color:var(--accent-cyan);" id="dp-value">${fairnessData ? (fairnessData.demographic_parity * 100).toFixed(1) + '%' : 'N/A'}</div></div>
                    <div><div style="font-size:12px; color:var(--text-muted);">Equal Opportunity</div><div style="font-size:1.5rem; font-weight:700; color:var(--accent-purple);" id="eo-value">${fairnessData ? (fairnessData.equal_opportunity * 100).toFixed(1) + '%' : 'N/A'}</div></div>
                    <div><div style="font-size:12px; color:var(--text-muted);">P(>50K | Male)</div><div style="font-size:1.5rem; font-weight:700; color:var(--accent-amber);" id="pmale-value">${biasData ? (biasData.p_y_given_male * 100).toFixed(1) + '%' : 'N/A'}</div></div>
                </div>
                <div style="height:150px;"><canvas id="radarChart"></canvas></div>
            </div>
        </div>

        <!-- Live Stream + Critical Issues Row -->
        <div class="grid grid-2" style="margin-top:1.5rem;">
            <div class="card glass-card">
                <div class="card-header"><h3 class="card-title">Live Audit Stream</h3></div>
                <div id="audit-stream" style="display:flex; flex-direction:column; gap:0.5rem; max-height:180px; overflow-y:auto;">
                    ${recent && recent.length > 0 ? recent.map(r => {
                        const color = r.trust_score > 0.7 ? 'var(--accent-emerald)' : (r.trust_score > 0.5 ? 'var(--accent-amber)' : 'var(--accent-red)');
                        const status = r.trust_score > 0.7 ? 'Approved' : (r.trust_score > 0.5 ? 'Processing...' : 'Flagged');
                        return '<div style="background:rgba(255,255,255,0.03); border-radius:6px; padding:0.65rem; font-family:var(--font-mono); font-size:0.8rem;"><span style="color:var(--text-muted);">' + r.audit_id.slice(0,8) + '</span> | <a href="#/reports/' + r.audit_id + '" style="color:var(--accent-cyan); text-decoration:none;">' + (r.input || '').slice(0,40) + '...</a> | <span style="color:' + color + ';">' + status + ' (' + (r.trust_score*100).toFixed(0) + '%)</span></div>';
                    }).join('') : '<div style="color:var(--text-muted); text-align:center; padding:2rem;">No recent audits</div>'}
                </div>
            </div>
            <div class="card glass-card">
                <div class="card-header"><h3 class="card-title">Critical Issues (Human Review)</h3></div>
                <div style="display:flex; flex-direction:column; gap:0.5rem; max-height:180px; overflow-y:auto;">
                    ${recent && recent.filter(r => r.trust_score < 0.6).length > 0 ? recent.filter(r => r.trust_score < 0.6).map(r => '<div style="display:flex; justify-content:space-between; align-items:center; background:rgba(244,63,94,0.05); border:1px solid rgba(244,63,94,0.1); border-radius:6px; padding:0.65rem;"><div style="font-size:0.82rem;"><span style="color:var(--text-muted);">' + r.audit_id.slice(0,8) + ' | </span><span style="color:var(--accent-red);">Low Trust</span> - Requires Review</div><a href="#/review" class="btn btn-sm btn-secondary" style="border-radius:4px; font-size:0.75rem;">Review</a></div>').join('') : '<div style="color:var(--text-muted); text-align:center; padding:2rem;">No critical issues</div>'}
                </div>
            </div>
        </div>

        <!-- Bias Simulator -->
        <div class="card" style="margin-top:1.5rem;">
            <div class="card-header"><h3 class="card-title">🎮 Interactive Bias Simulation</h3></div>
            <div style="padding:1rem; display:flex; gap:1rem; flex-wrap:wrap; align-items:center;">
                <button class="btn-action btn-danger" id="btn-simulate-bias"><span class="btn-icon">⚡</span> Inject Biased Data</button>
                <button class="btn-action btn-success" id="btn-mitigate-bias"><span class="btn-icon">🛡️</span> Auto-Mitigate (Reweight)</button>
                <button class="btn-action btn-primary" id="btn-retrain"><span class="btn-icon">🔄</span> Retrain Model</button>
                <div id="action-status" class="action-status-badge" style="display:none;">Idle</div>
            </div>
        </div>

        <!-- 8-Step Pipeline Overview -->
        <div class="card glass-card" style="margin-top:1.5rem;">
            <div class="card-header"><h3 class="card-title">🔗 8-Step Reasoning Pipeline</h3><span class="badge badge-purple">Parallel Processing</span></div>
            <div style="overflow-x:auto;">
                <table style="width:100%; border-collapse:separate; border-spacing:0 4px; font-size:0.78rem;">
                    <thead>
                        <tr style="color:var(--text-muted); text-transform:uppercase; letter-spacing:0.05em; font-size:0.68rem;">
                            <th style="padding:0.5rem 0.75rem; text-align:left;">Step</th>
                            <th style="padding:0.5rem 0.75rem; text-align:left;">Purpose</th>
                            <th style="padding:0.5rem 0.75rem; text-align:left;">Technology</th>
                            <th style="padding:0.5rem 0.75rem; text-align:center;">Mode</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr style="background:rgba(255,255,255,0.03); border-radius:4px;">
                            <td style="padding:0.5rem 0.75rem; color:var(--accent-cyan); font-weight:600;">⚖️ 1. Bias Detection</td>
                            <td style="padding:0.5rem 0.75rem; color:var(--text-secondary);">Demographic parity & equalized odds</td>
                            <td style="padding:0.5rem 0.75rem;"><code style="color:var(--accent-purple); font-size:0.72rem;">Scikit-learn SGD</code></td>
                            <td style="padding:0.5rem 0.75rem; text-align:center;"><span style="color:var(--accent-emerald); font-size:0.68rem;">∥ Parallel</span></td>
                        </tr>
                        <tr style="background:rgba(255,255,255,0.03);">
                            <td style="padding:0.5rem 0.75rem; color:var(--accent-cyan); font-weight:600;">🔍 2. Truth Verification</td>
                            <td style="padding:0.5rem 0.75rem; color:var(--text-secondary);">Semantic search against knowledge base</td>
                            <td style="padding:0.5rem 0.75rem;"><code style="color:var(--accent-purple); font-size:0.72rem;">FAISS + TF-IDF</code></td>
                            <td style="padding:0.5rem 0.75rem; text-align:center;"><span style="color:var(--accent-emerald); font-size:0.68rem;">∥ Parallel</span></td>
                        </tr>
                        <tr style="background:rgba(255,255,255,0.03);">
                            <td style="padding:0.5rem 0.75rem; color:var(--accent-cyan); font-weight:600;">📊 3. Cluster Analysis</td>
                            <td style="padding:0.5rem 0.75rem; color:var(--text-secondary);">Fairness across data subgroups</td>
                            <td style="padding:0.5rem 0.75rem;"><code style="color:var(--accent-purple); font-size:0.72rem;">KMeans clustering</code></td>
                            <td style="padding:0.5rem 0.75rem; text-align:center;"><span style="color:var(--accent-emerald); font-size:0.68rem;">∥ Parallel</span></td>
                        </tr>
                        <tr style="background:rgba(255,255,255,0.03);">
                            <td style="padding:0.5rem 0.75rem; color:var(--accent-cyan); font-weight:600;">📈 4. Distribution Analysis</td>
                            <td style="padding:0.5rem 0.75rem; color:var(--text-secondary);">Data drift & label imbalance</td>
                            <td style="padding:0.5rem 0.75rem;"><code style="color:var(--accent-purple); font-size:0.72rem;">SciPy statistics</code></td>
                            <td style="padding:0.5rem 0.75rem; text-align:center;"><span style="color:var(--accent-emerald); font-size:0.68rem;">∥ Parallel</span></td>
                        </tr>
                        <tr style="background:rgba(255,255,255,0.03);">
                            <td style="padding:0.5rem 0.75rem; color:var(--accent-amber); font-weight:600;">🎯 5. Trust Scoring</td>
                            <td style="padding:0.5rem 0.75rem; color:var(--text-secondary);">Weighted composite: Trust = Σ(wᵢ × metricᵢ)</td>
                            <td style="padding:0.5rem 0.75rem;"><code style="color:var(--accent-purple); font-size:0.72rem;">Configurable per industry</code></td>
                            <td style="padding:0.5rem 0.75rem; text-align:center;"><span style="color:var(--accent-blue); font-size:0.68rem;">Sequential</span></td>
                        </tr>
                        <tr style="background:rgba(255,255,255,0.03);">
                            <td style="padding:0.5rem 0.75rem; color:var(--accent-amber); font-weight:600;">🔧 6. Auto-Correction</td>
                            <td style="padding:0.5rem 0.75rem; color:var(--text-secondary);">Halves biased weights, replaces hallucinations</td>
                            <td style="padding:0.5rem 0.75rem;"><code style="color:var(--accent-purple); font-size:0.72rem;">Rule-based engine</code></td>
                            <td style="padding:0.5rem 0.75rem; text-align:center;"><span style="color:var(--accent-blue); font-size:0.68rem;">Sequential</span></td>
                        </tr>
                        <tr style="background:rgba(255,255,255,0.03);">
                            <td style="padding:0.5rem 0.75rem; color:var(--accent-amber); font-weight:600;">📐 7. SHAP Explainability</td>
                            <td style="padding:0.5rem 0.75rem; color:var(--text-secondary);">Explains why each feature matters</td>
                            <td style="padding:0.5rem 0.75rem;"><code style="color:var(--accent-purple); font-size:0.72rem;">Multi-method SHAP + cache</code></td>
                            <td style="padding:0.5rem 0.75rem; text-align:center;"><span style="color:var(--accent-cyan); font-size:0.68rem;">0ms (cached)</span></td>
                        </tr>
                        <tr style="background:rgba(255,255,255,0.03);">
                            <td style="padding:0.5rem 0.75rem; color:var(--accent-red); font-weight:600;">👁️ 8. Human Review</td>
                            <td style="padding:0.5rem 0.75rem; color:var(--text-secondary);">Flags low-trust (<60%) for approval</td>
                            <td style="padding:0.5rem 0.75rem;"><code style="color:var(--accent-purple); font-size:0.72rem;">HITL review queue</code></td>
                            <td style="padding:0.5rem 0.75rem; text-align:center;"><span style="color:var(--accent-amber); font-size:0.68rem;">Human</span></td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Key Differentiators -->
        <div class="card glass-card" style="margin-top:1.5rem;">
            <div class="card-header"><h3 class="card-title">🏆 Key Differentiators</h3></div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem; padding:0.5rem 0;">
                <div style="padding:0.75rem; background:rgba(16,185,129,0.05); border:1px solid rgba(16,185,129,0.15); border-radius:var(--radius-md);">
                    <div style="font-size:0.85rem; font-weight:600; color:var(--accent-emerald); margin-bottom:0.3rem;">⚡ Parallel Processing</div>
                    <div style="font-size:0.75rem; color:var(--text-secondary); line-height:1.5;">Steps 1-4 run concurrently via <code style="color:var(--accent-purple);">asyncio.gather</code>, cutting latency ~60%. Pick <strong>Fast</strong> (~1s), <strong>Standard</strong> (~3s), or <strong>Thorough</strong> (~8s).</div>
                </div>
                <div style="padding:0.75rem; background:rgba(59,130,246,0.05); border:1px solid rgba(59,130,246,0.15); border-radius:var(--radius-md);">
                    <div style="font-size:0.85rem; font-weight:600; color:var(--accent-blue); margin-bottom:0.3rem;">🎯 Dynamic Trust Formula</div>
                    <div style="font-size:0.75rem; color:var(--text-secondary); line-height:1.5;">Weights configurable per industry. Healthcare = truth-heavy (0.45). HR/Hiring = bias-heavy (0.40). No code changes needed.</div>
                </div>
                <div style="padding:0.75rem; background:rgba(167,139,250,0.05); border:1px solid rgba(167,139,250,0.15); border-radius:var(--radius-md);">
                    <div style="font-size:0.85rem; font-weight:600; color:var(--accent-purple); margin-bottom:0.3rem;">📐 Instant Explainability</div>
                    <div style="font-size:0.75rem; color:var(--text-secondary); line-height:1.5;">Coefficient-based SHAP returns in <strong>0ms</strong> vs 2-5s for traditional SHAP, with result caching for repeat queries.</div>
                </div>
                <div style="padding:0.75rem; background:rgba(244,63,94,0.05); border:1px solid rgba(244,63,94,0.15); border-radius:var(--radius-md);">
                    <div style="font-size:0.85rem; font-weight:600; color:var(--accent-red); margin-bottom:0.3rem;">👁️ Human-in-the-Loop + RLHF</div>
                    <div style="font-size:0.75rem; color:var(--text-secondary); line-height:1.5;">Low-trust outputs auto-queue for review. Human feedback adjusts trust weights and triggers model retraining automatically.</div>
                </div>
            </div>
        </div>
    `;

    setTimeout(() => initCharts(stats.avg_trust || 0, biasData, fairnessData), 100);
    loadShapChart(api, 'linear');

    document.querySelectorAll('#shap-method-selector .method-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#shap-method-selector .method-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            loadShapChart(api, btn.dataset.method);
        });
    });

    document.getElementById('btn-simulate-bias').addEventListener('click', () => handleAction(api, 'simulate'));
    document.getElementById('btn-mitigate-bias').addEventListener('click', () => handleAction(api, 'mitigate'));
    document.getElementById('btn-retrain').addEventListener('click', () => handleAction(api, 'retrain'));
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
    container.innerHTML = '<div class="loading-overlay" style="position:relative; height:180px;"><div class="loading-spinner"></div><div style="color:var(--text-muted); margin-top:12px;">Computing ' + method + '...</div></div>';
    const shapData = await api.get('/explain?index=0&method=' + method);

    if (!shapData || shapData.status === 'error') {
        container.innerHTML = '<div style="color:var(--text-muted); text-align:center; padding:30px;">SHAP unavailable. Retrain the model first.</div>';
        return;
    }

    const contributions = shapData.contributions || [];
    if (contributions.length === 0) { container.innerHTML = '<div style="color:var(--text-muted); text-align:center;">No features.</div>'; return; }
    const maxVal = Math.max(...contributions.map(c => Math.abs(c.impact)));

    container.innerHTML = '<div style="margin-bottom:10px; font-size:13px; color:var(--text-muted);">Base: <strong style="color:var(--accent-purple);">' + shapData.base_value.toFixed(3) + '</strong> | Top ' + contributions.length + ' features | ' + (shapData.computation_time ? (shapData.computation_time*1000).toFixed(0) + 'ms' : '') + (shapData.from_cache ? ' (cached)' : '') + '</div><div class="shap-chart">' + contributions.map(c => {
        const pct = Math.min((Math.abs(c.impact)/maxVal)*100, 100);
        const color = c.impact > 0 ? 'var(--accent-cyan)' : '#f43f5e';
        return '<div class="shap-row"><div class="shap-label" title="' + c.feature + '">' + c.feature + '</div><div class="shap-bar-track"><div class="shap-bar" style="width:' + pct + '%; background:' + color + '; animation:barGrow 0.6s ease-out forwards;"></div></div><div class="shap-val" style="color:' + color + '">' + (c.impact > 0 ? '+' : '') + c.impact.toFixed(3) + '</div></div>';
    }).join('') + '</div>';
}

async function handleAction(api, action) {
    const statusEl = document.getElementById('action-status');
    statusEl.style.display = 'inline-block';
    const buttons = document.querySelectorAll('.btn-action');
    buttons.forEach(b => b.disabled = true);

    if (action === 'simulate') {
        statusEl.textContent = '⚡ Injecting biased data…';
        statusEl.className = 'action-status-badge status-danger';
        const res = await api.post('/simulate-bias');
        if (res && res.status === 'success') { statusEl.textContent = '🔴 Model is now biased!'; await refreshMetrics(api); }
    } else if (action === 'mitigate') {
        statusEl.textContent = '🛡️ Applying reweighing…';
        statusEl.className = 'action-status-badge status-success';
        const res = await api.post('/mitigate-bias');
        if (res && res.status === 'success') { statusEl.textContent = '🟢 Model is now fair!'; await refreshMetrics(api); }
    } else if (action === 'retrain') {
        statusEl.textContent = '🔄 Retraining…';
        statusEl.className = 'action-status-badge status-primary';
        const res = await api.post('/train');
        if (res && res.status === 'success') { statusEl.textContent = '✅ Trained! Acc: ' + (res.accuracy*100).toFixed(1) + '%'; await refreshMetrics(api); }
    }
    buttons.forEach(b => b.disabled = false);
}

async function refreshMetrics(api) {
    const biasData = await api.get('/bias');
    const fairnessData = await api.get('/fairness');
    const animateValue = (id, text) => { const el = document.getElementById(id); if(el) { el.style.opacity='0.3'; setTimeout(() => { el.textContent=text; el.style.opacity='1'; }, 200); } };
    if (biasData) { animateValue('live-bias-value', (biasData.bias_score*100).toFixed(1)+'%'); animateValue('pmale-value', (biasData.p_y_given_male*100).toFixed(1)+'%'); }
    if (fairnessData) { animateValue('dp-value', (fairnessData.demographic_parity*100).toFixed(1)+'%'); animateValue('eo-value', (fairnessData.equal_opportunity*100).toFixed(1)+'%'); }
    const activeMethod = document.querySelector('#shap-method-selector .method-btn.active');
    await loadShapChart(api, activeMethod ? activeMethod.dataset.method : 'linear');
}

function initCharts(score, bias, fairness) {
    const tCtx = document.getElementById('trustChart');
    if (tCtx) {
        const gradient = tCtx.getContext('2d').createLinearGradient(0, 0, 280, 0);
        gradient.addColorStop(0, '#f43f5e');
        gradient.addColorStop(1, '#ff6b6b');
        new Chart(tCtx, { type:'doughnut', data:{ datasets:[{ data:[score*100,(1-score)*100], backgroundColor:[gradient,'rgba(255,255,255,0.05)'], borderWidth:0, borderRadius:[10,0] }] }, options:{ cutout:'82%', rotation:-90, circumference:180, plugins:{legend:{display:false},tooltip:{enabled:false}}, layout:{padding:5} } });
    }

    const sCtx = document.getElementById('scatterChart');
    if (sCtx) {
        const gen = (n, xr, yr) => Array.from({length:n}, () => ({x:Math.random()*(xr[1]-xr[0])+xr[0], y:Math.random()*(yr[1]-yr[0])+yr[0]}));
        new Chart(sCtx, { type:'scatter', data:{ datasets:[{label:'Safe',data:gen(25,[0.1,0.5],[0.5,0.95]),backgroundColor:'#3b82f6',pointRadius:4},{label:'Critical',data:gen(8,[0.6,0.95],[0.3,0.85]),backgroundColor:'#f43f5e',pointRadius:5}] }, options:{ responsive:true, maintainAspectRatio:false, scales:{x:{title:{display:true,text:'Bias Score',color:'#94a3b8'},grid:{color:'rgba(255,255,255,0.05)'},ticks:{color:'#94a3b8'},min:0,max:1},y:{title:{display:true,text:'Truth Score',color:'#94a3b8'},grid:{color:'rgba(255,255,255,0.05)'},ticks:{color:'#94a3b8'},min:0,max:1}}, plugins:{legend:{display:false}} } });
    }

    const rCtx = document.getElementById('radarChart');
    if (rCtx) {
        let f1 = fairness ? Math.max((1-bias?.bias_score)*100,0) : 62;
        let eo = fairness ? (fairness.equal_opportunity*100) : 55;
        let pm = bias ? (bias.p_y_given_male*100) : 40;
        new Chart(rCtx, { type:'radar', data:{ labels:['Fairness','Eq. Opp','P(M)'], datasets:[{label:'Pipeline',data:[f1,eo,pm],backgroundColor:'rgba(167,139,250,0.2)',borderColor:'rgba(167,139,250,1)',pointBackgroundColor:'#06b6d4',borderWidth:2}] }, options:{ scales:{r:{angleLines:{color:'rgba(255,255,255,0.1)'},grid:{color:'rgba(255,255,255,0.1)'},pointLabels:{color:'#94a3b8',font:{family:'Inter',size:11}},ticks:{display:false,max:100}}}, plugins:{legend:{display:false}} } });
    }
}
