# Plan de monetización

## Objetivo

Convertir Tasador SD en una oferta **clara, repetible y escalable** para el
mercado inmobiliario dominicano, empezando por el ingreso que no requiere
infraestructura de pago y avanzando hacia suscripciones self-service.

## Segmentos y escalera de valor

| Segmento | Qué recibe | Plan |
|---|---|---|
| **Usuario individual** (agente, propietario) | Tasaciones rápidas, historial personal, límite mensual | Free → Pro |
| **Agencia / inmobiliaria** (foco comercial) | Reportes por sector, historial de mercado, múltiples usuarios, insights agregados | Agency |
| **Integrador / partner** (portal, proptech) | Uso del API de tasación, integración con sus sistemas | Partner API |

## Los planes

### Free — adquisición
- Tasaciones limitadas por mes (el límite ya está en la BD).
- Web básica + historial de estimaciones por usuario.
- Objetivo: que el agente pruebe el valor y lo use a diario.

### Pro — profesional individual
- Volumen mensual mayor, historial más largo.
- Reportes por sector.
- Prioridad de soporte.

### Agency — inmobiliaria
- Múltiples usuarios bajo una organización.
- Dashboards de mercado y reportes premium.
- SLA y soporte.

### Partner API — expansión B2B
- Acceso al API de tasación por API key con facturación por uso.
- Para portales e integradores que embeben la tasación en su producto.

## Lo que YA está construido (no es aspiracional)

- **Planes y límites de uso en la base de datos** (`profiles.plan` +
  `usage_counters`), aplicados por **triggers de Postgres**. Ningún cliente
  puede saltarse el límite: la regla vive en la BD, no en el navegador.
- **RLS en todas las tablas**: cada usuario solo ve sus datos; las tablas
  del agente son solo service-role.
- **La semilla del producto de reportes**: el workflow `resumen-semanal`
  de n8n ya agrega el mercado por sector — es el borrador del reporte
  mensual que se le vende a la agencia.

## El primer ingreso (sin pasarela de pago)

**Producto de entrada: reporte mensual de mercado por sector**, vendido a
inmobiliarias por **RD$ 2,000–5,000/mes**, cobrado por **transferencia
bancaria + factura manual**. No requiere Azul, CardNet ni Stripe: se vende
como un servicio profesional. Requisito técnico: datos reales acumulados
(ver [SCALABILITY-ROADMAP.md](SCALABILITY-ROADMAP.md), fase de data
flywheel) y el reporte a partir del `resumen-semanal`.

Esta secuencia es deliberada: **valida la disposición a pagar antes de
invertir en billing self-service.**

## Control de uso y billing (para los planes self-service)

1. **Control de uso** — ya existe (triggers + `usage_counters`). Falta
   exponerlo en la UI (contador de uso, aviso al acercarse al límite).
2. **Roles de organización** — cuentas de agencia con varios usuarios
   (columna `org_id`, preparada en la arquitectura, no construida aún).
3. **Pasarela de pago** — solo para Pro/Agency self-service, a partir del
   mes 2+. Stripe es lo más rápido de montar; Azul/CardNet exigen RNC y
   fees de entrada — evaluarlos cuando el volumen lo justifique.
4. **API de partners** — tabla `api_keys` con hash + facturación por uso,
   cuando exista demanda B2B.

## Recomendación de lanzamiento

Lanzar en este orden reduce el riesgo y mantiene el foco comercial:

1. **Herramienta útil para agentes** (Free/Pro) — construir uso y confianza.
2. **Reporte de mercado a agencias** (cobro por transferencia) — primer
   ingreso real, sin pasarela.
3. **Billing self-service** (Pro/Agency) — cuando haya demanda probada.
4. **API de partners** — expansión, cuando el producto tenga tracción.

El upsell natural es del dato: una tasación se consulta una vez; un
**feed de gangas y un reporte de tendencias** se pagan cada mes. Ese
historial de precios es el activo que hace el ingreso recurrente
defendible.
