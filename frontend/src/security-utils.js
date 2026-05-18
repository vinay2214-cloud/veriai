/**
 * VeriAI Frontend Security Utilities
 *
 * Lightweight, demo-focused security helpers for the public prototype.
 * Provides client-side file validation, XSS-safe rendering helpers,
 * and graceful error handling without heavy auth or enterprise login.
 *
 * DESIGN DECISIONS (preserving VeriAI's public demo nature):
 * - JWTs are memory-only and cleared when the page is closed
 * - File validation is UX sugar only; server enforces real checks
 * - All helpers degrade gracefully when backend is unavailable
 */

// ---- Configuration ----
const CONFIG = Object.freeze({
  MAX_FILE_SIZE_MB: 50,
  ALLOWED_EXTENSIONS: ['.csv', '.json', '.xlsx', '.xls'],
  ALLOWED_MIME_PREFIXES: ['text/', 'application/json', 'application/vnd.openxmlformats-officedocument', 'application/vnd.ms-excel'],
  DANGEROUS_CSV_PREFIXES: ['=', '+', '@', '|', '-', '--'],
});

const RETRYABLE_STATUS_CODES = new Set([408, 429, 500, 502, 503, 504]);
const SAFE_RETRY_METHODS = new Set(['GET', 'HEAD']);
const MAX_SAFE_FETCH_RETRIES = 3;

let accessToken = null;

export const session = {
  set(token) {
    accessToken = token || null;
  },
  get() {
    return accessToken;
  },
  clear() {
    accessToken = null;
  },
  isLoggedIn() {
    return Boolean(accessToken);
  },
};

if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', () => session.clear());
}

export async function authFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  return fetch(url, { ...options, headers });
}

// ---- File Validation ----

/**
 * Client-side file pre-validation (UX sugar; server enforces real checks).
 * Returns { valid: boolean, error?: string }
 */
export function validateFileClient(file) {
  if (!file) {
    return { valid: false, error: 'No file selected.' };
  }

  // Name validation
  const name = (file.name || '').trim();
  if (!name) {
    return { valid: false, error: 'File has no name.' };
  }

  // Extension check
  const ext = '.' + name.split('.').pop()?.toLowerCase() || '';
  if (!CONFIG.ALLOWED_EXTENSIONS.includes(ext)) {
    return {
      valid: false,
      error: `Unsupported file type "${ext}". Allowed: ${CONFIG.ALLOWED_EXTENSIONS.join(', ')}`,
    };
  }

  // Size check (client-side estimate; server enforces exact limit)
  if (file.size > CONFIG.MAX_FILE_SIZE_MB * 1024 * 1024) {
    return {
      valid: false,
      error: `File exceeds ${CONFIG.MAX_FILE_SIZE_MB}MB limit (${(file.size / 1024 / 1024).toFixed(1)}MB detected).`,
    };
  }

  // Empty file check
  if (file.size === 0) {
    return { valid: false, error: 'File is empty.' };
  }

  return { valid: true };
}

/**
 * Quick heuristic check for dangerous CSV content (formula injection).
 * This is a client-side hint only; the backend does the real scan.
 */
export function hasDangerousCSVContent(text) {
  if (!text || typeof text !== 'string') return false;
  const firstChars = text.trimStart();
  return CONFIG.DANGEROUS_CSV_PREFIXES.some(prefix => firstChars.startsWith(prefix));
}

/**
 * Format a file size in human-readable form (e.g., "2.3 MB").
 */
export function formatFileSize(bytes) {
  if (bytes == null || bytes < 0) return '0 B';
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const size = bytes / Math.pow(1024, i);
  return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

// ---- Safe Rendering ----

/**
 * Sanitize a string for safe use in HTML context, URL context, or as JSON.
 * This is a superset of basic HTML escaping with context-awareness.
 *
 * @param {string} value - The user-provided value to sanitize
 * @param {'html'|'url'|'json'} context - Where the value will be used
 * @returns {string} Sanitized string
 */
export function sanitizeOutput(value, context = 'html') {
  if (value == null) return '';
  const str = String(value);

  switch (context) {
    case 'html':
      return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/`/g, '&#96;');

    case 'url':
      return encodeURIComponent(str);

    case 'json':
      try {
        return JSON.stringify(str);
      } catch {
        return '""';
      }

    default:
      return str;
  }
}

export const escHtml = (value) => sanitizeOutput(value, 'html');

export function safeText(el, value) {
  if (el) el.textContent = String(value ?? '');
  return el;
}

/**
 * Create a safe, truncated preview of a string for list displays.
 * Preserves whole words when possible.
 *
 * @param {string} value - The text to preview
 * @param {number} maxLen - Maximum character length (default 100)
 * @returns {string} Safe, truncated preview
 */
export function safePreview(value, maxLen = 100) {
  if (!value) return '';
  const sanitized = sanitizeOutput(value);
  if (sanitized.length <= maxLen) return sanitized;
  return sanitized.slice(0, maxLen - 1) + '…';
}

// ---- Graceful UI Handling ----

/**
 * Show a temporary toast notification for non-critical info/errors.
 * Uses the existing api-toast element if available, or creates one.
 *
 * @param {string} message - The message to display
 * @param {'info'|'warning'|'error'|'success'} type - Visual style
 * @param {number} duration - How long to show it (ms)
 */
export function showToast(message, type = 'info', duration = 4000) {
  let toast = document.getElementById('veriai-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'veriai-toast';
    toast.style.cssText = `
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 9999;
      padding: 12px 20px;
      border-radius: 8px;
      font-size: 0.82rem;
      font-family: 'Inter', sans-serif;
      color: #fff;
      opacity: 0;
      transform: translateY(12px);
      transition: opacity 0.3s ease, transform 0.3s ease;
      max-width: 360px;
      backdrop-filter: blur(12px);
      box-shadow: 0 8px 32px rgba(0,0,0,0.3);
      pointer-events: none;
    `;
    document.body.appendChild(toast);
  }

  // Color by type
  const colors = {
    info: 'rgba(59,130,246,0.85)',
    warning: 'rgba(245,158,11,0.85)',
    error: 'rgba(239,68,68,0.85)',
    success: 'rgba(16,185,129,0.85)',
  };
  toast.style.background = colors[type] || colors.info;
  toast.textContent = message;

  // Animate in
  requestAnimationFrame(() => {
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';
  });

  // Auto-dismiss
  clearTimeout(toast._hideTimer);
  toast._hideTimer = setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(12px)';
  }, duration);
}

function getRequestMethod(options = {}) {
  return String(options.method || 'GET').toUpperCase();
}

function canRetryRequest(options = {}) {
  return SAFE_RETRY_METHODS.has(getRequestMethod(options));
}

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function parseRetryAfter(value) {
  if (!value) return null;
  const seconds = Number(value);
  if (Number.isFinite(seconds)) return Math.max(0, seconds * 1000);
  const retryDate = Date.parse(value);
  if (Number.isNaN(retryDate)) return null;
  return Math.max(0, retryDate - Date.now());
}

function retryDelayMs(attempt, response) {
  const retryAfter = parseRetryAfter(response?.headers?.get?.('Retry-After'));
  if (retryAfter !== null) return Math.min(retryAfter, 6000);
  return Math.min(750 * (2 ** attempt), 6000);
}

function shouldRetryResponse(response, options, attempt) {
  return attempt < MAX_SAFE_FETCH_RETRIES
    && canRetryRequest(options)
    && RETRYABLE_STATUS_CODES.has(response.status);
}

function shouldRetryFetchError(err, options, attempt, hasCallerSignal) {
  if (attempt >= MAX_SAFE_FETCH_RETRIES || !canRetryRequest(options)) return false;
  if (err.name === 'AbortError' && hasCallerSignal) return false;
  return err instanceof TypeError;
}

function fallbackErrorText(text, status) {
  const lowerText = text.trim().toLowerCase();
  if (lowerText.startsWith('<!doctype html') || lowerText.startsWith('<html') || lowerText.startsWith('<svg')) {
    return `Server error (HTTP ${status}). The service might be temporarily unavailable.`;
  }
  return text.length > 200 ? text.slice(0, 200) + '...' : text;
}

/**
 * Wrapper around fetch with graceful degradation.
 * Returns { data, error } — never throws.
 * Useful for demo flows where backend might be unavailable.
 *
 * @param {string} url - The URL to fetch
 * @param {object} options - Standard fetch options
 * @returns {Promise<{data: any|null, error: string|null}>}
 */
export async function safeFetch(url, options = {}) {
  const hasCallerSignal = Boolean(options.signal);
  for (let attempt = 0; attempt <= MAX_SAFE_FETCH_RETRIES; attempt += 1) {
    try {
      const response = await fetch(url, {
        ...options,
        signal: options.signal || AbortSignal.timeout(15000), // 15s timeout
      });
      if (!response.ok) {
        let error = `HTTP ${response.status}`;
        try {
          const text = await response.text();
          if (text) {
            try {
              const body = JSON.parse(text);
              error = body.detail || body.error || error;
            } catch {
              error = fallbackErrorText(text, response.status) || error;
            }
          }
        } catch {
          // Keep the status-based fallback.
        }
        if (shouldRetryResponse(response, options, attempt)) {
          await delay(retryDelayMs(attempt, response));
          continue;
        }
        return { data: null, error };
      }
      const data = await response.json();
      return { data, error: null };
    } catch (err) {
      if (shouldRetryFetchError(err, options, attempt, hasCallerSignal)) {
        await delay(retryDelayMs(attempt));
        continue;
      }
      if (err.name === 'AbortError') {
        return { data: null, error: 'Request timed out. Check your connection and try again.' };
      }
      return { data: null, error: err.message || 'Network error. Please try again.' };
    }
  }
  return { data: null, error: 'Request failed. Please try again.' };
}

/**
 * Wrapper for form uploads with a progress callback (if XHR is needed).
 * For simple fetch-based uploads, use safeFetch directly.
 *
 * @param {string} url - Upload endpoint
 * @param {FormData} formData - The form data with file
 * @param {(pct: number) => void} onProgress - Called with 0-100
 * @returns {Promise<{data: any|null, error: string|null}>}
 */
export async function uploadWithProgress(url, formData, onProgress) {
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest();

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener('load', () => {
      try {
        const data = JSON.parse(xhr.responseText);
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve({ data, error: null });
        } else {
          resolve({ data: null, error: data.detail || data.error || `HTTP ${xhr.status}` });
        }
      } catch {
        const text = xhr.responseText || '';
        const lowerText = text.trim().toLowerCase();
        if (lowerText.startsWith('<!doctype html') || lowerText.startsWith('<html') || lowerText.startsWith('<svg')) {
          resolve({ data: null, error: `Server error (HTTP ${xhr.status}). The service might be temporarily unavailable.` });
        } else {
          const safeText = text.length > 200 ? text.slice(0, 200) + '...' : text;
          resolve({ data: null, error: safeText || `HTTP ${xhr.status}` });
        }
      }
    });

    xhr.addEventListener('error', () => {
      resolve({ data: null, error: 'Network error during upload.' });
    });

    xhr.addEventListener('abort', () => {
      resolve({ data: null, error: 'Upload was cancelled.' });
    });

    xhr.addEventListener('timeout', () => {
      resolve({ data: null, error: 'Upload timed out.' });
    });

    xhr.open('POST', url, true);
    xhr.timeout = 120000; // 2 minute timeout for uploads
    xhr.send(formData);
  });
}

export async function uploadDataset(file, onProgress) {
  const validation = validateFileClient(file);
  if (!validation.valid) {
    return { data: null, error: validation.error };
  }
  const formData = new FormData();
  formData.append('file', file);
  return uploadWithProgress('/api/upload-csv', formData, onProgress);
}

export default {
  session,
  authFetch,
  validateFileClient,
  hasDangerousCSVContent,
  formatFileSize,
  sanitizeOutput,
  escHtml,
  safeText,
  safePreview,
  showToast,
  safeFetch,
  uploadWithProgress,
  uploadDataset,
};
