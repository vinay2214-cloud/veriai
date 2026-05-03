export async function renderSettingsPage(rootEl, api) {
    const config = await api.get('/settings/weights');
    const weights = config?.active_weights || { truth: 0.35, bias: 0.3, confidence: 0.15, cluster: 0.1, distribution: 0.1 };
    const presets = config?.presets || {};

    // Fetch knowledge base stats
    const kbStats = await api.get('/knowledge-base/stats');

    rootEl.innerHTML = `
        <div style="margin-bottom:1.5rem;">
            <div style="font-size:0.8rem; color:var(--text-muted);">VeriAI Industry Configuration</div>
            <h2 style="font-size:1.4rem; font-weight:700;">Dynamic Trust Formula Configuration</h2>
            <p style="font-size:0.82rem; color:var(--text-secondary); margin-top:0.3rem;">
                Adjust how VeriAI calculates the composite Trust Score. The formula: <code style="color:var(--accent-cyan); font-family:var(--font-mono);">Trust = Σ(wᵢ × scoreᵢ)</code> where weights must sum to 1.0.
            </p>
        </div>

        <div class="grid" style="grid-template-columns:1fr 340px; gap:2rem; align-items:start;">
            <div>
                <h3 style="font-size:1rem; font-weight:600; margin-bottom:0.75rem;">Industry Preset Selection</h3>
                <div style="display:flex; gap:0.5rem; flex-wrap:wrap; margin-bottom:2rem;" id="preset-buttons">
                    ${Object.keys(presets).map(key => {
                        const p = presets[key];
                        return '<button class="btn preset-btn" data-preset="' + key + '" style="background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); color:var(--text-secondary); font-size:0.82rem; padding:0.5rem 1rem;"><strong>' + p.label + '</strong></button>';
                    }).join('')}
                    <button class="btn preset-btn" data-preset="reset" style="background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); color:var(--accent-amber); font-size:0.82rem; padding:0.5rem 1rem;">⟳ Reset Defaults</button>
                </div>
                <div id="preset-desc" style="font-size:0.8rem; color:var(--accent-cyan); margin-bottom:1rem; display:none;"></div>

                <h3 style="font-size:1rem; font-weight:600; margin-bottom:1.25rem;">Manual Weight Adjustment</h3>
                <div style="display:flex; flex-direction:column; gap:1.75rem;" id="weight-sliders">
                    ${buildSlider('truth', 'Truth Verification Weight', weights.truth, 'Weight given to factual accuracy and hallucination detection. Higher values penalize hallucinated or unverified claims.')}
                    ${buildSlider('bias', 'Bias Detection Weight', weights.bias, 'Controls importance of fairness and non-discrimination metrics. Critical for HR and lending applications.')}
                    ${buildSlider('confidence', 'Model Confidence Weight', weights.confidence, 'Weight of the model\'s own prediction confidence in the final trust score.')}
                    ${buildSlider('cluster', 'Clustering Anomaly Weight', weights.cluster, 'Focus on identifying anomalous data clusters that may indicate data poisoning or distribution shift.')}
                    ${buildSlider('distribution', 'Distribution Shift Weight', weights.distribution, 'Impact of data representativeness on trust score. Detects training/serving skew.')}
                </div>

                <div style="margin-top:1.5rem; padding:1rem; background:rgba(255,255,255,0.03); border-radius:var(--radius-md); border:1px solid rgba(255,255,255,0.08);">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-size:0.82rem; color:var(--text-muted);">Weight Sum:</span>
                        <span id="weight-sum" style="font-size:0.95rem; font-weight:700; color:var(--accent-emerald);">100%</span>
                    </div>
                    <div style="font-size:0.75rem; color:var(--text-muted); margin-top:0.3rem;">Weights should sum to 100% for accurate scoring. Auto-normalized on save.</div>
                </div>
            </div>

            <div style="display:flex; flex-direction:column; gap:1.5rem;">
                <div class="card glass-card">
                    <h3 class="card-title" style="margin-bottom:1rem;">Simulated Score Impact</h3>
                    <div style="display:flex; align-items:center; gap:1rem;">
                        <div style="position:relative; width:100px; height:100px;">
                            <svg viewBox="0 0 36 36" style="width:100%; height:100%;"><path d="M18 2.0845a15.9155 15.9155 0 010 31.831 15.9155 15.9155 0 010-31.831" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="4"/><path d="M18 2.0845a15.9155 15.9155 0 010 31.831 15.9155 15.9155 0 010-31.831" fill="none" stroke="var(--accent-blue)" stroke-width="4" stroke-dasharray="85, 100" id="score-ring"/></svg>
                            <div style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); font-size:1.3rem; font-weight:700;" id="sim-score">85%</div>
                        </div>
                        <div style="flex:1;">
                            <div style="font-size:0.75rem; color:var(--text-muted);">Dynamic Preview</div>
                            <div style="font-size:0.75rem; color:var(--accent-emerald); margin-top:0.5rem;" id="score-trend">Score Trend: +4%</div>
                            <div style="font-size:0.7rem; color:var(--text-muted); margin-top:0.3rem;" id="active-preset">${config?.is_custom ? 'Custom Configuration' : 'Default Preset'}</div>
                        </div>
                    </div>
                </div>

                <div class="card glass-card">
                    <h4 style="font-size:0.9rem; margin-bottom:0.5rem;">📐 Trust Formula</h4>
                    <div style="font-family:var(--font-mono); font-size:0.72rem; color:var(--accent-cyan); line-height:1.8; padding:0.5rem; background:rgba(0,0,0,0.2); border-radius:4px;" id="formula-display">
                        Trust = ${(weights.truth).toFixed(2)}×Truth + ${(weights.bias).toFixed(2)}×Bias + ${(weights.confidence).toFixed(2)}×Conf + ${(weights.cluster).toFixed(2)}×Clust + ${(weights.distribution).toFixed(2)}×Dist
                    </div>
                </div>

                <!-- Knowledge Base Management — FUNCTIONAL -->
                <div class="card glass-card">
                    <h4 style="font-size:0.9rem; margin-bottom:0.5rem;">📚 Knowledge Base Management</h4>
                    <p style="font-size:0.72rem; color:var(--text-muted); margin-bottom:0.75rem;">
                        Upload training data (CSV) for bias scanning, or add knowledge articles to the FAISS vector store for truth/hallucination verification.
                    </p>

                    <!-- Hidden file inputs -->
                    <input type="file" id="csv-file-input" accept=".csv" style="display:none;" />
                    <input type="file" id="kb-file-input" accept=".csv" style="display:none;" />

                    <button class="btn" id="btn-upload-csv" style="width:100%; background:var(--accent-blue); color:white; justify-content:center; margin-bottom:0.75rem; transition:all 0.2s;">
                        📊 Upload CSV Data (Bias Scan)
                    </button>
                    <button class="btn" id="btn-connect-faiss" style="width:100%; background:transparent; border:1px solid rgba(255,255,255,0.2); color:white; justify-content:center; margin-bottom:0.75rem; transition:all 0.2s;">
                        🔗 Connect FAISS Vector Store
                    </button>

                    <!-- FAISS Status -->
                    <div style="display:flex; justify-content:space-between; align-items:center; padding:0.5rem 0; border-top:1px solid rgba(255,255,255,0.06);">
                        <div style="font-size:0.72rem; color:var(--text-muted);">FAISS Status:</div>
                        <div style="display:flex; align-items:center; gap:0.3rem;">
                            <div style="width:6px; height:6px; border-radius:50%; background:${kbStats?.faiss_status === 'connected' ? 'var(--accent-emerald)' : 'var(--accent-red)'}; box-shadow:0 0 6px ${kbStats?.faiss_status === 'connected' ? 'var(--accent-emerald)' : 'var(--accent-red)'};"></div>
                            <span id="faiss-status" style="font-size:0.72rem; color:${kbStats?.faiss_status === 'connected' ? 'var(--accent-emerald)' : 'var(--accent-red)'};">${kbStats?.faiss_status === 'connected' ? 'Connected' : 'Disconnected'}</span>
                        </div>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; padding:0.3rem 0;">
                        <div style="font-size:0.72rem; color:var(--text-muted);">Articles Indexed:</div>
                        <span id="kb-count" style="font-size:0.72rem; color:var(--accent-cyan); font-weight:600;">${kbStats?.total_articles || 0}</span>
                    </div>

                    <!-- Upload result area -->
                    <div id="upload-result" style="display:none; margin-top:0.75rem; padding:0.75rem; border-radius:var(--radius-md); font-size:0.78rem;"></div>
                </div>

                <button class="btn btn-primary" id="save-weights-btn" style="width:100%; justify-content:center;">💾 Save Configuration & Apply</button>
                <div id="save-status" style="text-align:center; font-size:0.85rem; display:none;"></div>
            </div>
        </div>
    `;

    // ==========================================
    // UPLOAD CSV — Bias Scan Data
    // ==========================================
    const csvFileInput = document.getElementById('csv-file-input');
    const btnUploadCsv = document.getElementById('btn-upload-csv');

    btnUploadCsv.addEventListener('click', () => {
        csvFileInput.click();
    });

    csvFileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        btnUploadCsv.disabled = true;
        btnUploadCsv.textContent = '⏳ Uploading ' + file.name + '...';

        const formData = new FormData();
        formData.append('file', file);

        const resultEl = document.getElementById('upload-result');

        try {
            const data = await api.postForm('/upload-csv', formData);

            if (data && data.status === 'success') {
                resultEl.style.display = 'block';
                resultEl.style.background = 'rgba(16,185,129,0.1)';
                resultEl.style.border = '1px solid rgba(16,185,129,0.3)';
                resultEl.style.color = 'var(--accent-emerald)';
                resultEl.innerHTML = `
                    <div style="font-weight:600; margin-bottom:0.3rem;">✅ ${data.filename} uploaded successfully!</div>
                    <div style="color:var(--text-secondary);">
                        <strong>${data.rows}</strong> rows × <strong>${data.num_features}</strong> features<br/>
                        Label column: <strong>${data.label_column}</strong><br/>
                        Columns: ${data.columns.join(', ')}
                    </div>
                    <div style="margin-top:0.5rem; font-size:0.72rem; color:var(--text-muted);">
                        Dataset parsed and ready for bias scan. Run an audit to analyze this data.
                    </div>
                `;
                btnUploadCsv.textContent = '✅ ' + data.filename + ' Loaded';
            } else {
                resultEl.style.display = 'block';
                resultEl.style.background = 'rgba(244,63,94,0.1)';
                resultEl.style.border = '1px solid rgba(244,63,94,0.3)';
                resultEl.style.color = 'var(--accent-red)';
                resultEl.textContent = '❌ ' + ((data && data.error) || 'Upload failed');
                btnUploadCsv.textContent = '📊 Upload CSV Data (Bias Scan)';
            }
        } catch (err) {
            resultEl.style.display = 'block';
            resultEl.style.background = 'rgba(244,63,94,0.1)';
            resultEl.style.border = '1px solid rgba(244,63,94,0.3)';
            resultEl.style.color = 'var(--accent-red)';
            resultEl.textContent = '❌ Network error: ' + err.message;
            btnUploadCsv.textContent = '📊 Upload CSV Data (Bias Scan)';
        }

        btnUploadCsv.disabled = false;
        csvFileInput.value = ''; // Reset so same file can be re-uploaded
    });

    // ==========================================
    // CONNECT FAISS — Knowledge Base Upload
    // ==========================================
    const kbFileInput = document.getElementById('kb-file-input');
    const btnFaiss = document.getElementById('btn-connect-faiss');

    btnFaiss.addEventListener('click', () => {
        kbFileInput.click();
    });

    kbFileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        btnFaiss.disabled = true;
        btnFaiss.textContent = '⏳ Uploading to FAISS: ' + file.name + '...';

        const formData = new FormData();
        formData.append('file', file);

        const resultEl = document.getElementById('upload-result');

        try {
            const data = await api.postForm('/upload-csv-knowledge', formData);

            if (data && data.status === 'success') {
                // Now rebuild the FAISS index
                btnFaiss.textContent = '🔧 Rebuilding FAISS index...';
                const rebuildRes = await api.post('/knowledge-base/rebuild');

                resultEl.style.display = 'block';
                resultEl.style.background = 'rgba(16,185,129,0.1)';
                resultEl.style.border = '1px solid rgba(16,185,129,0.3)';
                resultEl.style.color = 'var(--accent-emerald)';
                resultEl.innerHTML = `
                    <div style="font-weight:600; margin-bottom:0.3rem;">✅ FAISS Vector Store Updated!</div>
                    <div style="color:var(--text-secondary);">
                        <strong>${data.articles_inserted}</strong> new articles inserted<br/>
                        <strong>${data.skipped_duplicates}</strong> duplicates skipped<br/>
                        Total articles indexed: <strong>${data.total_articles}</strong>
                    </div>
                    ${rebuildRes ? '<div style="margin-top:0.5rem; font-size:0.72rem; color:var(--accent-cyan);">🔗 FAISS index rebuilt — ' + (rebuildRes.index_dimensions || 0) + ' dimensions, ' + (rebuildRes.total_articles || 0) + ' articles</div>' : ''}
                `;

                // Update status indicators
                document.getElementById('faiss-status').textContent = 'Connected';
                document.getElementById('faiss-status').style.color = 'var(--accent-emerald)';
                document.getElementById('kb-count').textContent = data.total_articles;
                btnFaiss.textContent = '✅ FAISS Connected (' + data.total_articles + ' articles)';
            } else {
                resultEl.style.display = 'block';
                resultEl.style.background = 'rgba(244,63,94,0.1)';
                resultEl.style.border = '1px solid rgba(244,63,94,0.3)';
                resultEl.style.color = 'var(--accent-red)';
                resultEl.innerHTML = `
                    <div style="font-weight:600;">❌ ${(data && data.error) || 'Upload failed'}</div>
                    <div style="color:var(--text-muted); margin-top:0.3rem; font-size:0.72rem;">
                        CSV format: columns named <strong>title</strong>, <strong>content</strong>, <strong>source</strong> (source is optional).<br/>
                        The <strong>content</strong> column contains the knowledge text for FAISS indexing.
                    </div>
                `;
                btnFaiss.textContent = '🔗 Connect FAISS Vector Store';
            }
        } catch (err) {
            resultEl.style.display = 'block';
            resultEl.style.background = 'rgba(244,63,94,0.1)';
            resultEl.style.border = '1px solid rgba(244,63,94,0.3)';
            resultEl.style.color = 'var(--accent-red)';
            resultEl.textContent = '❌ Network error: ' + err.message;
            btnFaiss.textContent = '🔗 Connect FAISS Vector Store';
        }

        btnFaiss.disabled = false;
        kbFileInput.value = '';
    });

    // ==========================================
    // Simulation + Presets + Save (existing)
    // ==========================================
    const updateSimulation = () => {
        const vals = {};
        let sum = 0;
        document.querySelectorAll('.weight-slider').forEach(s => {
            vals[s.dataset.key] = parseInt(s.value);
            sum += parseInt(s.value);
        });
        document.getElementById('weight-sum').textContent = sum + '%';
        document.getElementById('weight-sum').style.color = Math.abs(sum - 100) < 5 ? 'var(--accent-emerald)' : 'var(--accent-red)';
        
        const simScore = Math.round(vals.truth * 0.7 + vals.bias * 0.85 + vals.confidence * 0.9 + vals.cluster * 0.6 + vals.distribution * 0.75);
        const clampedScore = Math.min(Math.max(simScore, 10), 99);
        document.getElementById('sim-score').textContent = clampedScore + '%';
        document.getElementById('score-ring').setAttribute('stroke-dasharray', clampedScore + ', 100');

        document.getElementById('formula-display').textContent = 
            'Trust = ' + (vals.truth/100).toFixed(2) + '×Truth + ' + (vals.bias/100).toFixed(2) + '×Bias + ' + (vals.confidence/100).toFixed(2) + '×Conf + ' + (vals.cluster/100).toFixed(2) + '×Clust + ' + (vals.distribution/100).toFixed(2) + '×Dist';
    };

    document.querySelectorAll('.weight-slider').forEach(s => {
        s.addEventListener('input', updateSimulation);
    });

    // Preset buttons
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const preset = btn.dataset.preset;
            const descEl = document.getElementById('preset-desc');
            
            if (preset === 'reset') {
                const res = await api.post('/settings/weights/reset');
                if (res) {
                    const defaults = config?.defaults || { truth: 0.35, bias: 0.3, confidence: 0.15, cluster: 0.1, distribution: 0.1 };
                    applyWeights(defaults);
                    descEl.textContent = '⟳ Reset to default weights.';
                    descEl.style.display = 'block';
                    document.getElementById('active-preset').textContent = 'Default Preset';
                }
            } else if (presets[preset]) {
                const res = await api.post('/settings/weights/preset', { preset });
                const w = presets[preset].weights;
                applyWeights(w);
                descEl.textContent = presets[preset].description;
                descEl.style.display = 'block';
                document.getElementById('active-preset').textContent = presets[preset].label;
            }
            
            document.querySelectorAll('.preset-btn').forEach(b => {
                b.style.borderColor = 'rgba(255,255,255,0.1)';
                b.style.background = 'rgba(255,255,255,0.05)';
            });
            btn.style.borderColor = 'var(--accent-blue)';
            btn.style.background = 'rgba(59,130,246,0.15)';
            updateSimulation();
        });
    });

    function applyWeights(w) {
        Object.keys(w).forEach(k => {
            const slider = document.getElementById('slider-' + k);
            const valEl = document.getElementById('val-' + k);
            if (slider) { slider.value = Math.round(w[k] * 100); valEl.textContent = Math.round(w[k] * 100) + '%'; }
        });
    }

    // Save weights
    const saveBtn = document.getElementById('save-weights-btn');
    const saveStatusEl = document.getElementById('save-status');
    if (saveBtn) {
        // Ensure the button is interactable when this page renders.
        saveBtn.disabled = false;
        saveBtn.removeAttribute('disabled');
        saveBtn.addEventListener('click', async () => {
            const data = {};
            document.querySelectorAll('.weight-slider').forEach(s => { data[s.dataset.key] = parseInt(s.value) / 100; });
            saveBtn.disabled = true;
            saveBtn.textContent = '⏳ Saving...';
            if (saveStatusEl) saveStatusEl.style.display = 'block';
            try {
                const res = await api.post('/settings/weights', data);
                if (res) {
                    if (saveStatusEl) {
                        saveStatusEl.textContent = '✅ Weights saved and applied to all future audits!';
                        saveStatusEl.style.color = 'var(--accent-emerald)';
                    }
                    saveBtn.textContent = '✅ Saved!';
                    const activePresetEl = document.getElementById('active-preset');
                    if (activePresetEl) activePresetEl.textContent = 'Custom Configuration';
                } else {
                    if (saveStatusEl) {
                        saveStatusEl.textContent = '❌ Save failed — check backend connection';
                        saveStatusEl.style.color = 'var(--accent-red)';
                    }
                }
            } catch (err) {
                if (saveStatusEl) {
                    saveStatusEl.textContent = '❌ Save failed — ' + err.message;
                    saveStatusEl.style.color = 'var(--accent-red)';
                }
            } finally {
                setTimeout(() => {
                    if (saveStatusEl) saveStatusEl.style.display = 'none';
                    saveBtn.disabled = false;
                    saveBtn.textContent = '💾 Save Configuration & Apply';
                }, 3000);
            }
        });
    }

    updateSimulation();
}

function buildSlider(key, label, value, tooltip) {
    const pct = Math.round((value || 0) * 100);
    return '<div><div style="display:flex; justify-content:space-between; margin-bottom:0.4rem;"><label style="font-size:0.88rem; color:var(--text-secondary);">' + label + ' <span title="' + tooltip + '" style="cursor:help; color:var(--text-muted);">ℹ️</span></label><span id="val-' + key + '" style="font-size:0.88rem; font-weight:600;">' + pct + '%</span></div><input type="range" class="weight-slider" id="slider-' + key + '" data-key="' + key + '" min="0" max="100" value="' + pct + '" style="width:100%; accent-color:var(--accent-blue);" oninput="document.getElementById(\'val-' + key + '\').textContent=this.value+\'%\'"/></div>';
}
