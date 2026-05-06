import { renderLogin } from './pages/login.js?v=17';
import { renderDashboard } from './pages/dashboard.js?v=17';
import { renderAuditPage } from './pages/audit.js?v=17';
import { renderReportsPage } from './pages/reports.js?v=17';
import { renderFeedbackPage } from './pages/feedback.js?v=17';
import { renderSettingsPage } from './pages/settings.js?v=17';
import { renderReviewPage } from './pages/review.js?v=17';

export const API_BASE = window.location.origin + '/api';

// Simple API Client
export const apiClient = {
    async get(endpoint) {
        try {
            const res = await fetch(`${API_BASE}${endpoint}`);
            if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
            return await res.json();
        } catch (error) {
            console.error('API GET Error:', error);
            return null;
        }
    },
    async post(endpoint, data) {
        try {
            const res = await fetch(`${API_BASE}${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
            return await res.json();
        } catch (error) {
            console.error('API POST Error:', error);
            return null;
        }
    },
    async postForm(endpoint, formData) {
        try {
            const res = await fetch(`${API_BASE}${endpoint}`, {
                method: 'POST',
                body: formData
            });
            if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
            return await res.json();
        } catch (error) {
            console.error('API FORM POST Error:', error);
            return null;
        }
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
            document.querySelector('.main-content').style.marginLeft = 'var(--sidebar-width)';
            document.querySelector('.content-area').style.padding = '2rem';
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
