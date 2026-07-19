# CI/CD

How changes ship to production with control. The pipeline is defined in
[`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) and runs on
every push to `main` and every pull request.

## Pipeline

```
push / PR
   │
   ├─ job: python
   │    ├─ install tasador-core (editable) + pinned sklearn/pandas
   │    ├─ core contract tests        (packages/core_py)
   │    ├─ API contract tests         (apps/api)
   │    └─ serverless parity + discovery filter  (root tests/)
   │
   └─ job: web
        └─ production build           (apps/web)
```

## Quality gates (what CI guarantees)

| Gate | Where | Protects |
|---|---|---|
| **Parity contract** | `packages/core_py`, root `tests/` | The serverless API, the container API and the mobile port all reproduce the sklearn pipeline **exactly**. No client can silently drift from the model. |
| **API contract** | `apps/api` | Appraisals equal the exported reference predictions; invalid input is rejected with shared messages. |
| **Discovery filter** | root `tests/test_discovery.py` | The data agent only collects apartment detail pages in known sectors, never disallowed paths — the legal boundary of collection. |
| **Web build** | `apps/web` | The commercial surface compiles for production on every change. |

A red gate blocks the change. The parity gate is the important one: it is
what lets the product claim "one definition of the model" as a fact, not a
hope.

## Deploy (continuous)

Deployment is handled by **Vercel's GitHub integration**, not by a CI job:
every push to `main` triggers a redeploy of both Vercel projects (web and
API). This is why keeping `main` green matters — a merged change goes live.

- **Preview deploys**: pull requests get Vercel preview URLs automatically.
- **Production**: merge to `main` → live.

## Rollback

The safest rollback is `git revert` of the offending commit + push; Vercel
redeploys the previous state within a minute. Database migrations are
**forward-only** — never edit an applied migration; write a compensating
one. See the runbook in [../README.md](../README.md).

## Where this could grow (not built, on purpose)

The current setup fits the product's stage. When paying clients depend on
it, natural additions are: required status checks on `main`, a staging
environment before production, and smoke tests against the deployed URLs.
Deferred until the traffic justifies the process
([scalability roadmap](../../docs/SCALABILITY-ROADMAP.md), Fase 2).
