# Estructura productiva y escalable

## Principio rector

El proyecto se organiza como **un producto con una sola cara hacia el
cliente**, no como un conjunto de demos o repos sueltos. Cada carpeta de
primer nivel corresponde a una responsabilidad de negocio clara, de modo
que un cliente, un inversionista o un desarrollador nuevo entienda el
producto sin leer código.

## Las cuatro capas del producto

| Capa | Carpeta(s) | Responsabilidad de negocio |
|---|---|---|
| **Producto** | `apps/web` | La cara comercial: lo que el cliente abre y por lo que paga |
| **Motor / contrato** | `apps/api`, `api/`, `packages/core_py` | Inferencia estable y una sola definición del modelo |
| **Data flywheel** | `services/` | Ingesta de datos reales, validación y automatización que mejora el producto con el uso |
| **Operación** | `infra/`, `supabase/`, `.github/` | Despliegue, CI/CD, base de datos y seguridad |

## Estructura real del repositorio

```text
tasador-sd/
├─ apps/
│  ├─ web/                     # producto comercial (Next.js) — la cara que vende
│  └─ api/                     # motor de inferencia (contenedor) — contrato público estable
├─ api/                        # mismo contrato, build serverless (desplegado en Vercel)
├─ packages/
│  └─ core_py/                 # tasador-core: fuente única del dominio del modelo
├─ services/                   # automatización y data flywheel
│  ├─ listings-agent/          # recolector autónomo de listados reales (Anthropic tool use)
│  └─ n8n/                     # automatización de producto: alertas de gangas, reportes de mercado
├─ ml/
│  └─ training/                # entrenamiento reproducible; emite artefactos versionados
├─ supabase/
│  └─ migrations/              # historia formal de la BD (RLS, planes, historial de precios)
├─ infra/                      # despliegue, CI/CD y operación
│  ├─ README.md                # topología de despliegue y runbook
│  └─ ci-cd/                   # pipeline de CI y quality gates
├─ docs/                       # arquitectura, monetización y crecimiento
└─ README.md                   # narrativa comercial del producto
```

## Qué cambió respecto a "colección de demos"

1. **Una sola cara al cliente.** `apps/web` es el producto. El demo de
   Streamlit (repo aparte) queda como evidencia de portafolio, no como la
   cara del negocio. Una sola ruta de valor.

2. **El modelo no se duplica.** Toda la lógica del dominio vive en
   `packages/core_py` (tasador-core). El API la sirve; la web y la móvil la
   consumen. Ningún cliente reimplementa el modelo, y un test de paridad en
   CI lo garantiza.

3. **El data flywheel es una capa de primer nivel, no un script perdido.**
   `services/` agrupa lo que convierte el uso en un activo: el agente que
   recolecta listados reales y la automatización (n8n) que los transforma
   en alertas y reportes vendibles.

4. **La operación es explícita.** `infra/` documenta cómo se despliega,
   cómo corre el CI/CD y cómo se opera — lo que separa un producto de un
   prototipo.

## Restricciones de despliegue (por qué algunas cosas viven donde viven)

- `api/index.py`, `requirements.txt` (raíz) y `vercel.json` **deben estar
  en la raíz**: Vercel despliega la función serverless desde ahí, y
  `vercel.json` incluye `ml/training/models/model_params.json` en el
  bundle. Mover cualquiera de estos rompe el deploy en vivo.
- `apps/web` es un proyecto Vercel aparte con Root Directory `apps/web`.
- El `Dockerfile` de la raíz es el build del contenedor (self-host / HF
  Spaces) y espera ese contexto.

Estas rutas se documentan en [infra/README.md](../infra/README.md); no se
reorganizan porque el costo (romper producción) supera el beneficio
cosmético.

## Estado objetivo

Con esta estructura, el proyecto se presenta y se vende como:

- una **plataforma de tasación de alquileres** con una cara comercial clara,
- con un **API estable** y un **modelo versionado**,
- con un **data flywheel** que mejora la calidad con el uso,
- con **planes y control de uso** ya en la base de datos,
- y con un **camino de crecimiento** documentado (ver
  [SCALABILITY-ROADMAP.md](SCALABILITY-ROADMAP.md)).
