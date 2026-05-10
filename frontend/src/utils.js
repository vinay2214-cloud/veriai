/**
 * Safe text rendering utilities for VeriAI.
 * Lightweight XSS prevention focused on demo UX safety.
 */

const HTML_ENTITIES = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
  '`': '&#96;',
};

/**
 * Escape HTML special characters to prevent XSS injection.
 * Handles &, <, >, ", ', and backtick characters.
 */
export function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"'`]/g, (char) => HTML_ENTITIES[char] || char);
}

/**
 * Sanitize user-provided text for safe display in the UI.
 * - Escapes HTML entities
 * - Trims whitespace
 * - Replaces null/undefined with a fallback string
 * - Limits length to prevent layout breakage
 */
export function sanitizeText(value, { maxLength = 500, fallback = '' } = {}) {
    if (value === null || value === undefined) return fallback;
    const str = String(value).trim();
    if (str.length === 0) return fallback;
    const truncated = str.length > maxLength ? str.slice(0, maxLength) + '…' : str;
    return escapeHtml(truncated);
}

/**
 * Safely interpolate values into an HTML template string.
 * Each value is run through sanitizeText before insertion.
 * Usage:
 *   safeRender`<div>${userInput}</div>`
 * Returns a safe HTML string where all dynamic values are escaped.
 */
export function safeRender(strings, ...values) {
    return strings.reduce((result, str, i) => {
        const val = i < values.length ? values[i] : '';
        // Numbers and booleans are safe to inline directly
        if (typeof val === 'number' || typeof val === 'boolean') {
            return result + str + String(val);
        }
        // Objects render as [object Object] — safe but noisy, so escape anyway
        return result + str + (val == null ? '' : sanitizeText(String(val)));
    }, '');
}

/**
 * Safely set innerHTML with a template literal.
 * All interpolated values are auto-escaped.
 * Returns the element for chaining.
 */
export function setSafeHTML(element, strings, ...values) {
    const html = safeRender(strings, ...values);
    element.innerHTML = html;
    return element;
}

/**
 * Create a DOM text node safely from untrusted input.
 * Prefer this over innerHTML when you don't need markup.
 */
export function safeTextNode(value) {
    return document.createTextNode(String(value ?? ''));
}

export function formatDate(value) {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '—';
    return date.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
    });
}

export function asPercent(value, digits = 0) {
    const numeric = Number(value || 0) * 100;
    return `${numeric.toFixed(digits)}%`;
}
