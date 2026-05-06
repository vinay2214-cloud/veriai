import { renderLogin } from './pages/login.js?v=19';
import { renderDashboard } from './pages/dashboard.js?v=19';
import { renderAuditPage } from './pages/audit.js?v=19';
import { renderReportsPage } from './pages/reports.js?v=19';
import { renderFeedbackPage } from './pages/feedback.js?v=19';
import { renderSettingsPage } from './pages/settings.js?v=19';
import { renderReviewPage } from './pages/review.js?v=19';

function normalizeApiBase(value) {
    return value.replace(/\/+$/, '').endsWith('/api')
        ? value.replace(/\/+$/, '')
        : `${value.replace(/\/+$/, '')}/api`;
}

function resolveApiBase() {
    const configured = window.VERIAI_API_BASE || document.querySelector('meta[name="veriai-api-base"]')?.content;
    if (configured) return normalizeApiBase(configured);

    const { protocol, hostname, port, origin } = window.location;
    const isLocal = hostname === 'localhost' || hostname === '127.0.0.1';
    const staticDevPorts = new Set(['3000', '5173', '5174', '8080']);
    if (protocol === 'file:' || (isLocal && staticDevPorts.has(port))) {
        return 'http://127.0.0.1:8000/api';
    }
    return `${origin}/api`;
}

export const API_BASE = resolveApiBase();

function showApiNotice(message) {
    let notice = document.getElementById('api-toast');
    if (!notice) {
        notice = document.createElement('div');
        notice.id = 'api-toast';
        notice.className = 'api-toast';
        document.body.appendChild(notice);
    }
    notice.textContent = message;
    notice.classList.add('visible');
    window.clearTimeout(showApiNotice.timer);
    showApiNotice.timer = window.setTimeout(() => notice.classList.remove('visible'), 4200);
}

async function parseResponse(res) {
    const text = await res.text();
    if (!text) return null;
    try {
        return JSON.parse(text);
    } catch (_err) {
        return { detail: text };
    }
}

// Simple API Client
export const apiClient = {
    async request(endpoint, options = {}) {
        try {
            const res = await fetch(`${API_BASE}${endpoint}`, options);
            const payload = await parseResponse(res);
            if (!res.ok) {
                const detail = payload?.detail || payload?.error || `HTTP ${res.status}`;
                throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
            }
            return payload;
        } catch (error) {
            console.error('API Error:', endpoint, error);
            showApiNotice(`API issue: ${error.message}`);
            return null;
        }
    },
    async get(endpoint) {
        return this.request(endpoint);
    },
    async post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    },
    async postForm(endpoint, formData) {
        return this.request(endpoint, {
            method: 'POST',
            body: formData
        });
    }
};

// Vanilla SPA Router
const routes = {
    '/': { render: renderLogin, title: 'Login - VeriAI' },
    '/dashboard': { render: renderDashboard, title: 'Dashboard' },
    '/audit': { render: renderAuditPage, title: 'Run Audit' },
    '/reports': { render: renderReportsPage, title: 'Audit Reports' },
    '/feedback': { render: renderFeedbackPage, title: 'Feedback' },
    '/settings': { render: renderSettingsPage, title: 'Settings' },
    '/review': { render: renderReviewPage, title: 'Review Queue' },
};

async function router() {
    let hash = window.location.hash.slice(1) || '/';

    // Check if route has an ID parameter (e.g., /reports/demo-001)
    let id = null;
    let baseRoute = hash;
    const parts = hash.split('/');
    if (parts.length > 2) {
        baseRoute = `/${parts[1]}`;
        id = parts[2];
    }

    const route = routes[baseRoute];
    const appRoot = document.getElementById('app-root');
    const pageTitle = document.getElementById('page-title');
    const sidebar = document.getElementById('sidebar');
    const topBar = document.querySelector('.top-bar');

    if (route) {
        const ambientGlow = document.querySelector('.ambient-glow');
        const hamburgerBtn = document.getElementById('hamburger-btn');
        const sidebarOverlay = document.getElementById('sidebar-overlay');
        // Toggle Layout for Landing Page
        if (baseRoute === '/') {
            if (sidebar) sidebar.style.display = 'none';
            if (topBar) topBar.style.display = 'none';
            if (ambientGlow) ambientGlow.style.display = 'none';
            if (hamburgerBtn) hamburgerBtn.style.display = 'none';
            if (sidebarOverlay) sidebarOverlay.style.display = 'none';
            document.querySelector('.main-content').style.marginLeft = '0';
            document.querySelector('.content-area').style.padding = '0';
        } else {
            if (sidebar) sidebar.style.display = 'flex';
            if (topBar) topBar.style.display = 'flex';
            if (ambientGlow) ambientGlow.style.display = 'block';
            if (hamburgerBtn) hamburgerBtn.style.display = '';
            if (sidebarOverlay) sidebarOverlay.style.display = '';
            const isMobile = window.matchMedia('(max-width: 768px)').matches;
            document.querySelector('.main-content').style.marginLeft = isMobile ? '0' : 'var(--sidebar-width)';
            document.querySelector('.content-area').style.padding = isMobile ? '1rem' : '2rem';
            appRoot.style.padding = '';
            appRoot.style.height = '';
            appRoot.style.overflow = '';
        }

        // Update UI
        pageTitle.textContent = route.title;
        document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
        const navEl = document.getElementById(`nav-${baseRoute.substring(1)}`);
        if (navEl) navEl.classList.add('active');

        // Render Route
        appRoot.innerHTML = '<div class="loading-overlay"><div class="loading-spinner"></div><div>Loading...</div></div>';
        try {
            await route.render(appRoot, apiClient, id);
        } catch (err) {
            console.error('Route render error:', err);
            appRoot.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">❌</div>
                    <h3 class="empty-title">Render Error</h3>
                    <div class="empty-desc" style="font-family: var(--font-mono); color: var(--accent-red);">${err.message}</div>
                </div>
            `;
        }
    } else {
        appRoot.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">404</div>
                <h3 class="empty-title">Page Not Found</h3>
            </div>
        `;
    }
}

// Init
console.log('[VeriAI] Module loaded. Hash:', window.location.hash);
window.addEventListener('hashchange', router);
// For ES modules (deferred), DOMContentLoaded may have already fired.
// Call router() immediately since the DOM is guaranteed ready when a
// type="module" script executes.
router().catch(err => console.error('[VeriAI] Router fatal error:', err));
