import { escapeHtml } from '../utils.js';

export async function renderReviewPage(rootEl, api) {
    // Phase 3 — pull the AI-prioritized, enriched queue (a superset of
    // /review/queue, each item carrying an `ai_review` block) plus stats
    // concurrently. Fall back to the raw queue if the AI endpoint is unavailable,
    // so the page behaves exactly as before in the worst case.
    const [insights, reviewStats] = await Promise.all([
        api.get('/ai/review-insights').catch(() => null),
        api.get('/review/stats'),
    ]);
    let items = (insights && Array.isArray(insights.queue)) ? insights.queue : null;
    if (!items) {
        items = (await api.get('/review/queue')) || [];
    }
    const totalReviewed = reviewStats ? ((reviewStats.approved || 0) + (reviewStats.rejected || 0) + (reviewStats.escalated || 0)) : 0;
    const pendingCount = items.filter(i => i.status === 'pending').length;

    rootEl.innerHTML = `
        <!-- Stats Overview -->
        <div class="stats-grid" style="margin-bottom:1.5rem;">
            <div class="stat-card purple"><div class="stat-label">Pending Review</div><div class="stat-value purple">${pendingCount}</div></div>
            <div class="stat-card cyan"><div class="stat-label">Total Reviewed</div><div class="stat-value cyan">${totalReviewed}</div></div>
            <div class="stat-card amber"><div class="stat-label">Approved</div><div class="stat-value amber">${reviewStats?.approved || 0}</div></div>
            <div class="stat-card green"><div class="stat-label">Avg Trust</div><div class="stat-value green">${items.length > 0 ? (items.reduce((s,i) => s + (i.trust_score||0), 0) / items.length * 100).toFixed(0) + '%' : 'N/A'}</div></div>
        </div>

        <div class="review-layout">
            <!-- Queue List -->
            <div class="card glass-card" style="padding:1.25rem 1rem;">
                <h3 class="card-title" style="margin-left:0.5rem; margin-bottom:0.75rem;">Flagged Items</h3>
                <div id="queue-list" style="display:flex; flex-direction:column; gap:0.5rem; max-height:520px; overflow-y:auto;">
                    ${items.length > 0 ? items.map((item, i) => {
                        const severity = item.trust_score < 0.4 ? 'High' : (item.trust_score < 0.6 ? 'Medium' : 'Low');
                        const sevColor = severity === 'High' ? 'var(--accent-red)' : (severity === 'Medium' ? 'var(--accent-amber)' : 'var(--accent-emerald)');
                        const active = i === 0 ? 'background:rgba(59,130,246,0.15); border:1px solid rgba(59,130,246,0.3);' : 'background:rgba(255,255,255,0.03); border:1px solid transparent;';
                        const statusIcon = item.status === 'approved' ? '✅' : item.status === 'rejected' ? '❌' : item.status === 'escalated' ? '🚨' : '⏳';
                        return '<div class="queue-item" data-index="' + i + '" style="' + active + ' border-radius:var(--radius-md); padding:0.75rem; cursor:pointer; transition:all 0.2s;">' +
                            '<div style="display:flex; justify-content:space-between; align-items:center;">' +
                            '<div style="font-weight:600; font-size:0.82rem;">' + statusIcon + ' #' + escapeHtml(String(item.audit_id || '').substring(0,8)) + '</div>' +
                                '<div style="background:' + sevColor + '; color:white; font-size:0.65rem; font-weight:600; padding:2px 8px; border-radius:4px;">' + severity + '</div>' +
                            '</div>' +
                            '<div style="font-size:0.7rem; color:var(--text-muted); margin-top:4px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">' + escapeHtml((item.input_preview || '').substring(0, 45)) + '...</div>' +
                            '<div style="font-size:0.68rem; color:' + sevColor + '; margin-top:2px;">Trust: ' + (item.trust_score * 100).toFixed(0) + '%</div>' +
                        '</div>';
                    }).join('') : '<div style="color:var(--text-muted); text-align:center; padding:2rem;">✅ No items pending review</div>'}
                </div>
            </div>

            <!-- Detail Panel -->
            <div class="card glass-card" style="padding:2rem;" id="review-detail">
                ${items.length > 0 ? buildDetailPanel(items[0]) : '<div class="empty-state"><div class="empty-icon">✅</div><h3 class="empty-title">All Clear</h3><div class="empty-desc">No items require human review at this time.</div></div>'}
            </div>
        </div>
    `;

    // Queue item click handlers
    document.querySelectorAll('.queue-item').forEach(el => {
        el.addEventListener('click', () => {
            document.querySelectorAll('.queue-item').forEach(q => { q.style.background='rgba(255,255,255,0.03)'; q.style.border='1px solid transparent'; });
            el.style.background='rgba(59,130,246,0.15)'; el.style.border='1px solid rgba(59,130,246,0.3)';
            const idx = parseInt(el.dataset.index);
            if (items[idx]) {
                document.getElementById('review-detail').innerHTML = buildDetailPanel(items[idx]);
                bindReviewActions(api, items[idx], items, idx);
            }
        });
    });

    if (items.length > 0) bindReviewActions(api, items[0], items, 0);
}

const AISEV_COLOR = { critical: 'var(--accent-red)', high: 'var(--accent-red)', medium: 'var(--accent-amber)', low: 'var(--accent-emerald)' };

// Phase 3 — AI Review Manager guidance block (severity/urgency/impact/reviewer/action).
function renderAiReview(ai) {
    const color = AISEV_COLOR[ai.severity] || 'var(--text-muted)';
    const row = (label, val) => '<div style="display:flex; gap:0.5rem; margin-bottom:0.35rem;"><span style="color:var(--text-muted); min-width:150px; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.04em;">' + label + '</span><span style="color:var(--text-primary); font-size:0.82rem;">' + escapeHtml(val || '') + '</span></div>';
    return '<div style="background:' + color + '12; border:1px solid ' + color + '44; border-radius:var(--radius-md); padding:1rem; margin-bottom:1.25rem;">' +
        '<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.6rem;">' +
        '<h4 style="font-size:0.82rem; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.05em; margin:0;">🤖 AI Review Manager</h4>' +
        '<span style="background:' + color + '; color:#fff; font-size:0.68rem; font-weight:700; padding:2px 10px; border-radius:6px; text-transform:capitalize;">' + escapeHtml(ai.severity || '') + ' priority</span>' +
        '</div>' +
        row('Urgency', ai.urgency) +
        row('Business impact', ai.business_impact) +
        row('Recommended reviewer', ai.recommended_reviewer) +
        row('Recommended action', ai.recommended_action) +
        '</div>';
}

function buildDetailPanel(item) {
    const ts = item.trust_score ? (item.trust_score * 100).toFixed(0) : '??';
    const tsColor = item.trust_score < 0.5 ? 'var(--accent-red)' : (item.trust_score < 0.7 ? 'var(--accent-amber)' : 'var(--accent-emerald)');
    const biasScore = item.bias_score != null ? (item.bias_score * 100).toFixed(0) : null;
    const truthScore = item.truth_score != null ? (item.truth_score * 100).toFixed(0) : null;
    const statusText = item.status === 'approved' ? '✅ Approved' : (item.status === 'rejected' ? '❌ Rejected' : (item.status === 'escalated' ? '🚨 Escalated' : '⏳ Pending'));
    const statusColor = item.status === 'approved' ? 'var(--accent-emerald)' : (item.status === 'rejected' ? 'var(--accent-red)' : (item.status === 'escalated' ? 'var(--accent-amber)' : 'var(--accent-blue)'));
    const isActioned = item.status !== 'pending';
    const auditId = escapeHtml(item.audit_id || '');
    const createdAt = escapeHtml(item.created_at || '');
    const inputPreview = escapeHtml(item.input_preview || 'No input data');
    const correctedOutput = item.corrected_output ? escapeHtml(item.corrected_output) : '';
    const reviewerNotes = escapeHtml(item.reviewer_notes || '');

    // Determine risk factors
    const risks = [];
    if (truthScore !== null && truthScore < 50) risks.push({ label: 'Hallucination Risk', desc: 'Truth score (' + truthScore + '%) is below 50%. The AI output may contain unverified or fabricated claims.', color: 'var(--accent-red)', icon: '🔴' });
    if (biasScore !== null && biasScore > 60) risks.push({ label: 'Bias Detected', desc: 'Bias score (' + biasScore + '%) exceeds the 60% threshold. The output may disproportionately affect protected demographic groups.', color: 'var(--accent-amber)', icon: '🟠' });
    if (item.trust_score < 0.5) risks.push({ label: 'Critical Trust Level', desc: 'Overall trust (' + ts + '%) is significantly below the 70% safety threshold. This output is NOT safe for production release.', color: 'var(--accent-red)', icon: '🔴' });
    if (risks.length === 0) risks.push({ label: 'Marginal Trust', desc: 'Trust score (' + ts + '%) is borderline. Manual review is recommended before release.', color: 'var(--accent-amber)', icon: '🟡' });

    return `
        <!-- Header -->
        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:1.5rem;">
            <div>
                <div style="font-size:0.72rem; color:var(--text-muted); margin-bottom:0.25rem;">AUDIT ID</div>
                <h2 style="font-size:1.1rem; font-weight:700; font-family:var(--font-mono);">${auditId}</h2>
                <div style="font-size:0.72rem; color:var(--text-muted); margin-top:0.25rem;">${createdAt}</div>
            </div>
            <div style="text-align:right;">
                <div style="font-size:0.72rem; color:var(--text-muted); margin-bottom:0.25rem;">STATUS</div>
                <div style="font-size:0.88rem; font-weight:600; color:${statusColor};">${statusText}</div>
            </div>
        </div>

        <!-- Score Breakdown -->
        <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:0.75rem; margin-bottom:1.5rem;">
            <div style="background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); border-radius:var(--radius-md); padding:0.75rem; text-align:center;">
                <div style="font-size:1.3rem; font-weight:700; color:${tsColor};">${ts}%</div>
                <div style="font-size:0.68rem; color:var(--text-muted); margin-top:0.2rem;">Trust Score</div>
                <div style="width:100%; height:4px; background:rgba(255,255,255,0.1); border-radius:2px; margin-top:0.5rem; overflow:hidden;">
                    <div style="width:${ts}%; height:100%; background:${tsColor}; border-radius:2px;"></div>
                </div>
            </div>
            <div style="background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); border-radius:var(--radius-md); padding:0.75rem; text-align:center;">
                <div style="font-size:1.3rem; font-weight:700; color:${truthScore && truthScore < 50 ? 'var(--accent-red)' : 'var(--accent-cyan)'};">${truthScore !== null ? truthScore + '%' : 'N/A'}</div>
                <div style="font-size:0.68rem; color:var(--text-muted); margin-top:0.2rem;">Truth Score</div>
                <div style="width:100%; height:4px; background:rgba(255,255,255,0.1); border-radius:2px; margin-top:0.5rem; overflow:hidden;">
                    <div style="width:${truthScore || 0}%; height:100%; background:${truthScore && truthScore < 50 ? 'var(--accent-red)' : 'var(--accent-cyan)'}; border-radius:2px;"></div>
                </div>
            </div>
            <div style="background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); border-radius:var(--radius-md); padding:0.75rem; text-align:center;">
                <div style="font-size:1.3rem; font-weight:700; color:${biasScore && biasScore > 60 ? 'var(--accent-amber)' : 'var(--accent-emerald)'};">${biasScore !== null ? biasScore + '%' : 'N/A'}</div>
                <div style="font-size:0.68rem; color:var(--text-muted); margin-top:0.2rem;">Bias Score</div>
                <div style="width:100%; height:4px; background:rgba(255,255,255,0.1); border-radius:2px; margin-top:0.5rem; overflow:hidden;">
                    <div style="width:${biasScore || 0}%; height:100%; background:${biasScore && biasScore > 60 ? 'var(--accent-amber)' : 'var(--accent-emerald)'}; border-radius:2px;"></div>
                </div>
            </div>
        </div>

        <!-- Phase 3 — AI Review Manager guidance -->
        ${item.ai_review ? renderAiReview(item.ai_review) : ''}

        <!-- What Was Audited -->
        <div style="margin-bottom:1.25rem;">
            <h4 style="font-size:0.82rem; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.05em; margin-bottom:0.4rem;">What Was Audited</h4>
            <div style="background:rgba(255,255,255,0.05); padding:0.85rem; border-radius:var(--radius-md); font-size:0.85rem; color:var(--text-primary); border-left:3px solid var(--accent-blue); line-height:1.5;">
                "${inputPreview}"
            </div>
            <div style="font-size:0.68rem; color:var(--text-muted); margin-top:0.3rem; font-style:italic;">
                This is the AI claim or text that was submitted to VeriAI for trust auditing. The system checked it against the FAISS knowledge base for truth, analyzed it for demographic bias, and produced the scores above.
            </div>
        </div>

        <!-- Auto-Corrected Output (only shown if exists) -->
        ${item.corrected_output ? `
        <div style="margin-bottom:1.25rem;">
            <h4 style="font-size:0.82rem; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.05em; margin-bottom:0.4rem;">Auto-Corrected Output</h4>
            <div style="background:rgba(16,185,129,0.05); padding:0.85rem; border-radius:var(--radius-md); font-size:0.85rem; color:var(--text-primary); border-left:3px solid var(--accent-emerald); line-height:1.5;">
                ${correctedOutput}
            </div>
            <div style="font-size:0.68rem; color:var(--text-muted); margin-top:0.3rem; font-style:italic;">
                VeriAI auto-corrected the original AI output using verified knowledge from the FAISS vector store. Review this correction before approving.
            </div>
        </div>
        ` : ''}

        <!-- Risk Analysis -->
        <div style="background:rgba(244,63,94,0.04); border:1px solid rgba(244,63,94,0.15); padding:1rem; border-radius:var(--radius-md); margin-bottom:1.5rem;">
            <h4 style="font-size:0.82rem; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.05em; margin-bottom:0.6rem;">⚠️ Risk Analysis</h4>
            ${risks.map(r => '<div style="display:flex; align-items:flex-start; gap:0.5rem; margin-bottom:0.5rem;"><span style="font-size:0.85rem;">' + r.icon + '</span><div><div style="font-size:0.82rem; font-weight:600; color:' + r.color + ';">' + r.label + '</div><div style="font-size:0.75rem; color:var(--text-secondary); line-height:1.4;">' + r.desc + '</div></div></div>').join('')}
        </div>

        <!-- Actions -->
        ${!isActioned ? `
        <div style="display:flex; gap:0.75rem; margin-bottom:1.25rem;">
            <button class="btn" id="btn-approve" style="flex:1; background:var(--accent-green); color:white; justify-content:center; font-weight:600;">✅ Approve</button>
            <button class="btn" id="btn-reject" style="flex:1; background:var(--accent-blue); color:white; justify-content:center; font-weight:600;">❌ Reject</button>
            <button class="btn" id="btn-escalate" style="flex:1; background:var(--accent-red); color:white; justify-content:center; font-weight:600;">🚨 Escalate</button>
        </div>
        <div id="action-result" style="display:none; padding:0.75rem; border-radius:var(--radius-md); font-size:0.85rem; margin-bottom:1rem;"></div>
        <div>
            <h4 style="font-size:0.82rem; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.05em; margin-bottom:0.4rem;">Reviewer Notes (RLHF Feedback)</h4>
            <textarea class="form-textarea" id="review-notes" placeholder="Your feedback improves the model. Describe why you approved, rejected, or escalated this item..." style="min-height:70px; background:rgba(255,255,255,0.02); font-size:0.82rem;">${reviewerNotes}</textarea>
            <div style="font-size:0.68rem; color:var(--text-muted); margin-top:0.3rem;">Rejection requires notes. Your feedback is used via RLHF to retrain and improve the model's trust scoring.</div>
        </div>
        ` : `
        <div style="background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); border-radius:var(--radius-md); padding:1rem;">
            <div style="font-size:0.82rem; color:${statusColor}; font-weight:600; margin-bottom:0.3rem;">${statusText}</div>
            <div style="font-size:0.75rem; color:var(--text-muted);">Reviewed on ${item.reviewed_at || 'unknown date'}</div>
            ${item.reviewer_notes ? '<div style="font-size:0.78rem; color:var(--text-secondary); margin-top:0.5rem; padding-top:0.5rem; border-top:1px solid rgba(255,255,255,0.06);"><strong>Notes:</strong> ' + reviewerNotes + '</div>' : ''}
        </div>
        `}
    `;
}

function bindReviewActions(api, item, items, idx) {
    if (item.status !== 'pending') return; // Already actioned

    const actionResult = document.getElementById('action-result');
    const auditId = item.audit_id || item.id;
    
    const showResult = (msg, color) => {
        if (!actionResult) return;
        actionResult.style.display = 'block';
        actionResult.style.background = color === 'green' ? 'rgba(16,185,129,0.1)' : (color === 'red' ? 'rgba(244,63,94,0.1)' : 'rgba(59,130,246,0.1)');
        actionResult.style.border = '1px solid ' + (color === 'green' ? 'rgba(16,185,129,0.3)' : (color === 'red' ? 'rgba(244,63,94,0.3)' : 'rgba(59,130,246,0.3)'));
        actionResult.style.color = color === 'green' ? 'var(--accent-emerald)' : (color === 'red' ? 'var(--accent-red)' : 'var(--accent-blue)');
        actionResult.textContent = msg;
    };

    const approve = document.getElementById('btn-approve');
    const reject = document.getElementById('btn-reject');
    const escalate = document.getElementById('btn-escalate');

    if (approve) approve.addEventListener('click', async () => {
        const notes = document.getElementById('review-notes')?.value || '';
        approve.disabled = true;
        approve.textContent = '⏳ Processing...';
        const res = await api.post('/review/' + auditId + '/approve', { notes });
        if (res) {
            approve.textContent = '✅ Approved!';
            showResult('✅ Approved and released. RLHF feedback recorded.', 'green');
            item.status = 'approved';
            // Update queue item visually
            const queueEl = document.querySelector('.queue-item[data-index="' + idx + '"]');
            if (queueEl) {
                const nameEl = queueEl.querySelector('div[style*="font-weight"]');
                if (nameEl) nameEl.textContent = '✓ #' + String(item.audit_id || '').substring(0,8);
            }
        } else {
            approve.textContent = '❌ Failed';
            showResult('Failed to approve. Check backend connection.', 'red');
        }
        if (reject) reject.disabled = true;
        if (escalate) escalate.disabled = true;
    });

    if (reject) reject.addEventListener('click', async () => {
        const notes = document.getElementById('review-notes')?.value || '';
        if (!notes) { showResult('⚠️ Please provide feedback notes for rejection.', 'red'); return; }
        reject.disabled = true;
        reject.textContent = '⏳ Processing...';
        const res = await api.post('/review/' + auditId + '/reject', { notes });
        if (res) {
            reject.textContent = '❌ Rejected';
            showResult('❌ Rejected. Feedback sent to RLHF pipeline.', 'red');
            item.status = 'rejected';
            const queueEl = document.querySelector('.queue-item[data-index="' + idx + '"]');
            if (queueEl) {
                const nameEl = queueEl.querySelector('div[style*="font-weight"]');
                if (nameEl) nameEl.textContent = 'Rejected #' + String(item.audit_id || '').substring(0,8);
            }
        } else {
            reject.textContent = '❌ Failed';
            showResult('Failed to reject. Check backend connection.', 'red');
        }
        if (approve) approve.disabled = true;
        if (escalate) escalate.disabled = true;
    });

    if (escalate) escalate.addEventListener('click', async () => {
        const notes = document.getElementById('review-notes')?.value || 'Escalated for senior review';
        escalate.disabled = true;
        escalate.textContent = '⏳ Escalating...';
        const res = await api.post('/review/' + auditId + '/escalate', { notes });
        if (res) {
            escalate.textContent = '🚨 Escalated';
            showResult('🚨 Escalated to senior reviewer.', 'blue');
            item.status = 'escalated';
            const queueEl = document.querySelector('.queue-item[data-index="' + idx + '"]');
            if (queueEl) {
                const nameEl = queueEl.querySelector('div[style*="font-weight"]');
                if (nameEl) nameEl.textContent = 'Escalated #' + String(item.audit_id || '').substring(0,8);
            }
        } else {
            escalate.textContent = '🚨 Failed';
            showResult('Failed to escalate. Check backend connection.', 'red');
        }
        if (approve) approve.disabled = true;
        if (reject) reject.disabled = true;
    });
}
