# Propuesta: de tasador a plataforma SaaS inmobiliaria

*Propuesta de arquitectura y producto — 28 de julio de 2026. **Estado: pendiente de aprobación.** Nada de esto está implementado todavía.*

---

## 1. Resumen ejecutivo

La visión (plataforma SaaS con chatbot y recomendaciones proactivas) es correcta y
alcanzable. Pero hay **una tensión de secuencia que debe resolverse antes de escribir
código**, y es el punto más importante de este documento:

> **El motor de recomendaciones que se pidió necesita un inventario de propiedades
> que hoy no existe.** "Propiedades similares", "oportunidades de inversión",
> "propiedades recientemente agregadas" y "zonas según presupuesto" presuponen un
> catálogo. La tabla `listings` está **vacía**: el agente de datos nunca corrió.

Construir la interfaz de recomendaciones sobre una base vacía produciría un producto
de apariencia, no de valor — exactamente lo que la evaluación externa (47/100) señaló
como el mayor error estratégico: *construir el ecosistema antes de demostrar un
producto monetizable*.

**La buena noticia — y el hallazgo central de esta propuesta:** existe una capa de
inteligencia real, diferenciadora y honesta que **puede construirse hoy, sin un solo
dato nuevo y sin costo**. Ver §2.

---

## 2. Hallazgo: el modelo ya puede explicarse a sí mismo

`GET /v1/model/params` expone `coef`, `intercept`, `scaler_mean`, `scaler_scale`,
`numeric_features` y `sectors`. En un modelo lineal estandarizado:

```
precio = intercept + Σ coef_i · (x_i − mean_i) / scale_i
```

De donde el **valor marginal real** de cada característica es `coef_i / scale_i`, en
pesos. Esto significa que hoy, sin recolectar nada, la plataforma puede responder con
cifras exactas y verificables:

| Pregunta del usuario | De dónde sale la respuesta |
|---|---|
| ¿Por qué mi propiedad vale eso? | Descomposición de la predicción por característica |
| ¿Cuánto sube si añado un parqueo? | `coef_parking / scale_parking` |
| ¿Cuánto vale amueblarla? | `coef_furnished / scale_furnished` |
| ¿Cuánto pierde por la antigüedad? | `coef_age / scale_age × años` |
| ¿Qué gano mudando el mismo inmueble a Naco? | Diferencia entre coeficientes de sector |
| Con RD$X de presupuesto, ¿qué sectores me convienen? | Inversión del modelo por sector |

Esto entrega literalmente tres de las capacidades pedidas — *explicar el resultado de
la IA*, *sugerir mejoras para aumentar el valor* y *orientar según presupuesto* — con
tres propiedades que ninguna alternativa tiene: **es gratis, es instantáneo y es
imposible de alucinar** porque son operaciones aritméticas sobre el modelo desplegado,
no texto generado.

**Propuesta: llamarlo "Asesor de valor" y convertirlo en el diferenciador del
producto.** Un tasador dice *cuánto*. Esto dice *por qué* y *qué hacer al respecto* —
que es justamente por lo que una inmobiliaria paga.

---

## 3. Arquitectura propuesta

### 3.1 Capa de IA agnóstica de proveedor

Requisito explícito: cambiar de proveedor con el mínimo esfuerzo.

```
apps/web/src/lib/ai/
├── types.ts            ChatMessage, ToolCall, ToolResult, StreamChunk
├── provider.ts         interface AIProvider { chat(msgs, tools): AsyncIterable<StreamChunk> }
├── providers/
│   ├── anthropic.ts    Claude (por defecto)
│   ├── openai.ts       GPT
│   └── ollama.ts       modelos locales (sin costo, para desarrollo)
├── tools/              definiciones de herramientas, agnósticas del proveedor
└── index.ts            factory: getProvider() según AI_PROVIDER en env
```

Reglas de diseño:
- **Las claves viven solo en el servidor.** El navegador habla con `/api/chat` de la
  propia app; nunca con el proveedor. El `connect-src 'self'` del CSP no se toca.
- **Cambiar de proveedor = cambiar una variable de entorno.** El resto del código
  (herramientas, prompt, UI) no se entera.
- **Ollama incluido desde el día uno** para desarrollar sin gastar (encaja con el
  entorno local ya documentado en `docs/entorno-ia-local.md`).

### 3.2 El chatbot no inventa precios: usa herramientas

Principio ya vigente en el proyecto — *el modelo tiene exactamente una definición* —
extendido al chatbot. **El bot nunca estima de memoria**; llama a las mismas fuentes
que la web:

| Herramienta | Qué hace |
|---|---|
| `tasar_propiedad(...)` | `POST /v1/appraisals` — la misma API que usa la web |
| `promedio_sector(sector)` | Promedios reales del modelo |
| `explicar_tasacion(...)` | Descomposición por característica (§2) |
| `valor_marginal(caracteristica)` | Cuánto suma o resta cada mejora |
| `sectores_por_presupuesto(monto)` | Qué sectores alcanzan con ese dinero |
| `comparables(...)` | *(fase 2, requiere inventario)* |

Beneficio: una respuesta del chatbot y la tarjeta de resultado **nunca pueden
contradecirse**, porque salen del mismo endpoint. Es el mismo patrón de *tool use*
que ya domina `services/listings-agent`.

### 3.3 Motor de recomendaciones en dos niveles

```
RecommendationService
├── ModelStrategy       ← disponible HOY, sin datos nuevos, costo cero
│     mejoras de valor · sectores por presupuesto · posición vs sector
└── InventoryStrategy   ← requiere listings con datos reales
      similares · oportunidades · recién agregadas · tendencias
```

Una sola interfaz, dos estrategias. La segunda se activa cuando haya inventario
**sin reescribir la primera ni la UI**. Esto es lo que evita rehacer el proyecto,
que es justo lo que se pidió.

### 3.4 Lo que NO propongo construir todavía

Como arquitecto, señalo lo que sería sobre-ingeniería a esta escala y por qué:

| Descartado por ahora | Motivo |
|---|---|
| Microservicios | Un monorepo con API serverless escala de sobra para los primeros cientos de clientes |
| Cola de mensajes / Redis | No hay carga que lo justifique; los puntos de inserción ya están definidos |
| Multi-tenant completo (`org_id`) | Se añade cuando exista el primer plan Agencia, no antes |
| Base vectorial / RAG | Con 10 sectores y un modelo lineal, la aritmética supera al RAG en precisión y costo |

---

## 4. Qué se puede construir hoy vs qué está bloqueado

### 🟢 Hoy, sin datos nuevos y sin costo
- **Asesor de valor** (§2): explicación de la tasación, mejoras que suben el precio,
  sectores por presupuesto. *El diferenciador real.*
- **SEO**: metadatos por página, `sitemap.xml`, `robots.txt`, Open Graph, datos
  estructurados. Hoy la web es invisible para Google.
- **Analítica**: Vercel Analytics (gratis) para saber qué miran los visitantes.
- **Monitoreo de errores**: Sentry (plan gratuito).
- **Rendimiento**: la web ya renderiza dinámica por el nonce del CSP; se puede
  optimizar sin perder seguridad.
- **UX premium**: recálculo en vivo, comparación de escenarios, estados de carga
  con contenido real.

### 🟡 Requiere la API key de Anthropic (~US$5 + centavos por uso)
- **Chatbot con IA** (§3.1, §3.2).
- Nota: con Ollama local el desarrollo del chatbot cuesta **US$0**; la key solo hace
  falta para producción.

### 🔴 Bloqueado por datos reales (el agente nunca corrió)
- Propiedades similares, oportunidades de inversión, recién agregadas.
- Tendencias de mercado reales (hoy son marcadores de ejemplo en la UI).
- Comparables del mapa a nivel de propiedad.
- **Reentrenar el modelo** — sin esto no se puede cobrar con la cara seria.

---

## 5. Costos reales de operar comercialmente

Hallazgo importante para la decisión de negocio:

> ⚠️ **El plan Hobby de Vercel prohíbe el uso comercial.** En el momento en que se
> cobre a un cliente, el proyecto queda en violación de los términos y Vercel puede
> suspenderlo. Requiere **Pro: US$20/mes**.

| Concepto | Costo | Cuándo |
|---|---|---|
| Crédito Anthropic (agente de datos) | US$5 una vez | Ahora — desbloquea todo |
| Recolección continua | ~US$1-2/mes | Desde la activación |
| **Vercel Pro** | **US$20/mes** | **Antes del primer cliente que pague** |
| Supabase Pro | US$25/mes | Cuando el free tier apriete (500 MB / pausa por inactividad) |
| Chatbot en producción | ~US$1-5/mes | Con tráfico bajo, modelo Haiku |
| Dominio propio | ~US$12/año | Antes de vender |
| Sentry, Analytics | US$0 | Ahora |

**Para lanzar comercialmente: ~US$25-50/mes.** Es información que cambia el cálculo
del precio de venta: un solo cliente a RD$2,000/mes (~US$33) ya cubre la operación.

---

## 6. Secuencia propuesta

Ordenada por **valor entregado ÷ esfuerzo**, no por entusiasmo técnico.

**Fase 0 — Desbloqueo (1.5 h, US$5)**
API key → primera recolección → recurrencia. Sin esto, tres de las funciones pedidas
son imposibles y el modelo sigue siendo sintético.

**Fase 1 — El diferenciador (sin costo)**
Asesor de valor + SEO + analítica + Sentry. Es lo que convierte "otro formulario de
tasación" en un producto con criterio propio, y no depende de nada externo.

**Fase 2 — Chatbot (US$0 en desarrollo con Ollama)**
Capa agnóstica de proveedor + herramientas sobre la API real. Se desarrolla y prueba
local sin gastar; solo producción consume crédito.

**Fase 3 — Con datos reales (semanas 2-3)**
Reentrenar, reemplazar los marcadores de ejemplo por datos reales, activar
`InventoryStrategy` del motor de recomendaciones.

**Fase 4 — Comercial (con el primer cliente)**
Vercel Pro, dominio, términos y privacidad, pasarela de pagos.

---

## 7. Riesgos

| Riesgo | Severidad | Mitigación |
|---|---|---|
| Construir chatbot y recomendaciones antes que los datos | **Alta** | Fase 0 primero; Fase 1 no depende de datos |
| Vercel Hobby suspendido al cobrar | **Alta** | Pasar a Pro antes del primer cobro |
| Chatbot que alucina precios | **Alta** | Arquitectura de herramientas (§3.2): nunca estima de memoria |
| Costo del LLM sin control | Media | Límite de mensajes por plan, modelo Haiku, caché de respuestas frecuentes |
| Prompt injection vía chat | Media | El bot solo tiene herramientas de lectura; ninguna escribe en BD |
| Sobre-ingeniería | Media | §3.4: lista explícita de lo que no se construye todavía |

---

## 8. Decisión pendiente

Este documento es una **propuesta**, no un plan aprobado. La pregunta concreta es el
orden de ejecución — en particular si la Fase 1 (Asesor de valor, gratis, sin
dependencias) va antes que la Fase 2 (chatbot, requiere key), o si se prefiere
arrancar por el chatbot aun sabiendo que sus respuestas más valiosas dependen de
datos que todavía no existen.
