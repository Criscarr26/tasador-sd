import { NextRequest, NextResponse } from 'next/server';

// Per-request CSP with a nonce, so script-src can drop 'unsafe-inline':
// only same-origin bundles ('self') and Next's own nonce-tagged inline
// bootstrap run. Next.js reads the nonce from the request's CSP header and
// applies it to its scripts automatically. Kept in middleware (not
// next.config headers) because the nonce must be unique per response.
export function middleware(request: NextRequest) {
  const nonce = crypto.randomUUID().replace(/-/g, '');

  const supabase = process.env.NEXT_PUBLIC_SUPABASE_URL ?? 'https://*.supabase.co';
  const api = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
  const isDev = process.env.NODE_ENV === 'development';

  const csp = [
    "default-src 'self'",
    // Dev needs 'unsafe-eval' for fast refresh; production runs on nonce only.
    `script-src 'self' 'nonce-${nonce}'${isDev ? " 'unsafe-eval'" : ''}`,
    // Styles stay 'unsafe-inline' (Next injects inline CSS; far lower XSS risk).
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    `connect-src 'self' ${supabase} ${api}`,
    "font-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join('; ');

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set('x-nonce', nonce);
  requestHeaders.set('Content-Security-Policy', csp);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set('Content-Security-Policy', csp);
  return response;
}

export const config = {
  // Skip static assets and image optimization (they need no nonce).
  matcher: [
    {
      source: '/((?!_next/static|_next/image|favicon.ico).*)',
      missing: [
        { type: 'header', key: 'next-router-prefetch' },
        { type: 'header', key: 'purpose', value: 'prefetch' },
      ],
    },
  ],
};
