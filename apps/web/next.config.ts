import type { NextConfig } from "next";

// Origins the browser may talk to (Supabase auth/data + the model API).
// Read from env at build time so production tightens automatically.
const supabaseOrigin = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "https://*.supabase.co";
const apiOrigin = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Next.js dev mode needs eval for fast refresh; production does not.
const isDev = process.env.NODE_ENV === "development";

const csp = [
  "default-src 'self'",
  // Next.js injects inline bootstrap scripts, hence 'unsafe-inline'.
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  `connect-src 'self' ${supabaseOrigin} ${apiOrigin}`,
  "font-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
];

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
