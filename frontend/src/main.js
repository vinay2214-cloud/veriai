import { renderLogin } from './pages/login.js?v=24';
import { renderDashboard } from './pages/dashboard.js?v=24';
import { renderAuditPage } from './pages/audit.js?v=24';
import { renderReportsPage } from './pages/reports.js?v=24';
import { renderFeedbackPage } from './pages/feedback.js?v=24';
import { renderSettingsPage } from './pages/settings.js?v=24';
import { renderReviewPage } from './pages/review.js?v=24';
import { renderInsightsPage } from './pages/insights.js?v=24';
import { renderOnboardingPage } from './pages/onboarding.js?v=24';

import { sanitizeText, safeRender } from './utils.js';
import { showToast } from './security-utils.js';

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
// Expose for non-module consumers (e.g. anchor hrefs in page templates) without
// forcing a circular import of this module.
window.__VERIAI_API_BASE__ = API_BASE;

const RETRYABLE_STATUS_CODES = new Set([408, 429, 500, 502, 503, 504]);
const SAFE_RETRY_METHODS = new Set(['GET', 'HEAD']);
const MAX_REQUEST_RETRIES = 1;
const DEFAULT_REQUEST_TIMEOUT_MS = 30000;
// Audits (especially the first, cold audit on Render Free, or a thorough audit)
// legitimately run longer than 30s. Aborting them client-side discards a result the
// server actually produced. Give audit/upload endpoints a much longer budget so valid
// long-running requests are never cut off prematurely.
const LONG_RUNNING_TIMEOUT_MS = 180000;
const LONG_RUNNING_PATTERNS = [/^\/audit(?:\b|\/|$)/, /run-audit/, /\/demo\//, /\/upload-csv/];

function timeoutForEndpoint(endpoint) {
    return LONG_RUNNING_PATTERNS.some((re) => re.test(endpoint)) ? LONG_RUNNING_TIMEOUT_MS : DEFAULT_REQUEST_TIMEOUT_MS;
}

function getRequestMethod(options = {}) {
    return String(options.method || 'GET').toUpperCase();
}

function canRetryRequest(options = {}) {
    return SAFE_RETRY_METHODS.has(getRequestMethod(options));
}

function wait(ms) {
    return new Promise(resolve => window.setTimeout(resolve, ms));
}

function parseRetryAfter(value) {
    if (!value) return null;
    const seconds = Number(value);
    if (Number.isFinite(seconds)) return Math.max(0, seconds * 1000);
    const retryDate = Date.parse(value);
    if (Number.isNaN(retryDate)) return null;
    return Math.max(0, retryDate - Date.now());
}

function retryDelayMs(attempt, res) {
    const retryAfter = parseRetryAfter(res?.headers?.get?.('Retry-After'));
    if (retryAfter !== null) return Math.min(retryAfter, 6000);
    return Math.min(750 * (2 ** attempt), 6000);
}

function shouldRetryResponse(res, options, attempt) {
    return attempt < MAX_REQUEST_RETRIES
        && canRetryRequest(options)
        && RETRYABLE_STATUS_CODES.has(res.status);
}

function shouldRetryFetchError(error, options, attempt) {
    if (attempt >= MAX_REQUEST_RETRIES || !canRetryRequest(options)) return false;
    return error instanceof TypeError;
}

function withRequestTimeout(options = {}, timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS) {
    if (options.signal || typeof AbortSignal === 'undefined' || typeof AbortSignal.timeout !== 'function') {
        return options;
    }
    return { ...options, signal: AbortSignal.timeout(timeoutMs) };
}

function initMobileNavigation() {
    const btn = document.getElementById('hamburger-btn');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (!btn || !sidebar || !overlay) return;

    const closeMenu = () => {
        sidebar.classList.remove('open');
        overlay.classList.remove('visible');
    };

    btn.addEventListener('click', () => {
        sidebar.classList.toggle('open');
        overlay.classList.toggle('visible');
    });
    overlay.addEventListener('click', closeMenu);
    sidebar.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', closeMenu);
    });
}

function showApiNotice(message) {
    // Use the new showToast for consistent UX; fall back to old approach
    try {
        showToast(message, 'info', 4200);
    } catch {
        // Graceful fallback if showToast is unavailable
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
}

async function parseResponse(res) {
    const text = await res.text();
    if (!text) return null;
    try {
        return JSON.parse(text);
    } catch (_err) {
        const lowerText = text.trim().toLowerCase();
        if (lowerText.startsWith('<!doctype html') || lowerText.startsWith('<html') || lowerText.startsWith('<svg')) {
            return { detail: `Server error (HTTP ${res.status}). The service might be temporarily unavailable.` };
        }
        // Truncate other unexpectedly long text responses to avoid breaking UI
        const safeText = text.length > 200 ? text.slice(0, 200) + '...' : text;
        return { detail: safeText };
    }
}

// Simple API Client
export const apiClient = {
    async request(endpoint, options = {}) {
        let lastError = null;
        const timeoutMs = timeoutForEndpoint(endpoint);
        // Fail fast and clearly when the browser is offline — no hanging, no silent
        // null. The user gets an actionable message instead of a timeout later.
        if (typeof navigator !== 'undefined' && navigator.onLine === false) {
            showApiNotice('You appear to be offline. Reconnect and try again.');
            return null;
        }
        for (let attempt = 0; attempt <= MAX_REQUEST_RETRIES; attempt += 1) {
            try {
                const res = await fetch(`${API_BASE}${endpoint}`, withRequestTimeout(options, timeoutMs));
                const payload = await parseResponse(res);
                if (!res.ok) {
                    if (shouldRetryResponse(res, options, attempt)) {
                        await wait(retryDelayMs(attempt, res));
                        continue;
                    }
                    const detail = payload?.detail || payload?.error || `HTTP ${res.status}`;
                    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
                }
                return payload;
            } catch (error) {
                lastError = error;
                if (shouldRetryFetchError(error, options, attempt)) {
                    await wait(retryDelayMs(attempt));
                    continue;
                }
                if (error?.name === 'AbortError') {
                    const isAudit = LONG_RUNNING_PATTERNS.some((re) => re.test(endpoint));
                    showApiNotice(isAudit
                        ? 'This audit took longer than expected and timed out. Please try again, or use a lighter audit depth.'
                        : 'The request timed out. Please check your connection and try again.');
                    return null;
                }
                break;
            }
        }
        console.error('API Error:', endpoint, lastError);
        showApiNotice(`API issue: ${lastError?.message || 'Request failed'}`);
        return null;
    },
    // Phase 2 — in-flight GET deduplication. When the same GET endpoint is
    // requested again while a previous identical request is still pending
    // (e.g. a page re-render), share the in-flight promise instead of issuing a
    // second network call. Behavior-preserving (identical response) and reduces
    // duplicate parallel bursts against Render. The entry clears as soon as the
    // request settles, so later GETs always fetch fresh data.
    _inflightGets: new Map(),
    async get(endpoint) {
        const pending = this._inflightGets.get(endpoint);
        if (pending) return pending;
        const promise = this.request(endpoint).finally(() => {
            this._inflightGets.delete(endpoint);
        });
        this._inflightGets.set(endpoint, promise);
        return promise;
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
    '/insights': { render: renderInsightsPage, title: 'Executive Insights' },
    '/onboarding': { render: renderOnboardingPage, title: 'Get Started' },
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

        // Render Route with safe loading state
        appRoot.innerHTML = `<div class="loading-overlay"><div class="loading-spinner"></div><div>Loading...</div></div>`;
        try {
            await route.render(appRoot, apiClient, id);
        } catch (err) {
            console.error('Route render error:', err);
            // Use safe rendering to prevent XSS from error messages
            const safeError = sanitizeText(err.message || 'Unknown error', { maxLength: 200 });
            appRoot.innerHTML = safeRender`
                <div class="empty-state">
                    <div class="empty-icon">❌</div>
                    <h3 class="empty-title">Render Error</h3>
                    <div class="empty-desc" style="font-family: var(--font-mono); color: var(--accent-red);">${safeError}</div>
                </div>
            `;
        }
    } else {
        appRoot.innerHTML = safeRender`
            <div class="empty-state">
                <div class="empty-icon">404</div>
                <h3 class="empty-title">Page Not Found</h3>
            </div>
        `;
    }
}

// Init
initMobileNavigation();
window.addEventListener('hashchange', router);
// For ES modules (deferred), DOMContentLoaded may have already fired.
// Call router() immediately since the DOM is guaranteed ready when a
// type="module" script executes.
router().catch(err => console.error('[VeriAI] Router fatal error:', err));

// Global unhandled rejection handler — prevents crashes from breaking UX
window.addEventListener('unhandledrejection', (event) => {
    console.warn('[VeriAI] Unhandled promise rejection caught:', event.reason);
    try {
        showToast('Something unexpected happened. The demo will continue to work.', 'warning', 5000);
    } catch {
        // Silence — toast is non-critical
    }
});
