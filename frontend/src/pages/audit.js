import { escapeHtml } from '../utils.js';

export async function renderAuditPage(rootEl, api) {
    rootEl.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:1.5rem;">
            <div>
                <div style="font-size:0.8rem; color:var(--text-muted);">VeriAI > AI Trust & Safety Auditing Platform</div>
                <h2 style="font-size:1.4rem; font-weight:700;">Run AI Trust Audit</h2>
            </div>
            <div id="depth-control" style="display:flex; background:rgba(255,255,255,0.05); border-radius:var(--radius-md); border:1px solid rgba(255,255,255,0.1); overflow:hidden;">
                <button class="depth-btn" data-depth="fast" title="Bias + Truth only (~1s)" style="background:transparent; border:none; color:var(--text-secondary); padding:0.5rem 1rem; cursor:pointer; font-size:0.82rem;">⚡ Fast</button>
                <button class="depth-btn active" data-depth="standard" title="All 4 parallel checks (~3s)" style="background:rgba(59,130,246,0.2); border:none; color:var(--accent-blue); padding:0.5rem 1rem; cursor:pointer; font-size:0.82rem; border-left:1px solid rgba(255,255,255,0.1); border-right:1px solid rgba(255,255,255,0.1);">🔍 Standard</button>
                <button class="depth-btn" data-depth="thorough" title="Full pipeline + re-evaluation (~8s)" style="background:transparent; border:none; color:var(--text-secondary); padding:0.5rem 1rem; cursor:pointer; font-size:0.82rem;">🔬 Thorough</button>
            </div>
        </div>

        <!-- Depth Info -->
        <div id="depth-info" style="font-size:0.75rem; color:var(--accent-cyan); margin-bottom:1rem; padding:0.5rem 0.75rem; background:rgba(6,182,212,0.05); border:1px solid rgba(6,182,212,0.15); border-radius:var(--radius-md);">
            🔍 <strong>Standard</strong> — Steps 1-4 run in parallel via <code style="color:var(--accent-purple);">asyncio.gather</code> (~3s). Bias + Truth + Cluster + Distribution.
        </div>

        <!-- Audit Input -->
        <div class="card glass-card" style="margin-bottom:1.5rem;">
            <div class="card-header"><h3 class="card-title">Initiate AI Audit</h3><span class="badge badge-purple">8-Step Pipeline</span></div>

            <!-- Upload CSV Section -->
            <div style="margin-bottom:1rem; padding:1rem; background:rgba(167,139,250,0.05); border:1px solid rgba(167,139,250,0.2); border-radius:var(--radius-md);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.4rem;">
                    <div>
                        <div style="font-size:0.9rem; font-weight:600; color:var(--accent-purple);">📂 Upload Your Dataset (CSV)</div>
                        <div style="font-size:0.72rem; color:var(--text-muted); margin-top:0.2rem;">Upload a CSV to audit. System auto-detects features, labels, and protected attributes.</div>
                    </div>
                    <button class="btn" id="btn-upload-audit-csv" style="background:var(--accent-purple); color:white; font-size:0.82rem; white-space:nowrap;">📁 Choose CSV File</button>
                </div>
                <input type="file" id="audit-csv-input" accept=".csv" style="display:none;" />
                <div id="csv-upload-status" style="display:none;"></div>
            </div>

            <!-- OR divider -->
            <div style="text-align:center; font-size:0.72rem; color:var(--text-muted); margin-bottom:0.75rem; position:relative;">
                <span style="background:var(--bg-card); padding:0 0.75rem; position:relative; z-index:1;">OR enter text / JSON manually</span>
                <div style="position:absolute; top:50%; left:0; right:0; height:1px; background:rgba(255,255,255,0.08);"></div>
            </div>

            <div class="form-group">
                <label class="form-label">Input Payload (Text or JSON Dataset)</label>
                <textarea class="form-textarea" id="audit-input" placeholder='Enter a textual claim to verify for hallucinations, OR paste a JSON dataset to scan for bias.

Example text: "AI hiring tools treat all genders equally"
Example JSON: {"features": [[1,5,3,50],[0,2,4,30]], "labels": [1,0], "protected_index": 0}'></textarea>
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div style="font-size:0.82rem; color:var(--accent-purple);">Powered by <strong>Parallel Pipeline v2.0</strong> — Steps 1-4 run concurrently</div>
                <button class="btn btn-primary" id="run-audit-btn">→ Run Full Audit</button>
            </div>
        </div>

        <div class="card glass-card" style="margin-bottom:1.5rem;">
            <div class="card-header"><h3 class="card-title">Audit Real LLM Output</h3><span class="badge badge-cyan">Hallucination Detection</span></div>
            <div class="grid grid-2">
                <div class="form-group">
                    <label class="form-label">Model Name</label>
                    <input class="form-input" id="llm-model-name" value="gpt-4.1" />
                </div>
                <div class="form-group">
                    <label class="form-label">Prompt</label>
                    <input class="form-input" id="llm-prompt" placeholder="Enter the prompt sent to the LLM" />
                </div>
            </div>
            <div class="form-group">
                <label class="form-label">LLM Output</label>
                <textarea class="form-textarea" id="llm-output" placeholder="Paste LLM response output here"></textarea>
            </div>
            <div style="display:flex; gap:0.6rem; justify-content:flex-end; flex-wrap:wrap;">
                <button class="btn" id="btn-demo-scenario" style="background:var(--accent-purple); color:white;">▶ Run Demo Scenario</button>
                <button class="btn btn-primary" id="run-llm-audit-btn">Run LLM Output Audit</button>
            </div>
        </div>

        <!-- Results Container -->
        <div id="audit-results"></div>

        <!-- Static Explainability Section -->
        <div class="grid grid-2" style="margin-top:1.5rem;">
            <div class="card glass-card">
                <h3 class="card-title" style="margin-bottom:1rem;">SHAP Explainability</h3>
                <div style="font-size:0.82rem; text-align:center; color:var(--text-secondary); margin-bottom:0.75rem;">Feature Contribution to Prediction</div>
                <div id="shap-waterfall" style="display:flex; flex-direction:column; gap:0.4rem;"></div>
            </div>
            <div class="card glass-card">
                <h3 class="card-title" style="margin-bottom:1rem;">Demographic Parity</h3>
                <div style="font-size:0.82rem; text-align:center; color:var(--text-secondary); margin-bottom:0.5rem;">Fairness Across Groups (TPR)</div>
                <div style="height:200px;"><canvas id="parityChart"></canvas></div>
            </div>
        </div>

        <!-- Auto-Correction Example -->
        <h3 style="font-size:1.15rem; font-weight:600; margin:1.5rem 0 1rem;">VeriAI Auto-Correction (Step 6)</h3>
        <div class="grid grid-2">
            <div class="card glass-card" style="border-color:rgba(244,63,94,0.4); background:linear-gradient(145deg,rgba(244,63,94,0.05),rgba(10,14,26,0.7));">
                <h4 style="background:rgba(244,63,94,0.2); display:inline-block; padding:0.2rem 0.6rem; border-radius:4px; font-size:0.85rem; margin-bottom:0.75rem;">Original Output</h4>
                <p style="font-size:0.88rem; color:var(--text-secondary); line-height:1.6;">The applicant has a high probability of approval. However, due to their zip code and historical data for similar profiles, the system flags a potential risk. Recommended interest rate is 15%.</p>
                <div style="margin-top:1rem;"><span style="font-size:0.82rem; color:var(--accent-amber); font-weight:600;">⚠️ Bias Detected & Hallucination</span></div>
            </div>
            <div class="card glass-card" style="border-color:rgba(16,185,129,0.4); background:linear-gradient(145deg,rgba(16,185,129,0.05),rgba(10,14,26,0.7));">
                <h4 style="background:rgba(16,185,129,0.2); display:inline-block; padding:0.2rem 0.6rem; border-radius:4px; font-size:0.85rem; margin-bottom:0.75rem;">VeriAI Corrected Output</h4>
                <p style="font-size:0.88rem; color:var(--text-secondary); line-height:1.6;">The applicant has a high probability of approval based on credit score, income, and employment history. The system recommends an interest rate of 7.5%. Location data has been excluded to ensure fairness.</p>
                <div style="margin-top:1rem;"><span style="font-size:0.82rem; color:var(--accent-green); font-weight:600;">✓ Corrected, Unbiased & Verified</span></div>
            </div>
        </div>
    `;

    // CSV Upload Logic
    const csvInput = document.getElementById('audit-csv-input');
    const csvStatus = document.getElementById('csv-upload-status');
    document.getElementById('btn-upload-audit-csv').addEventListener('click', () => csvInput.click());

    csvInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        csvStatus.style.display = 'block';
        csvStatus.innerHTML = '<div style="font-size:0.78rem; color:var(--accent-cyan);">Uploading and parsing <strong>' + escapeHtml(file.name) + '</strong> (' + (file.size/1024).toFixed(1) + ' KB)...</div>';
        const uploadBtn = document.getElementById('btn-upload-audit-csv');
        uploadBtn.disabled = true;
        uploadBtn.textContent = '⏳ Parsing...';
        const formData = new FormData();
        formData.append('file', file);
        try {
            const data = await api.postForm('/upload-csv', formData);
            if (data && data.status === 'success' && data.dataset) {
                document.getElementById('audit-input').value = JSON.stringify(data.dataset, null, 2);
                csvStatus.innerHTML = '<div style="padding:0.75rem; background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.2); border-radius:6px; margin-top:0.5rem;">'
                    + '<div style="font-size:0.82rem; font-weight:600; color:var(--accent-emerald);">Dataset Loaded: ' + escapeHtml(file.name) + '</div>'
                    + '<div style="display:grid; grid-template-columns:repeat(4,1fr); gap:0.5rem; margin-top:0.5rem;">'
                    + '<div style="text-align:center; padding:0.4rem; background:rgba(255,255,255,0.03); border-radius:4px;"><div style="font-size:1rem; font-weight:700; color:var(--accent-cyan);">' + data.rows + '</div><div style="font-size:0.65rem; color:var(--text-muted);">Rows</div></div>'
                    + '<div style="text-align:center; padding:0.4rem; background:rgba(255,255,255,0.03); border-radius:4px;"><div style="font-size:1rem; font-weight:700; color:var(--accent-purple);">' + data.num_features + '</div><div style="font-size:0.65rem; color:var(--text-muted);">Features</div></div>'
                    + '<div style="text-align:center; padding:0.4rem; background:rgba(255,255,255,0.03); border-radius:4px;"><div style="font-size:1rem; font-weight:700; color:var(--accent-amber);">' + escapeHtml(data.label_column) + '</div><div style="font-size:0.65rem; color:var(--text-muted);">Label</div></div>'
                    + '<div style="text-align:center; padding:0.4rem; background:rgba(255,255,255,0.03); border-radius:4px;"><div style="font-size:1rem; font-weight:700; color:var(--accent-emerald);">' + escapeHtml(data.columns[0]) + '</div><div style="font-size:0.65rem; color:var(--text-muted);">Protected</div></div>'
                    + '</div>'
                    + '<div style="font-size:0.72rem; color:var(--text-muted); margin-top:0.5rem;">Columns: <strong>' + escapeHtml(data.columns.join(', ')) + '</strong></div>'
                    + '<div style="font-size:0.72rem; color:var(--accent-cyan); margin-top:0.3rem;">👉 Click <strong>"Run Full Audit"</strong> below to run the 8-step pipeline on this dataset.</div>'
                    + '</div>';
            } else {
                csvStatus.innerHTML = '<div style="font-size:0.78rem; color:var(--accent-red); margin-top:0.5rem;">Failed: ' + escapeHtml((data && (data.detail || data.error)) || 'Unknown error') + '</div>';
            }
        } catch (err) {
            csvStatus.innerHTML = '<div style="font-size:0.78rem; color:var(--accent-red); margin-top:0.5rem;">Upload failed: ' + escapeHtml(err.message) + '</div>';
        }
        uploadBtn.disabled = false;
        uploadBtn.textContent = '📁 Choose CSV File';
        csvInput.value = '';
    });

    // Depth control
    let selectedDepth = 'standard';
    const depthDescriptions = {
        fast: '⚡ <strong>Fast</strong> — Bias + Truth only, parallel via <code style="color:var(--accent-purple);">asyncio.gather</code> (~1s). Steps 3-4 skipped.',
        standard: '🔍 <strong>Standard</strong> — Steps 1-4 run in parallel via <code style="color:var(--accent-purple);">asyncio.gather</code> (~3s). Bias + Truth + Cluster + Distribution.',
        thorough: '🔬 <strong>Thorough</strong> — Full 8-step pipeline + re-evaluation pass (~8s). Maximum accuracy.'
    };
    document.querySelectorAll('.depth-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.depth-btn').forEach(b => { b.style.background='transparent'; b.style.color='var(--text-secondary)'; b.classList.remove('active'); });
            btn.style.background='rgba(59,130,246,0.2)'; btn.style.color='var(--accent-blue)'; btn.classList.add('active');
            selectedDepth = btn.dataset.depth;
            document.getElementById('depth-info').innerHTML = depthDescriptions[selectedDepth];
        });
    });

    // Run Audit
    document.getElementById('run-audit-btn').addEventListener('click', async () => {
        const input = document.getElementById('audit-input').value.trim();
        if (!input) { alert('Please enter input data.'); return; }
        const resultsEl = document.getElementById('audit-results');
        const btn = document.getElementById('run-audit-btn');
        btn.disabled = true;
        btn.textContent = '⏳ Running ' + selectedDepth + ' audit...';
        resultsEl.innerHTML = '<div style="text-align:center; padding:2rem;"><div class="loading-spinner"></div><div style="color:var(--text-muted); margin-top:12px;">Running 8-step pipeline (' + selectedDepth + ' mode)...</div></div>';

        const result = await api.post('/audit', { input_text: input, depth: selectedDepth });
        btn.disabled = false;
        btn.textContent = '→ Run Full Audit';

        if (result) {
            resultsEl.innerHTML = buildFullResult(result);
        } else {
            resultsEl.innerHTML = '<div class="card" style="border-color:var(--accent-red);"><div style="padding:1rem; color:var(--accent-red);">Audit failed. Check backend.</div></div>';
        }
    });

    document.getElementById('run-llm-audit-btn').addEventListener('click', async () => {
        const modelName = document.getElementById('llm-model-name').value.trim();
        const prompt = document.getElementById('llm-prompt').value.trim();
        const outputText = document.getElementById('llm-output').value.trim();
        if (!modelName || !prompt || !outputText) {
            alert('Please fill model name, prompt, and output.');
            return;
        }
        const result = await runWithLiveSteps(
            api,
            '/audit-llm-output',
            { model_name: modelName, prompt, output_text: outputText },
            'Running LLM hallucination checks',
        );
        const resultsEl = document.getElementById('audit-results');
        resultsEl.innerHTML = result ? buildFullResult(result) : '<div class="card" style="border-color:var(--accent-red);"><div style="padding:1rem; color:var(--accent-red);">LLM audit failed.</div></div>';
    });

    document.getElementById('btn-demo-scenario').addEventListener('click', async () => {
        const prompt = 'Give me accurate facts about Paris and its founding.';
        const output = 'Paris is the capital of France. Paris was founded in 1234 by aliens. The city is known for the Eiffel Tower.';
        document.getElementById('llm-model-name').value = 'gpt-4.1';
        document.getElementById('llm-prompt').value = prompt;
        document.getElementById('llm-output').value = output;
        const result = await runWithLiveSteps(
            api,
            '/audit-llm-output',
            { model_name: 'gpt-4.1', prompt, output_text: output },
            'Running one-click demo scenario',
        );
        const resultsEl = document.getElementById('audit-results');
        resultsEl.innerHTML = result ? buildFullResult(result) : '<div class="card" style="border-color:var(--accent-red);"><div style="padding:1rem; color:var(--accent-red);">Demo scenario failed.</div></div>';
    });

    // Static SHAP waterfall
    const features = [
        {name:'Credit Score (750)', val:'+0.15', pct:70, color:'var(--accent-green)'},
        {name:'Annual Income ($85k)', val:'+0.12', pct:55, color:'var(--accent-green)'},
        {name:'Years of Exp (5)', val:'+0.08', pct:40, color:'var(--accent-green)'},
        {name:'Education (Master\'s)', val:'+0.05', pct:25, color:'var(--accent-green)'},
        {name:'Loan Amount ($30k)', val:'-0.03', pct:15, color:'var(--accent-red)'},
        {name:'Debt-to-Income (25%)', val:'-0.05', pct:22, color:'var(--accent-red)'},
        {name:'Age (35)', val:'-0.02', pct:10, color:'var(--accent-red)'},
    ];
    const wf = document.getElementById('shap-waterfall');
    wf.innerHTML = features.map(f => '<div style="display:flex; align-items:center; gap:0.75rem;"><div style="width:130px; text-align:right; font-size:0.78rem; color:var(--text-secondary);">' + f.name + '</div><div style="flex:1; height:14px; background:rgba(255,255,255,0.04); border-radius:4px; overflow:hidden;"><div style="height:100%; width:' + f.pct + '%; background:' + f.color + '; border-radius:4px;"></div></div><div style="width:45px; font-size:0.75rem; font-family:var(--font-mono); color:' + (f.val.startsWith('+') ? 'var(--accent-green)' : 'var(--accent-red)') + ';">' + f.val + '</div></div>').join('');

    // Parity Chart
    setTimeout(() => {
        const ctx = document.getElementById('parityChart');
        if (!ctx) return;
        new Chart(ctx, { type:'bar', data:{ labels:['Female','Male','Black','White','Asian','Hispanic','18-25','26-50','51+'], datasets:[{data:[0.48,0.52,0.45,0.55,0.49,0.56,0.48,0.55,0.40], backgroundColor:['#f43f5e','#3b82f6','#f43f5e','#3b82f6','#3b82f6','#3b82f6','#3b82f6','#3b82f6','#3b82f6'], borderRadius:4}] }, options:{ responsive:true, maintainAspectRatio:false, scales:{y:{beginAtZero:true,max:0.8,grid:{color:'rgba(255,255,255,0.05)'},ticks:{color:'#94a3b8'}},x:{grid:{display:false},ticks:{color:'#94a3b8',font:{size:9}}}}, plugins:{legend:{display:false}} } });
    }, 100);
}

function buildFullResult(r) {
    const ts = (r.trust_score * 100).toFixed(1);
    const tsColor = r.trust_score > 0.7 ? 'var(--accent-emerald)' : (r.trust_score > 0.5 ? 'var(--accent-amber)' : 'var(--accent-red)');
    const biasScore = (r.bias.bias_score * 100).toFixed(1);
    const truthScore = (r.truth.truth_score * 100).toFixed(1);
    const clusterScore = (r.cluster.cluster_fairness * 100).toFixed(1);
    const distScore = (r.distribution.distribution_stability * 100).toFixed(1);

    // Pipeline steps
    const stepIcons = ['⚖️','🔍','📊','📈','🎯','🔧','🔄','👁️'];
    const pipelineHTML = r.reasoning_steps.map((s, i) => {
        const bg = s.status === 'complete' ? 'rgba(16,185,129,0.12)' : (s.status === 'flagged' ? 'rgba(244,63,94,0.12)' : (s.status === 'skipped' ? 'rgba(255,255,255,0.03)' : 'rgba(59,130,246,0.12)'));
        const border = s.status === 'complete' ? 'rgba(16,185,129,0.3)' : (s.status === 'flagged' ? 'rgba(244,63,94,0.3)' : (s.status === 'skipped' ? 'rgba(255,255,255,0.08)' : 'rgba(59,130,246,0.3)'));
        const color = s.status === 'complete' ? 'var(--accent-emerald)' : (s.status === 'flagged' ? 'var(--accent-red)' : (s.status === 'skipped' ? 'var(--text-muted)' : 'var(--accent-blue)'));
        const badge = s.status === 'complete' ? '✓' : (s.status === 'flagged' ? '⚠' : (s.status === 'skipped' ? '—' : '●'));
        const timing = s.elapsed > 0 ? '<span style="color:var(--accent-cyan); font-size:0.65rem;">' + (s.elapsed * 1000).toFixed(0) + 'ms</span>' : '';
        return '<div style="display:flex; align-items:center; gap:0.75rem; padding:0.6rem 0.75rem; background:' + bg + '; border:1px solid ' + border + '; border-radius:6px;">' +
            '<div style="font-size:1rem; width:24px; text-align:center;">' + stepIcons[i] + '</div>' +
            '<div style="flex:1;"><div style="font-size:0.78rem; font-weight:600; color:' + color + ';">Step ' + escapeHtml(s.step) + ': ' + escapeHtml(s.name) + ' <span style="font-weight:400; opacity:0.7;">' + badge + '</span></div>' +
            '<div style="font-size:0.68rem; color:var(--text-muted); margin-top:1px;">' + escapeHtml(s.detail) + '</div></div>' +
            timing + '</div>';
    }).join('');

    // Parallel indicator
    const parallelSteps = r.reasoning_steps.filter(s => s.elapsed > 0);
    const maxParallel = parallelSteps.length > 0 ? Math.max(...parallelSteps.map(s => s.elapsed)) : 0;

    // Citations
    const citationsHTML = (r.truth.citations || []).map(c =>
        '<div style="padding:0.5rem; background:rgba(255,255,255,0.03); border-radius:4px; margin-bottom:0.4rem;">' +
        '<div style="font-size:0.78rem; font-weight:600; color:var(--accent-cyan);">' + escapeHtml(c.title || 'Untitled source') + '</div>' +
        '<div style="font-size:0.7rem; color:var(--text-muted);">' + escapeHtml((c.snippet || '').substring(0, 120)) + '...</div>' +
        '<div style="font-size:0.65rem; color:var(--text-muted); margin-top:2px;">Similarity: ' + (Number(c.similarity || 0) * 100).toFixed(1) + '% | ' + escapeHtml(c.source || 'N/A') + '</div></div>'
    ).join('');

    return `
        <!-- Audit Result Header -->
        <div class="card glass-card" style="margin-bottom:1.5rem;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1.25rem;">
                <div>
                    <div style="font-size:0.72rem; color:var(--text-muted);">AUDIT COMPLETE — ${r.depth.toUpperCase()} MODE</div>
                    <h3 style="font-size:1.1rem; font-weight:700; font-family:var(--font-mono);">ID: ${escapeHtml(r.audit_id)}</h3>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:2rem; font-weight:700; color:${tsColor};">${ts}%</div>
                    <div style="font-size:0.72rem; color:var(--text-muted);">TRUST SCORE</div>
                </div>
            </div>

            <!-- Score Breakdown -->
            <div style="display:grid; grid-template-columns:repeat(5,1fr); gap:0.5rem; margin-bottom:1.25rem;">
                ${scoreCard('Bias', biasScore, parseFloat(biasScore) > 60 ? 'var(--accent-amber)' : 'var(--accent-emerald)')}
                ${scoreCard('Truth', truthScore, parseFloat(truthScore) < 50 ? 'var(--accent-red)' : 'var(--accent-cyan)')}
                ${scoreCard('Cluster', clusterScore, 'var(--accent-purple)')}
                ${scoreCard('Distrib.', distScore, 'var(--accent-blue)')}
                ${scoreCard('Trust', ts, tsColor)}
            </div>

            <!-- Performance Bar -->
            <div style="display:flex; justify-content:space-between; align-items:center; padding:0.5rem 0.75rem; background:rgba(255,255,255,0.03); border-radius:var(--radius-md); font-size:0.72rem;">
                <span style="color:var(--text-muted);">⏱ Total: <strong style="color:var(--accent-cyan);">${r.elapsed_seconds}s</strong></span>
                <span style="color:var(--text-muted);">Parallel latency: <strong style="color:var(--accent-purple);">${(maxParallel * 1000).toFixed(0)}ms</strong></span>
                <span style="color:var(--text-muted);">Depth: <strong style="color:var(--accent-blue);">${r.depth}</strong></span>
                <span style="color:${r.requires_human_review ? 'var(--accent-red)' : 'var(--accent-emerald)'};">${r.requires_human_review ? '🚨 Flagged for Review' : '✅ Auto-Approved'}</span>
            </div>
            ${r.pre_correction_trust !== undefined ? `
            <div style="margin-top:0.6rem; display:flex; justify-content:space-between; font-size:0.75rem; color:var(--text-secondary);">
                <span>Before correction: <strong>${(r.pre_correction_trust * 100).toFixed(1)}%</strong></span>
                <span>After correction: <strong>${(r.trust_score * 100).toFixed(1)}%</strong></span>
                <span style="color:${r.trust_delta >= 0 ? 'var(--accent-emerald)' : 'var(--accent-red)'};">Delta: <strong>${r.trust_delta >= 0 ? '+' : ''}${(r.trust_delta * 100).toFixed(1)}%</strong></span>
            </div>` : ''}
        </div>

        <!-- 8-Step Pipeline -->
        <div class="card glass-card" style="margin-bottom:1.5rem;">
            <h3 class="card-title" style="margin-bottom:1rem;">8-Step Reasoning Pipeline</h3>
            <div style="display:flex; flex-direction:column; gap:0.4rem;">${pipelineHTML}</div>
        </div>

        <!-- Truth Citations & Corrections -->
        <div class="grid grid-2" style="margin-bottom:1.5rem;">
            <div class="card glass-card">
                <h4 style="font-size:0.9rem; margin-bottom:0.75rem;">📚 FAISS Knowledge Citations</h4>
                ${citationsHTML || '<div style="color:var(--text-muted); font-size:0.78rem;">No citations found</div>'}
            </div>
            <div class="card glass-card">
                <h4 style="font-size:0.9rem; margin-bottom:0.75rem;">🔧 Auto-Correction Output</h4>
                <div style="font-size:0.82rem; color:var(--text-secondary); line-height:1.5; padding:0.75rem; background:rgba(16,185,129,0.05); border-left:3px solid var(--accent-emerald); border-radius:0 4px 4px 0;">
                    ${r.corrections ? escapeHtml(r.corrections) : 'No corrections needed — output approved as-is.'}
                </div>
                ${r.correction_actions && r.correction_actions.length > 0 ? '<div style="margin-top:0.5rem; font-size:0.72rem; color:var(--text-muted);">Actions: ' + escapeHtml(r.correction_actions.join(', ')) + '</div>' : ''}
            </div>
        </div>

        <div style="text-align:center;"><a href="#/reports/${encodeURIComponent(r.audit_id)}" class="btn btn-primary" style="display:inline-flex;">View Full Report →</a></div>
    `;
}

async function runWithLiveSteps(api, endpoint, payload, label) {
    const resultsEl = document.getElementById('audit-results');
    const steps = ['Input validation', 'Claim extraction', 'Truth verification', 'Scoring', 'Auto-correction', 'Final review'];
    let idx = 0;
    resultsEl.innerHTML = renderLiveStepCard(label, steps, idx);
    const timer = setInterval(() => {
        idx = Math.min(idx + 1, steps.length - 1);
        resultsEl.innerHTML = renderLiveStepCard(label, steps, idx);
    }, 700);
    try {
        const result = await api.post(endpoint, payload);
        clearInterval(timer);
        return result;
    } catch (_e) {
        clearInterval(timer);
        return null;
    }
}

function renderLiveStepCard(label, steps, activeIdx) {
    return `
    <div class="card glass-card">
        <h3 class="card-title" style="margin-bottom:0.75rem;">${escapeHtml(label)}</h3>
        <div style="display:flex; flex-direction:column; gap:0.45rem;">
            ${steps.map((s, i) => `
                <div style="padding:0.55rem 0.7rem; border-radius:6px; border:1px solid ${i <= activeIdx ? 'rgba(16,185,129,0.25)' : 'rgba(255,255,255,0.08)'}; background:${i <= activeIdx ? 'rgba(16,185,129,0.08)' : 'rgba(255,255,255,0.03)'};">
                    <span style="font-size:0.78rem; color:${i <= activeIdx ? 'var(--accent-emerald)' : 'var(--text-secondary)'};">${i <= activeIdx ? '✓' : '•'} ${escapeHtml(s)}</span>
                </div>
            `).join('')}
        </div>
    </div>`;
}

function scoreCard(label, value, color) {
    return '<div style="text-align:center; padding:0.6rem; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.06); border-radius:6px;">' +
        '<div style="font-size:1.1rem; font-weight:700; color:' + color + ';">' + value + '%</div>' +
        '<div style="font-size:0.65rem; color:var(--text-muted); margin-top:2px;">' + label + '</div>' +
        '<div style="width:100%; height:3px; background:rgba(255,255,255,0.08); border-radius:2px; margin-top:4px;"><div style="width:' + value + '%; height:100%; background:' + color + '; border-radius:2px;"></div></div></div>';
}
