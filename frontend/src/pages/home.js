export async function renderHomePage(rootEl, api) {
    // Inject custom styles for the landing page
    const styleId = "home-page-styles";
    if (!document.getElementById(styleId)) {
        const style = document.createElement('style');
        style.id = styleId;
        style.innerHTML = `
            .home-hero {
                text-align: center;
                padding: 6rem 2rem;
                margin-top: 2rem;
                position: relative;
            }
            .home-hero h1 {
                font-size: 3.5rem;
                font-weight: 700;
                margin-bottom: 1.5rem;
                background: var(--gradient-accent);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                letter-spacing: 0;
            }
            .home-hero p {
                font-size: 1.25rem;
                color: var(--text-secondary);
                max-width: 600px;
                margin: 0 auto 3rem;
                line-height: 1.6;
            }
            .hero-cta {
                display: inline-flex;
                align-items: center;
                gap: 0.75rem;
                padding: 1rem 2rem;
                font-size: 1.125rem;
                font-weight: 600;
                color: #fff;
                background: var(--gradient-accent);
                border-radius: var(--radius-lg);
                text-decoration: none;
                transition: var(--transition);
                box-shadow: var(--shadow-glow-purple);
            }
            .hero-cta:hover {
                transform: translateY(-2px);
                box-shadow: var(--shadow-glow-cyan);
            }
            
            .two-sided-crisis {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 2rem;
                margin: 4rem 0;
            }
            .crisis-card {
                background: var(--bg-card);
                border: 1px solid var(--border-glass);
                padding: 2rem;
                border-radius: var(--radius-xl);
                text-align: left;
                transition: var(--transition);
            }
            .crisis-card:hover {
                transform: translateY(-5px);
                border-color: var(--accent-purple);
            }
            .crisis-card h3 {
                font-size: 1.5rem;
                margin: 1rem 0;
                color: var(--text-primary);
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }
            .crisis-card p {
                color: var(--text-secondary);
                margin-bottom: 1.5rem;
            }
            .crisis-stat {
                font-size: 0.875rem;
                color: var(--accent-cyan);
                background: rgba(6, 182, 212, 0.1);
                padding: 0.5rem 1rem;
                border-radius: var(--radius-sm);
                font-weight: 600;
                display: inline-block;
            }

            .demo-stats-box {
                background: var(--bg-card);
                border: 1px solid var(--border-glass);
                border-radius: var(--radius-xl);
                padding: 3rem;
                margin: 4rem 0;
                text-align: center;
            }
            .demo-stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 2rem;
                margin-top: 2rem;
            }
            .demo-stat-item {
                display: flex;
                flex-direction: column;
                align-items: center;
            }
            .demo-stat-label {
                font-size: 1rem;
                color: var(--text-muted);
                margin-bottom: 0.5rem;
            }
            .demo-stat-numbers {
                font-size: 1.5rem;
                font-weight: 700;
                color: var(--text-primary);
            }
            .demo-stat-numbers span.before {
                color: var(--accent-red);
                text-decoration: line-through;
                margin-right: 0.5rem;
            }
            .demo-stat-numbers span.after {
                color: var(--accent-green);
            }
            
            .pipeline-section {
                margin: 4rem 0;
            }
            .pipeline-section h2 {
                text-align: center;
                font-size: 2.5rem;
                margin-bottom: 3rem;
                color: var(--text-primary);
            }
            .pipeline-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 1.5rem;
            }
            .pipeline-step {
                background: var(--bg-card);
                border: 1px solid var(--border-glass);
                padding: 1.5rem;
                border-radius: var(--radius-lg);
            }
            .pipeline-step-num {
                color: var(--accent-cyan);
                font-family: var(--font-mono);
                font-size: 0.875rem;
                font-weight: 600;
                margin-bottom: 0.5rem;
                display: block;
            }
            .pipeline-step h4 {
                font-size: 1.25rem;
                margin-bottom: 0.5rem;
                color: var(--text-primary);
            }
            .pipeline-step p {
                font-size: 0.875rem;
                color: var(--text-secondary);
            }
            
            .tech-stack {
                display: flex;
                justify-content: center;
                gap: 1.5rem;
                margin-top: 4rem;
                color: var(--text-muted);
                font-size: 0.875rem;
                flex-wrap: wrap;
            }
            .tech-stack span {
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }
        `;
        document.head.appendChild(style);
    }

    rootEl.innerHTML = `
        <div class="home-hero">
            <h1>End-to-End AI Fairness & Truth Auditor</h1>
            <p>We don't just build AI. We verify it's fair before it launches, and truthful every time it runs. Catch bias and hallucinations before they cause real-world harm.</p>
            <a href="#/dashboard" class="hero-cta">
                Launch Dashboard
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
            </a>
        </div>

        <div class="demo-stats-box">
            <h2>Composite Trust Score Impact</h2>
            <div class="demo-stats-grid">
                <div class="demo-stat-item">
                    <span class="demo-stat-label">Overall Trust Score</span>
                    <div class="demo-stat-numbers"><span class="before">51</span> <span class="after">→ 89</span></div>
                </div>
                <div class="demo-stat-item">
                    <span class="demo-stat-label">Bias</span>
                    <div class="demo-stat-numbers"><span class="before">38%</span> <span class="after">→ 4.2%</span></div>
                </div>
                <div class="demo-stat-item">
                    <span class="demo-stat-label">Truth</span>
                    <div class="demo-stat-numbers"><span class="before">62%</span> <span class="after">→ 94%</span></div>
                </div>
                <div class="demo-stat-item">
                    <span class="demo-stat-label">Confidence</span>
                    <div class="demo-stat-numbers"><span class="before">73%</span> <span class="after">→ 81%</span></div>
                </div>
            </div>
        </div>

        <div>
            <h2 style="text-align:center; font-size: 2.5rem; margin-bottom: 2rem;">The Two-Sided AI Trust Crisis</h2>
            <div class="two-sided-crisis">
                <div class="crisis-card">
                    <h3>⚠️ Biased Training Data</h3>
                    <p>Models learn historical discrimination and replicate it at scale. Hiring AI rejects women 40% more often for identical qualifications.</p>
                    <div class="crisis-stat">200M+ people screened by AI annually</div>
                </div>
                <div class="crisis-card">
                    <h3>🤥 Hallucinated Outputs</h3>
                    <p>LLMs generate confident but factually wrong responses. Health-advice bots cite retracted studies as current guidance.</p>
                    <div class="crisis-stat">38% of LLM medical responses contain errors</div>
                </div>
                <div class="crisis-card">
                    <h3>💥 Combined Failure</h3>
                    <p>A system that is both biased AND factually incorrect. Loan AI denies minorities citing fabricated risk statistics.</p>
                    <div class="crisis-stat">0 unified tools handle both failures today</div>
                </div>
            </div>
        </div>

        <div class="pipeline-section">
            <h2>The VeriAI Pipeline</h2>
            <p style="text-align:center; color:var(--text-secondary); margin-bottom: 3rem;">Active interception, not passive monitoring</p>
            <div class="pipeline-grid">
                <div class="pipeline-step">
                    <span class="pipeline-step-num">01 📥</span>
                    <h4>Input Ingestion</h4>
                    <p>Text, CSV, voice, or model outputs — normalized to a unified internal schema.</p>
                </div>
                <div class="pipeline-step">
                    <span class="pipeline-step-num">02 ⚡</span>
                    <h4>Parallel Analysis</h4>
                    <p>Bias scan, truth verification, cluster eval, and distribution analysis run concurrently via configurable depth control.</p>
                </div>
                <div class="pipeline-step">
                    <span class="pipeline-step-num">03 📊</span>
                    <h4>Configurable Scoring</h4>
                    <p>Trust Score = Σ(w<sub>i</sub> × metric<sub>i</sub>). Weights are configurable per industry (Healthcare, Finance, HR).</p>
                </div>
                <div class="pipeline-step">
                    <span class="pipeline-step-num">04 🔍</span>
                    <h4>SHAP Explainability</h4>
                    <p>Multi-method SHAP (Linear, Coefficient, Permutation) with caching for instant feature-level explanations.</p>
                </div>
                <div class="pipeline-step">
                    <span class="pipeline-step-num">05 🔧</span>
                    <h4>Auto-Correction</h4>
                    <p>If Trust Score < 70: applies demographic constraints, filters hallucinations, appends citations.</p>
                </div>
                <div class="pipeline-step">
                    <span class="pipeline-step-num">06 👁️</span>
                    <h4>Human-in-the-Loop</h4>
                    <p>Low-trust results (< 60%) are queued for human review. Approve, reject, or escalate before deployment.</p>
                </div>
            </div>
        </div>

        <div class="tech-stack">
            <span>🏆 PromptWars Solution Challenge 2026</span>
            <span>✧ Gemini 1.5 Pro</span>
            <span>✧ AIF360</span>
            <span>✧ GCP</span>
        </div>
    `;
}
