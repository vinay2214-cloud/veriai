export const PUBLIC_ROUTES = ["/dashboard", "/audit", "/reports", "/review"];

export function isPublicRoute(path) {
    if (!path) return false;
    if (PUBLIC_ROUTES.includes(path)) return true;
    return PUBLIC_ROUTES.some((route) => path.startsWith(`${route}/`));
}

export function shouldRedirectToLogin(path, isAuthenticated) {
    if (isPublicRoute(path)) return false;
    return !isAuthenticated;
}

