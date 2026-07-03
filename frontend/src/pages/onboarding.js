// Customer onboarding / Get Started (Phase 3, Task 5). A new organization should
// immediately understand what VeriAI does and exactly what to do next.

const STEPS = [
    {
        n: '01', icon: '📤', title: 'Upload your data',
        body: 'Drag a CSV of model decisions or a text output into the Audit page. Files stay in memory — nothing sensitive is persisted.',
        cta: { label: 'Go to Audit', href: '#/audit' },
    },
    {
        n: '02', icon: '🧭', title: 'Let the AI configure the audit',
        body: 'The AI Audit Orchestrator inspects your columns and recommends the right profile, depth, compliance framework and review priority — no manual tuning required.',
    },
    {
        n: '03', icon: '⚡', title: 'Run the trust audit',
        body: 'VeriAI scores fairness (bias), factual grounding (truth) and confidence in parallel, then combines them into one Trust Score (0–100).',
    },
    {
        n: '04', icon: '🧑‍⚖️', title: 'Read the AI Compliance report',
        body: 'Every audit ships with an executive summary, business-risk narrative, framework mapping (EEOC, ECOA, EU AI Act, NIST, GDPR), recommendations and next actions.',
        cta: { label: 'View Reports', href: '#/reports' },
    },
    {
        n: '05', icon: '👁️', title: 'Human-in-the-loop review',
        body: 'Low-trust results are queued and prioritized by the AI Review Manager — severity, business impact, urgency and recommended reviewer. Your team approves or overrides.',
        cta: { label: 'Open Review Queue', href: '#/review' },
    },
    {
        n: '06', icon: '📈', title: 'Track the business impact',
        body: 'Executive Insights shows trust trends, compliance health, high-risk volume and estimated analyst hours saved — the governance story leadership cares about.',
        cta: { label: 'Executive Insights', href: '#/insights' },
    },
];

export async function renderOnboardingPage(rootEl) {
    const cards = STEPS.map(s => `
        <div class="card glass-card" style="box-shadow:var(--shadow-md); display:flex; flex-direction:column; gap:0.5rem;">
            <div style="display:flex; align-items:center; gap:0.75rem;">
                <span style="font-family:var(--font-mono); color:var(--accent-cyan); font-size:0.85rem;">${s.n}</span>
                <span style="font-size:1.4rem;">${s.icon}</span>
                <h3 style="margin:0; font-size:1.15rem; color:var(--text-primary);">${s.title}</h3>
            </div>
            <p style="color:var(--text-secondary); margin:0.25rem 0 0.5rem; line-height:1.6; font-size:0.92rem;">${s.body}</p>
            ${s.cta ? `<a href="${s.cta.href}" class="btn btn-action" style="align-self:flex-start; padding:0.5rem 1rem; background:rgba(59,130,246,0.1); color:var(--accent-cyan); border:1px solid rgba(59,130,246,0.3); border-radius:var(--radius-sm); text-decoration:none; font-size:0.85rem;">${s.cta.label} →</a>` : ''}
        </div>
    `).join('');

    rootEl.innerHTML = `
        <div style="max-width:1100px; margin:0 auto;">
            <div style="text-align:center; padding:2rem 1rem 2.5rem;">
                <h1 style="font-size:2.4rem; margin:0 0 0.75rem; background:var(--gradient-accent); -webkit-background-clip:text; -webkit-text-fill-color:transparent;">Welcome to VeriAI</h1>
                <p style="color:var(--text-secondary); max-width:640px; margin:0 auto; line-height:1.65; font-size:1.05rem;">
                    VeriAI is your AI Trust &amp; Governance platform. It audits AI systems for bias and hallucinations,
                    explains the business and compliance impact, and routes risky results to human review — so you can
                    deploy AI with evidence, not hope.
                </p>
                <a href="#/audit" class="hero-cta" style="margin-top:1.75rem; display:inline-flex; align-items:center; gap:0.75rem; padding:0.9rem 1.75rem; color:#fff; background:var(--gradient-accent); border-radius:var(--radius-lg); text-decoration:none; font-weight:600;">
                    Run your first audit →
                </a>
            </div>
            <div class="grid grid-3" style="gap:1.25rem;">
                ${cards}
            </div>
            <div class="card glass-card" style="margin-top:1.5rem; box-shadow:var(--shadow-md); display:flex; align-items:center; gap:1rem; flex-wrap:wrap; justify-content:space-between;">
                <div>
                    <h3 style="margin:0 0 0.25rem;">No data handy? Try a demo dataset.</h3>
                    <p style="color:var(--text-muted); margin:0; font-size:0.9rem;">Load a built-in hiring-bias sample to see the full flow end to end.</p>
                </div>
                <a href="#/audit" class="btn btn-action" style="padding:0.65rem 1.25rem; background:rgba(139,92,246,0.12); color:var(--accent-purple); border:1px solid rgba(139,92,246,0.3); border-radius:var(--radius-md); text-decoration:none;">Start with a demo →</a>
            </div>
        </div>
    `;
}
