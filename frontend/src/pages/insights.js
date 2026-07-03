import { escapeHtml } from '../utils.js';

// Executive Insights (Phase 3, Tasks 4 & 6) — business intelligence, not ML metrics.
// Every number comes from /api/insights/executive (real DB aggregation). "Time saved"
// is explicitly labelled as an estimate.

const RISK_COLOR = {
    critical: 'var(--accent-red)',
    elevated: 'var(--accent-red)',
    moderate: 'var(--accent-amber)',
    low: 'var(--accent-emerald)',
};

function kpiCard(label, value, sub = '', accent = 'cyan') {
    return `
        <div class="stat-card ${accent} border-glow" style="padding:1.5rem;">
            <div class="stat-label" style="margin-bottom:0.5rem;">${escapeHtml(label)}</div>
            <div class="stat-value ${accent}" style="font-size:2.2rem; line-height:1;">${escapeHtml(String(value))}</div>
            ${sub ? `<div style="color:var(--text-muted); font-size:0.8rem; margin-top:0.5rem;">${escapeHtml(sub)}</div>` : ''}
        </div>`;
}

export async function renderInsightsPage(rootEl, api) {
    const data = await api.get('/insights/executive');
    const k = (data && data.kpis) || {};
    const risk = (data && data.business_risk_level) || { level: 'low', label: 'Low' };
    const timeSaved = (data && data.time_saved) || { hours: 0, basis: '' };
    const riskColor = RISK_COLOR[risk.level] || 'var(--text-muted)';
    const durationTxt = (k.avg_audit_duration_seconds != null)
        ? `${k.avg_audit_duration_seconds}s avg`
        : 'not tracked yet';

    rootEl.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:1rem; margin-bottom:1.5rem;">
            <div>
                <h2 style="margin:0; font-size:1.6rem;">Executive Insights</h2>
                <p style="color:var(--text-muted); margin:0.25rem 0 0;">AI trust & governance, at a business glance.</p>
            </div>
            <div style="display:flex; align-items:center; gap:0.75rem; padding:0.75rem 1.25rem; background:${riskColor}18; border:1px solid ${riskColor}55; border-radius:var(--radius-lg);">
                <span style="color:var(--text-muted); font-size:0.8rem; text-transform:uppercase; letter-spacing:0.5px;">Business Risk</span>
                <span style="color:${riskColor}; font-weight:700; font-size:1.1rem;">${escapeHtml(risk.label)}</span>
            </div>
        </div>

        <div class="grid grid-4" style="gap:1rem; margin-bottom:1rem;">
            ${kpiCard("Today's Audits", k.today_audits ?? 0, `${k.total_audits ?? 0} all-time`, 'purple')}
            ${kpiCard('Avg Trust Score', `${k.avg_trust_score ?? 0}`, 'out of 100', 'cyan')}
            ${kpiCard('High-Risk Audits', k.high_risk_audits ?? 0, 'trust below 60', 'amber')}
            ${kpiCard('Reviews Pending', k.reviews_pending ?? 0, `${k.human_reviews_completed ?? 0} completed`, 'purple')}
        </div>

        <div class="grid grid-4" style="gap:1rem; margin-bottom:1.5rem;">
            ${kpiCard('Compliance Health', `${k.compliance_health_pct ?? 0}%`, 'audits meeting the trust bar', 'emerald')}
            ${kpiCard('Datasets Processed', k.datasets_processed ?? 0, `${k.reports_generated ?? 0} reports`, 'cyan')}
            ${kpiCard('Est. Hours Saved', `${timeSaved.hours ?? 0}h`, 'vs. manual review (estimate)', 'emerald')}
            ${kpiCard('Avg Audit Time', durationTxt, 'automated pipeline', 'cyan')}
        </div>

        <div class="grid grid-2" style="gap:1.5rem;">
            <div class="card glass-card" style="box-shadow:var(--shadow-md);">
                <div class="card-header" style="border-bottom:1px solid var(--border-glass); padding-bottom:0.75rem;">
                    <h3 class="card-title" style="margin:0;">Trust Score Trend</h3>
                </div>
                <div style="height:220px; margin-top:1rem;"><canvas id="insights-trust-chart"></canvas></div>
            </div>
            <div class="card glass-card" style="box-shadow:var(--shadow-md);">
                <div class="card-header" style="border-bottom:1px solid var(--border-glass); padding-bottom:0.75rem;">
                    <h3 class="card-title" style="margin:0;">Bias Trend</h3>
                </div>
                <div style="height:220px; margin-top:1rem;"><canvas id="insights-bias-chart"></canvas></div>
            </div>
        </div>

        <div style="margin-top:1rem; color:var(--text-muted); font-size:0.78rem;">
            ${escapeHtml(timeSaved.basis || '')}
            ${data && data.generated === false ? ' · No audits yet — run an audit to populate these metrics.' : ''}
        </div>
    `;

    drawTrends(data);
}

function drawTrends(data) {
    if (typeof window.Chart === 'undefined') return;
    const trust = ((data && data.trends && data.trends.trust) || []).map(v => Math.round(v * 100));
    const bias = ((data && data.trends && data.trends.bias) || []).map(v => Math.round(v * 100));
    const labels = trust.map((_, i) => `#${i + 1}`);

    const common = {
        type: 'line',
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, max: 100, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } },
                x: { grid: { display: false }, ticks: { color: '#94a3b8' } },
            },
        },
    };

    const trustEl = document.getElementById('insights-trust-chart');
    if (trustEl) new window.Chart(trustEl, {
        ...common,
        data: { labels, datasets: [{ data: trust, borderColor: '#06b6d4', backgroundColor: 'rgba(6,182,212,0.15)', fill: true, tension: 0.35, pointRadius: 2 }] },
    });
    const biasEl = document.getElementById('insights-bias-chart');
    if (biasEl) new window.Chart(biasEl, {
        ...common,
        data: { labels: bias.map((_, i) => `#${i + 1}`), datasets: [{ data: bias, borderColor: '#f59e0b', backgroundColor: 'rgba(245,158,11,0.15)', fill: true, tension: 0.35, pointRadius: 2 }] },
    });
}
