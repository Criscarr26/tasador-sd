# Security Policy — Tasador SD

## Reporting a vulnerability

Please report security issues privately to **cristiancarrera1226@gmail.com**
with steps to reproduce. Do not open a public issue for undisclosed
vulnerabilities. Expect an acknowledgement within 72 hours.

## Supported versions

The `main` branch is the only supported version during pre-1.0.

## Security model (summary)

| Layer | Control |
|---|---|
| Transport | HTTPS/TLS everywhere (Supabase, API host, Vercel). HSTS on web and API. |
| Auth | Supabase Auth (JWT). Email/password; email confirmation configurable. |
| Authorization | Postgres Row Level Security — each user reads/writes only their own rows. |
| Secrets | `service_role` key only in server-side env (agent, platform vars); never shipped to clients. Publishable/anon key is public by design and safe only because RLS is enforced. |
| API CORS | Allowlist via `ALLOWED_ORIGINS`; native apps send no Origin and are unaffected. |
| API abuse | Per-IP sliding-window rate limit (`RATE_LIMIT_PER_MINUTE`, default 60). |
| Headers | CSP, `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, HSTS on web and API. |
| Input | Shared domain validation (`tasador_core.schema`) at the API; CHECK constraints and usage-limit triggers at the database. |
| Data | No card data stored. Personal data limited to email + appraisal history, isolated per user by RLS. |
| Supply chain | Pinned model/runtime versions; CI runs contract tests and the web build on every push. |

## Secret handling rules

- `.env` files are git-ignored and must never be committed.
- The `service_role` key grants full database access — treat it like a
  root password. It lives only in the agent's local `.env` and in
  platform environment variables.
- Rotate keys in the Supabase dashboard if any are exposed; revoke and
  reissue rather than editing in place.

## Pre-release checklist

See `docs/AUDITORIA-TASADOR-SD.pdf` (sections "Checklist previo al
lanzamiento" and "Checklist para producción") for the full gate.
