import { escapeHtml, formatDate } from '../utils.js';

// Resolved by main.js; fall back to a same-origin relative path.
const API_BASE = window.__VERIAI_API_BASE__ || '/api';

export async function renderReportsPage(rootEl, api, id = null) {
    if (id) {
        // Detailed report view
        renderSingleReport(rootEl, api, id);
    } else {
        // List view
        const recent = await api.get('/dashboard/recent');
        rootEl.innerHTML = `
            <div class="card glass-card" style="box-shadow: var(--shadow-md); overflow:hidden;">
                <div class="card-header" style="border-bottom: 1px solid var(--border-glass); padding-bottom:1rem;">
                    <h3 class="card-title">Audit History</h3>
                    <span class="badge badge-cyan">${recent ? recent.length : 0} Records</span>
                </div>
                <div class="table-wrap">
                    <table style="width: 100%; border-collapse: collapse; font-size: 0.95rem;">
                        <thead>
                            <tr style="border-bottom: 1px solid var(--border-glass); text-align:left; color:var(--text-muted); background:rgba(255,255,255,0.02);">
                                <th style="padding: 12px 16px;">Report ID</th>
                                <th style="padding: 12px 16px;">Date</th>
                                <th style="padding: 12px 16px;">Input Snippet</th>
                                <th style="padding: 12px 16px;">Trust Score</th>
                                <th style="padding: 12px 16px;">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${recent ? recent.map(r => `
                                <tr style="border-bottom: 1px solid rgba(255,255,255,0.05); transition: background 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.05)'" onmouseout="this.style.background='transparent'">
                                    <td style="padding: 16px;"><span class="badge badge-purple" style="font-family:var(--font-mono);">${escapeHtml(String(r.audit_id || '').substring(0,8))}...</span></td>
                                    <td style="padding: 16px; color:var(--text-secondary);">${formatDate(r.created_at)}</td>
                                    <td style="padding: 16px; color:var(--text-primary); max-width:250px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escapeHtml(r.input)}</td>
                                    <td style="padding: 16px;">
                                        <span style="font-weight:600; color:${r.trust_score > 0.8 ? 'var(--accent-emerald)' : (r.trust_score > 0.5 ? 'var(--accent-amber)' : 'var(--accent-red)')}">${(r.trust_score*100).toFixed(1)}%</span>
                                    </td>
                                    <td style="padding: 16px;">
                                        <a href="#/reports/${encodeURIComponent(r.audit_id)}" class="btn btn-action" style="padding:0.4rem 1rem; font-size:0.85rem; background:rgba(255,255,255,0.05); border:1px solid var(--border-glass); border-radius:var(--radius-sm); text-decoration:none; color:var(--accent-cyan); display:inline-block;">View Details</a>
                                    </td>
                                </tr>
                            `).join('') : `<tr><td colspan="5" style="text-align:center; padding:30px; color:var(--text-muted);">No reports found in history.</td></tr>`}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    }
}

const RISK_COLOR = {
    critical: 'var(--accent-red)',
    elevated: 'var(--accent-red)',
    moderate: 'var(--accent-amber)',
    low: 'var(--accent-emerald)',
};

const STATUS_STYLE = {
    violation: { color: 'var(--accent-red)', label: '✕ Violation' },
    attention: { color: 'var(--accent-amber)', label: '! Attention' },
    pass: { color: 'var(--accent-emerald)', label: '✓ Pass' },
};

// Phase 3 — AI Compliance Officer section. Renders the consultant-grade narrative
// returned by /api/ai/compliance-report/{id}. All dynamic values are escaped.
function renderComplianceSection(resp) {
    const c = resp && resp.compliance;
    if (!c) return '';
    const risk = c.risk_level || 'low';
    const color = RISK_COLOR[risk] || 'var(--text-muted)';
    const cv = c.customer_value || {};

    const mappingRows = (c.compliance_mapping || []).map(m => {
        const s = STATUS_STYLE[m.status] || { color: 'var(--text-muted)', label: escapeHtml(m.status || '') };
        return `<tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
            <td style="padding:10px 14px; color:var(--text-primary);">${escapeHtml(m.framework || '')}<div style="color:var(--text-muted); font-size:0.78rem; margin-top:2px;">${escapeHtml(m.reference || '')}</div></td>
            <td style="padding:10px 14px; white-space:nowrap; font-weight:600; color:${s.color};">${s.label}</td>
            <td style="padding:10px 14px; color:var(--text-secondary); font-size:0.88rem;">${escapeHtml(m.finding || '')}</td>
        </tr>`;
    }).join('');

    const recs = (c.recommendations || []).map(r => `<li style="margin-bottom:0.5rem; color:var(--text-secondary);">${escapeHtml(r)}</li>`).join('');
    const actions = (c.next_actions || []).map(a => `
        <div style="display:flex; align-items:center; gap:0.75rem; padding:0.65rem 0.9rem; background:rgba(255,255,255,0.03); border:1px solid var(--border-glass); border-radius:var(--radius-sm); margin-bottom:0.5rem;">
            <span class="badge ${a.urgency === 'immediate' ? 'badge-purple' : 'badge-cyan'}" style="text-transform:capitalize;">${escapeHtml(a.urgency || '')}</span>
            <span style="color:var(--text-primary); flex:1;">${escapeHtml(a.action || '')}</span>
            <span style="color:var(--text-muted); font-size:0.82rem;">${escapeHtml(a.owner || '')}</span>
        </div>`).join('');

    const valueRow = (label, val) => `
        <div style="display:flex; flex-direction:column; gap:0.25rem; padding:0.75rem 1rem; background:rgba(0,0,0,0.2); border-radius:var(--radius-sm); border-left:3px solid ${color};">
            <span style="color:var(--text-muted); font-size:0.78rem; text-transform:uppercase; letter-spacing:0.5px;">${escapeHtml(label)}</span>
            <span style="color:var(--text-primary); font-size:0.92rem;">${escapeHtml(val || '—')}</span>
        </div>`;

    return `
    <div class="card glass-card" style="box-shadow: var(--shadow-lg); margin-top:1.5rem;">
        <div class="card-header" style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-glass); padding-bottom:1rem;">
            <h3 class="card-title" style="margin:0; display:flex; align-items:center; gap:0.75rem;">
                🧑‍⚖️ AI Compliance Officer
            </h3>
            <span class="badge" style="background:${color}22; color:${color}; border:1px solid ${color}55; font-weight:600;">${escapeHtml(c.headline || '')}</span>
        </div>

        <div style="margin-top:1.5rem;">
            <h4 style="color:var(--text-muted); font-size:0.85rem; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:0.5rem;">Executive Summary</h4>
            <p style="color:var(--text-primary); line-height:1.65; margin-bottom:1.25rem;">${escapeHtml(c.executive_summary || '')}</p>
            <h4 style="color:var(--text-muted); font-size:0.85rem; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:0.5rem;">Business Risk</h4>
            <p style="color:var(--text-secondary); line-height:1.65;">${escapeHtml(c.business_risk_summary || '')}</p>
        </div>

        <div style="margin-top:1.5rem;">
            <h4 style="color:var(--text-muted); font-size:0.85rem; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:0.75rem;">What this means for you</h4>
            <div class="grid grid-3" style="gap:0.75rem;">
                ${valueRow('What happened', cv.what)}
                ${valueRow('Why', cv.why)}
                ${valueRow('Business impact', cv.business_impact)}
                ${valueRow('Compliance impact', cv.compliance_impact)}
                ${valueRow('Recommended action', cv.recommended_action)}
                ${valueRow('Who should review', cv.who_should_review)}
            </div>
        </div>

        <div style="margin-top:1.5rem;">
            <h4 style="color:var(--text-muted); font-size:0.85rem; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:0.75rem;">Compliance Mapping</h4>
            <div class="table-wrap">
                <table style="width:100%; border-collapse:collapse; font-size:0.9rem;">
                    <thead><tr style="text-align:left; color:var(--text-muted); border-bottom:1px solid var(--border-glass);">
                        <th style="padding:8px 14px;">Framework</th><th style="padding:8px 14px;">Status</th><th style="padding:8px 14px;">Finding</th>
                    </tr></thead>
                    <tbody>${mappingRows}</tbody>
                </table>
            </div>
        </div>

        <div class="grid grid-2" style="margin-top:1.5rem; gap:1.5rem;">
            <div>
                <h4 style="color:var(--text-muted); font-size:0.85rem; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:0.75rem;">Recommendations</h4>
                <ul style="padding-left:1.1rem; margin:0;">${recs}</ul>
            </div>
            <div>
                <h4 style="color:var(--text-muted); font-size:0.85rem; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:0.75rem;">Next Actions</h4>
                ${actions}
            </div>
        </div>
        <div style="margin-top:1rem; color:var(--text-muted); font-size:0.75rem; text-align:right;">Generated by ${escapeHtml(c.generated_by || 'VeriAI')} · ${escapeHtml(c.engine || 'deterministic')}</div>
    </div>`;
}

async function renderSingleReport(rootEl, api, id) {
    const [report, complianceResp] = await Promise.all([
        api.get(`/report/${id}`),
        api.get(`/ai/compliance-report/${id}`).catch(() => null),
    ]);
    if (!report || report.error) {
        rootEl.innerHTML = `<div class="empty-state"><div class="empty-icon">⚠️</div><h3 class="empty-title">Report not found</h3></div>`;
        return;
    }

    rootEl.innerHTML = `
        <div style="margin-bottom:1.5rem; display:inline-block;">
            <a href="#/reports" class="btn btn-action" style="display:flex; align-items:center; gap:0.5rem; color:var(--text-muted); text-decoration:none; padding:0.5rem 1rem; background:rgba(255,255,255,0.05); border-radius:var(--radius-md); border:1px solid var(--border-glass);">
               <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M19 12H5M12 19l-7-7 7-7"/></svg> Back to Reports
            </a>
        </div>
        
        <div class="card glass-card" style="box-shadow: var(--shadow-lg);">
            <div class="card-header" style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-glass); padding-bottom:1rem;">
                <h3 class="card-title" style="margin:0; display:flex; align-items:center; gap:0.75rem;">
                    <svg width="24" height="24" fill="none" stroke="var(--accent-purple)" stroke-width="2" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z"/><path d="M14 3v5h5M16 13H8M16 17H8M10 9H8"/></svg>
                    Audit Report Document
                </h3>
                <span class="badge badge-purple" style="font-family:var(--font-mono); font-size:0.9rem;">ID: ${escapeHtml(report.audit_id)}</span>
            </div>
            
            <div class="grid grid-2" style="margin-top:2rem; gap:2rem;">
                <!-- Left: Payload & Output -->
                <div style="display:flex; flex-direction:column; gap:1.5rem;">
                    <div>
                        <h4 style="font-size:0.95rem; color:var(--text-muted); margin-bottom:0.75rem; display:flex; align-items:center; gap:0.5rem;">
                            <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M13 10V3L4 14h7v7l9-11h-7z"/></svg> 
                            Original Input Payload
                        </h4>
                        <div style="background:rgba(0,0,0,0.3); padding:1.25rem; border-radius:var(--radius-md); border:1px solid var(--border-glass); font-size:0.9rem; font-family:var(--font-mono); color:var(--text-secondary); word-break:break-all; max-height:200px; overflow-y:auto; box-shadow: inset 0 2px 10px rgba(0,0,0,0.5);">
                            ${escapeHtml(report.input)}
                        </div>
                    </div>
                    
                    <div>
                        <h4 style="font-size:0.95rem; color:var(--accent-emerald); margin-bottom:0.75rem; display:flex; align-items:center; gap:0.5rem;">
                            <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg>
                            VeriAI Safely Corrected Output
                        </h4>
                        <div style="background:linear-gradient(145deg, rgba(16,185,129,0.05), rgba(52,211,153,0.1)); border:1px solid rgba(16,185,129,0.3); padding:1.25rem; border-radius:var(--radius-md); font-size:0.95rem; color:var(--text-primary); text-shadow: 0 0 1px rgba(255,255,255,0.1); line-height: 1.6;">
                            ${report.corrected ? escapeHtml(report.corrected) : '<span style="color:var(--text-muted); font-style:italic;">No corrections were required for this payload.</span>'}
                        </div>
                    </div>
                </div>
                
                <!-- Right: Score Summary -->
                <div style="display:flex; flex-direction:column; gap:1rem;">
                    <div class="stat-card purple" style="margin-bottom:0.5rem; display:flex; flex-direction:column; justify-content:center; align-items:center; padding:2rem; box-shadow: var(--shadow-glow-purple);">
                        <div class="stat-label" style="font-size:1.1rem; text-transform:uppercase; letter-spacing:1px; margin-bottom:1rem;">Final Trust Validation</div>
                        <div class="stat-value purple glow-text" style="font-size:4.5rem; line-height:1;">${(report.trust_score*100).toFixed(1)}%</div>
                    </div>
                    
                    <div class="grid grid-2" style="gap:1rem;">
                         <div class="stat-card cyan border-glow" style="padding:1.5rem; text-align:center;">
                            <div class="stat-label" style="margin-bottom:0.5rem;">Factual Truth</div>
                            <div class="stat-value cyan" style="font-size:2rem;">${(report.truth_score*100).toFixed(1)}%</div>
                        </div>
                        <div class="stat-card amber border-glow" style="padding:1.5rem; text-align:center;">
                            <div class="stat-label" style="margin-bottom:0.5rem;">Bias Detection</div>
                            <div class="stat-value amber" style="font-size:2rem;">${(report.bias_score*100).toFixed(1)}%</div>
                        </div>
                    </div>
                    
                    <div style="margin-top:auto; padding-top:1.5rem;">
                        <div style="display:flex; gap:0.5rem;">
                            <a class="btn btn-action" href="${API_BASE}/reports/${encodeURIComponent(report.audit_id)}/export?format=pdf" style="flex:1; padding:0.75rem; background:rgba(255,255,255,0.05); color:var(--text-primary); border:1px solid var(--border-glass); border-radius:var(--radius-md); display:flex; align-items:center; justify-content:center; gap:0.5rem; text-decoration:none;">
                                <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg> Export PDF
                            </a>
                            <a class="btn btn-action" href="${API_BASE}/reports/${encodeURIComponent(report.audit_id)}/export?format=json" style="flex:1; padding:0.75rem; background:rgba(59,130,246,0.08); color:var(--accent-cyan); border:1px solid rgba(59,130,246,0.25); border-radius:var(--radius-md); display:flex; align-items:center; justify-content:center; gap:0.5rem; text-decoration:none;">
                                JSON
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Phase 3 — append the AI Compliance Officer narrative below the score card.
    rootEl.insertAdjacentHTML('beforeend', renderComplianceSection(complianceResp));
}
