# Roadmap de escalabilidad

Un camino realista de MVP a plataforma, sin over-engineering. Cada fase se
sostiene sobre la anterior; no se salta a "plataforma grande" desde el
inicio.

## Fase 1 — MVP (✅ hecho)

- Web comercial estable en producción (`apps/web`).
- API de inferencia con contrato estable (`api/` + `apps/api`).
- Modelo versionado por hash de contenido.
- Auth y historial por usuario (Supabase).

**Estado:** en vivo. La base del producto existe y funciona de punta a punta.

## Fase 2 — Operación real (⚙️ en curso)

- ✅ Rate limiting por IP (con IP real vía `X-Forwarded-For`).
- ✅ Cabeceras de seguridad + CSP con nonce por request.
- ✅ RLS en todas las tablas.
- ⬜ Observabilidad (Sentry en web + API + móvil) y alertas por error.
- ⬜ Monitoreo de disponibilidad (uptime).
- ⬜ Verificar backups de la base de datos.

**Meta:** que un fallo en producción se detecte y se atienda, no que pase
inadvertido.

## Fase 3 — Monetización (⚙️ base lista)

- ✅ Planes y límites de uso en la BD, aplicados por triggers.
- ⬜ Exponer el control de uso en la UI (contador, aviso de límite).
- ⬜ Reporte mensual de mercado por sector (primer ingreso, sin pasarela).
- ⬜ Billing self-service (Stripe) para Pro/Agency.

**Meta:** primer ingreso recurrente. Ver
[MONETIZATION-PLAN.md](MONETIZATION-PLAN.md).

## Fase 4 — Data flywheel (⚙️ construido, en activación)

El motor que convierte el uso en un activo defendible:

- ✅ Agente de recolección de listados reales (`services/listings-agent`),
  con descubrimiento por sitemap, cola y recolección responsable.
- ✅ Historial de precios: un trigger snapshotea cada cambio de precio
  (`listing_prices`) — el índice de tendencias que nadie más tiene.
- ✅ Automatización de producto (`services/n8n`): alertas de gangas,
  monitor de ingesta, resumen semanal de mercado.
- ⬜ Recolección recurrente programada (fuera de n8n: cron/GitHub Actions).
- ⬜ Reentrenar el modelo con datos reales y publicar (los clientes
  detectan la nueva versión solos).

**Meta:** el modelo mejora con el uso, y el historial de precios se vuelve
el foso competitivo. Cada semana de ingesta es historial que no se puede
recuperar después — por eso esta fase se activa temprano.

## Fase 5 — Escala comercial (multi-tenant)

- ⬜ Cuentas de organización (`org_id`) — el tenant natural del mercado
  dominicano es la inmobiliaria con varios agentes. La arquitectura ya lo
  contempla; se construye cuando exista el plan Agency con demanda.
- ⬜ Dashboards de mercado por cliente.
- ⬜ API de partners (`api_keys` con hash, facturación por uso).
- ⬜ Métricas de negocio (activación, retención, uso por plan).

**Meta:** servir a varias organizaciones sobre la misma base, sin
reescribir el producto.

## Principios de escalabilidad

- **Escala horizontal del API** — es serverless/stateless; escala solo. El
  rate limit es best-effort por instancia (documentado); un límite duro
  compartido (Redis/Upstash) se añade cuando el tráfico lo exija.
- **Versionado del modelo** — el hash de contenido ya permite reentrenar y
  propagar sin tocar los clientes.
- **Sin infraestructura antes de tiempo** — nada de Redis, colas dedicadas
  ni Kubernetes hasta que un cliente pagando lo justifique. Los puntos de
  inserción quedan definidos; la complejidad se difiere.

## Recomendación

No conviertas el proyecto en una plataforma grande desde el inicio. Hazlo
crecer desde una base sólida: un producto útil, un modelo versionado, un
API estable y un sistema de datos que mejore con el uso. El orden de las
fases es la ruta de menor riesgo hacia un negocio real.
