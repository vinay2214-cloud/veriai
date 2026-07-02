import { sanitizeText } from '../utils.js';
import { showToast } from '../security-utils.js';

export async function renderFeedbackPage(rootEl, api) {
    const history = await api.get('/feedback/history');

    rootEl.innerHTML = `
        <div class="grid grid-2" style="gap:2rem;">
            <!-- Feedback Form -->
            <div class="card glass-card" style="box-shadow: var(--shadow-md);">
                 <div class="card-header" style="border-bottom:1px solid var(--border-glass); padding-bottom:1rem; margin-bottom:1.5rem;">
                    <h3 class="card-title" style="display:flex; align-items:center; gap:0.75rem;">
                        <svg width="20" height="20" fill="none" stroke="var(--accent-purple)" stroke-width="2" viewBox="0 0 24 24"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
                        Submit Human Review
                    </h3>
                </div>
                <div class="form-group">
                    <label class="form-label" style="color:var(--text-secondary);">Audit ID (Optional)</label>
                    <input type="text" id="fb-audit-id" class="form-input" style="border-color:rgba(255,255,255,0.1); background:rgba(0,0,0,0.3);" placeholder="e.g. demo-001" />
                </div>
                
                <div class="form-group" style="display:flex; flex-direction:column; gap:1rem; background:rgba(255,255,255,0.02); padding:1.25rem; border-radius:var(--radius-md); border:1px solid var(--border-glass);">
                    <label style="display:flex; align-items:center; gap:0.75rem; font-size:0.95rem; cursor:pointer;" class="btn-action">
                        <input type="checkbox" id="fb-correct" checked style="width:18px; height:18px; accent-color:var(--accent-green);" /> 
                        <span style="color:var(--text-primary);">The corrected output was satisfactory</span>
                    </label>
                    <label style="display:flex; align-items:center; gap:0.75rem; font-size:0.95rem; cursor:pointer;" class="btn-action">
                        <input type="checkbox" id="fb-bias" style="width:18px; height:18px; accent-color:var(--accent-red);" /> 
                        <span style="color:var(--text-primary);">I noticed remaining demographic bias</span>
                    </label>
                </div>
                
                <div class="form-group">
                    <label class="form-label" style="color:var(--text-secondary);">Additional Context / Notes</label>
                    <textarea id="fb-notes" class="form-textarea" style="border-color:rgba(255,255,255,0.1); background:rgba(0,0,0,0.3);" placeholder="Explain what went wrong or how the correction was helpful..."></textarea>
                </div>
                
                <button id="btn-submit-fb" class="btn btn-action" style="width:100%; background: var(--gradient-accent); border:none; padding:0.85rem; font-size:1rem; font-weight:600; color:#fff; border-radius:var(--radius-md); box-shadow: var(--shadow-glow-purple); margin-top:1rem;">
                    Submit Assessment to RLHF Loop
                </button>
            </div>

            <!-- Feedback History List -->
            <div class="card glass-card" style="box-shadow: var(--shadow-md); display:flex; flex-direction:column;">
                 <div class="card-header" style="border-bottom:1px solid var(--border-glass); padding-bottom:1rem; margin-bottom:1rem;">
                    <h3 class="card-title" style="display:flex; align-items:center; gap:0.75rem;">
                        <svg width="20" height="20" fill="none" stroke="var(--accent-cyan)" stroke-width="2" viewBox="0 0 24 24"><path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                        Recent RLHF Feedback
                    </h3>
                </div>
                 <div class="table-wrap" style="flex:1;">
                    <table style="width: 100%; border-collapse: collapse; font-size: 0.95rem;">
                        <thead>
                            <tr style="border-bottom: 1px solid rgba(255,255,255,0.1); text-align:left; color:var(--text-muted);">
                                <th style="padding: 10px;">Review ID</th>
                                <th style="padding: 10px;">Satisfactory</th>
                                <th style="padding: 10px;">Bias Flag</th>
                            </tr>
                        </thead>
                        <tbody id="fb-table-body">
                            ${history && history.length > 0 ? history.slice(0, 6).map(h => `
                                <tr style="border-bottom: 1px solid rgba(255,255,255,0.03); transition: background 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.05)'" onmouseout="this.style.background='transparent'">
                                    <td style="padding: 12px 10px;"><span class="badge badge-purple" style="font-family:var(--font-mono);">${String(h.audit_id || '').substring(0,8)}</span></td>
                                    <td style="padding: 12px 10px;">${h.correct ? '<span style="color:var(--accent-emerald); font-weight:600; display:flex; align-items:center; gap:0.25rem;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M5 13l4 4L19 7"/></svg> Yes</span>' : '<span style="color:var(--accent-red); font-weight:600; display:flex; align-items:center; gap:0.25rem;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M6 18L18 6M6 6l12 12"/></svg> No</span>'}</td>
                                    <td style="padding: 12px 10px;">
                                        <span class="badge ${h.bias_flag ? 'badge-red' : 'badge-green'}">${h.bias_flag ? 'Detected' : 'Clear'}</span>
                                    </td>
                                </tr>
                            `).join('') : `<tr><td colspan="3" style="text-align:center; padding:30px; color:var(--text-muted);">No feedback logged yet.</td></tr>`}
                        </tbody>
                    </table>
                </div>
                
                <div style="background:rgba(6, 182, 212, 0.1); border:1px solid rgba(6, 182, 212, 0.3); padding:1rem; border-radius:var(--radius-md); display:flex; align-items:center; gap:0.75rem; margin-top:1rem;">
                    <svg width="24" height="24" fill="none" stroke="var(--accent-cyan)" stroke-width="2" viewBox="0 0 24 24"><path d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                    <p style="margin:0; font-size:0.85rem; color:var(--text-primary); line-height:1.4;">
                        <strong style="color:var(--accent-cyan);">Auto-Calibration Active:</strong> System automatically retrains the scoring weights when a sufficient volume of negative human feedback is gathered regarding undetected biases.
                    </p>
                </div>
            </div>
        </div>
    `;

    document.getElementById('btn-submit-fb').addEventListener('click', async () => {
        const btn = document.getElementById('btn-submit-fb');
        const defaultText = btn.innerHTML;
        btn.innerHTML = `<span class="loading-spinner" style="width:16px;height:16px;border-width:2px;display:inline-block;vertical-align:middle;margin-right:8px;"></span> Submitting...`;
        btn.disabled = true;

        const payload = {
            audit_id: document.getElementById('fb-audit-id').value || 'human-' + Math.floor(Math.random()*1000),
            correct: document.getElementById('fb-correct').checked,
            bias_flag: document.getElementById('fb-bias').checked,
            notes: document.getElementById('fb-notes').value
        };
        const res = await api.post('/feedback', payload);
        
        btn.innerHTML = defaultText;
        btn.disabled = false;

        if (res) {
            // Trigger a global Toast Notification (Needs function in window or main.js, we will just use a nice injected alert or custom toast)
            showToast(
                res.status === 'received_and_retrained' ? 'Feedback Processed! Model Weights Retrained.' : 'Assessment logged successfully to the RLHF queue.', 
                'success'
            );
            
            // Clear inputs
            document.getElementById('fb-audit-id').value = '';
            document.getElementById('fb-notes').value = '';
            document.getElementById('fb-correct').checked = true;
            document.getElementById('fb-bias').checked = false;
            
            // Refresh table smoothly
            const newHistory = await api.get('/feedback/history');
            document.getElementById('fb-table-body').innerHTML = (Array.isArray(newHistory) ? newHistory : []).slice(0, 6).map(h => `
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.03); animation: fadeUp 0.3s ease-out;">
                    <td style="padding: 12px 10px;"><span class="badge badge-purple" style="font-family:var(--font-mono);">${String(h.audit_id || '').substring(0,8)}</span></td>
                    <td style="padding: 12px 10px;">${h.correct ? '<span style="color:var(--accent-emerald); font-weight:600; display:flex; align-items:center; gap:0.25rem;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M5 13l4 4L19 7"/></svg> Yes</span>' : '<span style="color:var(--accent-red); font-weight:600; display:flex; align-items:center; gap:0.25rem;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M6 18L18 6M6 6l12 12"/></svg> No</span>'}</td>
                    <td style="padding: 12px 10px;">
                        <span class="badge ${h.bias_flag ? 'badge-red' : 'badge-green'}">${h.bias_flag ? 'Detected' : 'Clear'}</span>
                    </td>
                </tr>
            `).join('');
        }
    });

}

