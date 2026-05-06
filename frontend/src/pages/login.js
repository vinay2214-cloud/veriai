export async function renderLogin(rootEl, api) {
    // Remove default padding from content-area for login
    rootEl.style.padding = '0';
    rootEl.style.height = '100vh';
    rootEl.style.overflow = 'hidden';

    rootEl.innerHTML = `
        <!-- Animated grid background -->
        <div class="login-bg">
            <div class="login-grid"></div>
            <div class="login-grid-fade"></div>
        </div>

        <div class="login-wrapper">
            <!-- Branding Section -->
            <div class="login-brand-section">
                <div class="login-logo-mark">
                    <svg width="44" height="44" viewBox="0 0 28 28" fill="none">
                        <path d="M4 14l6 8 14-16" stroke="url(#loginGrad)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
                        <defs><linearGradient id="loginGrad" x1="0" y1="0" x2="28" y2="28"><stop stop-color="#06b6d4"/><stop offset="1" stop-color="#8b5cf6"/></linearGradient></defs>
                    </svg>
                </div>
                <h1 class="login-title">VeriAI</h1>
                <p class="login-subtitle">AI Trust Operations</p>
            </div>

            <!-- Login Card -->
            <div class="login-card-v2">
                <h2 class="login-card-heading">Open your audit workspace</h2>
                <p class="login-card-subtext">Review fairness, truth, correction, and human-review signals from one console.</p>

                <form id="login-form">
                    <div class="login-field">
                        <label class="login-label">Email</label>
                        <div class="login-input-wrap">
                            <span class="login-input-icon">✉</span>
                            <input type="email" class="login-input" placeholder="you@company.com" required />
                        </div>
                    </div>
                    <div class="login-field">
                        <label class="login-label">Password</label>
                        <div class="login-input-wrap">
                            <span class="login-input-icon">🔒</span>
                            <input type="password" class="login-input" placeholder="••••••••" required />
                        </div>
                    </div>
                    <div class="login-options">
                        <label class="login-remember"><input type="checkbox" checked /> Remember me</label>
                        <a href="#" class="login-forgot">Forgot password?</a>
                    </div>
                    <button type="submit" class="login-submit-btn">
                        <span>Continue</span>
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
                    </button>
                </form>

                <div class="login-divider"><span>VeriAI controls</span></div>

                <div class="login-trust-badges">
                    <span class="login-trust-badge">AES-256</span>
                    <span class="login-trust-badge">JWT Auth</span>
                    <span class="login-trust-badge">Audit Logs</span>
                </div>
            </div>
        </div>
    `;

    document.getElementById('login-form').addEventListener('submit', (e) => {
        e.preventDefault();
        const btn = e.target.querySelector('.login-submit-btn');
        btn.innerHTML = '<div class="loading-spinner" style="width:18px;height:18px;border-width:2px;"></div> Authenticating...';
        btn.disabled = true;
        setTimeout(() => {
            rootEl.style.padding = '';
            rootEl.style.height = '';
            rootEl.style.overflow = '';
            window.location.hash = '/dashboard';
        }, 800);
    });
}
