// Tools the assistant may call.
//
// The rule that makes this trustworthy: the assistant NEVER estimates a
// price from memory. Every figure it states comes from the same API and the
// same weights the website uses, so a chat answer and the appraisal card
// can never disagree. This is the project's "one definition of the model"
// principle extended to the chatbot.
//
// Every tool is read-only. Nothing here writes to the database, which also
// bounds the blast radius of a prompt-injection attempt.

import {
  improvements,
  marginalValues,
  samePropertyAcrossSectors,
  sectorsWithinBudget,
  decompose,
  totalFromContributions,
} from '@/lib/advisor';
import { appraise, AppraisalInput, getModelInfo, ModelInfo } from '@/lib/api';
import { ToolResult, ToolSpec } from '@/lib/ai/types';

const PROPERTY_PROPS = {
  sector: { type: 'string', description: 'Sector de Santo Domingo' },
  area_m2: { type: 'number', description: 'Área construida en m² (20-1000)' },
  bedrooms: { type: 'number', description: 'Habitaciones (0-10)' },
  bathrooms: { type: 'number', description: 'Baños (1-10)' },
  parking_spots: { type: 'number', description: 'Parqueos (0-10)' },
  furnished: { type: 'number', description: '1 si está amueblado, 0 si no' },
  age_years: { type: 'number', description: 'Antigüedad en años (0-80)' },
};
const PROPERTY_REQUIRED = ['sector', 'area_m2', 'bedrooms', 'bathrooms'];

export const TOOLS: ToolSpec[] = [
  {
    name: 'tasar_propiedad',
    description:
      'Estima el alquiler mensual de una propiedad. Úsala SIEMPRE que necesites un precio; nunca lo calcules tú.',
    parameters: { type: 'object', properties: PROPERTY_PROPS, required: PROPERTY_REQUIRED },
  },
  {
    name: 'explicar_tasacion',
    description:
      'Descompone una tasación: cuánto aporta o resta cada característica sobre la base del mercado.',
    parameters: { type: 'object', properties: PROPERTY_PROPS, required: PROPERTY_REQUIRED },
  },
  {
    name: 'como_subir_el_valor',
    description:
      'Mejoras concretas que aumentarían el alquiler de una propiedad, ordenadas por cuánto suman en pesos.',
    parameters: { type: 'object', properties: PROPERTY_PROPS, required: PROPERTY_REQUIRED },
  },
  {
    name: 'comparar_sectores',
    description:
      'Cuánto se estimaría la MISMA propiedad en cada sector. Útil para ubicación y presupuesto.',
    parameters: {
      type: 'object',
      properties: {
        ...PROPERTY_PROPS,
        presupuesto: {
          type: 'number',
          description: 'Opcional: si se indica, solo devuelve sectores dentro de ese alquiler mensual',
        },
      },
      required: PROPERTY_REQUIRED,
    },
  },
  {
    name: 'panorama_del_mercado',
    description:
      'Alquiler promedio de cada sector cubierto y las métricas de precisión del modelo.',
    parameters: { type: 'object', properties: {} },
  },
];

function toInput(args: Record<string, unknown>): AppraisalInput {
  const n = (v: unknown, d: number) => (typeof v === 'number' && isFinite(v) ? v : d);
  return {
    sector: String(args.sector ?? ''),
    area_m2: n(args.area_m2, 80),
    bedrooms: n(args.bedrooms, 2),
    bathrooms: n(args.bathrooms, 2),
    parking_spots: n(args.parking_spots, 1),
    furnished: n(args.furnished, 0) ? 1 : 0,
    age_years: n(args.age_years, 10),
  };
}

const money = (v: number) => `RD$ ${Math.round(v).toLocaleString('en-US')}`;

export async function runTool(
  name: string,
  args: Record<string, unknown>,
  cache: { model?: ModelInfo }
): Promise<string> {
  const model = (cache.model ??= await getModelInfo());
  const w = model.weights;

  // Guard the sector early: a wrong name would silently drop the sector
  // term and produce a quietly wrong number.
  if (name !== 'panorama_del_mercado') {
    const sector = String(args.sector ?? '');
    if (!model.sectors.includes(sector)) {
      return JSON.stringify({
        error: `Sector desconocido: "${sector}"`,
        sectores_validos: model.sectors,
      });
    }
  }

  switch (name) {
    case 'tasar_propiedad': {
      const input = toInput(args);
      const a = await appraise(input);
      return JSON.stringify({
        estimado: money(a.estimate),
        rango: `${money(a.range_low)} — ${money(a.range_high)}`,
        promedio_del_sector: money(a.sector_avg),
        diferencia_vs_sector_pct: a.delta_vs_sector_pct,
        moneda: 'DOP',
        periodo: 'mensual',
      });
    }

    case 'explicar_tasacion': {
      const input = toInput(args);
      const parts = decompose(w, input);
      return JSON.stringify({
        total: money(totalFromContributions(parts)),
        componentes: parts.map((p) => ({ concepto: p.label, aporte: money(p.amount) })),
        nota: 'Los componentes suman exactamente el estimado.',
      });
    }

    case 'como_subir_el_valor': {
      const input = toInput(args);
      return JSON.stringify({
        mejoras: improvements(w, input).map((i) => ({
          accion: i.action,
          suma_al_mes: money(i.gain),
          una_sola_vez: !!i.oneOff,
        })),
        valor_marginal: Object.fromEntries(
          Object.entries(marginalValues(w)).map(([k, v]) => [k, money(v)])
        ),
      });
    }

    case 'comparar_sectores': {
      const input = toInput(args);
      const budget = typeof args.presupuesto === 'number' ? args.presupuesto : null;
      const list = budget
        ? sectorsWithinBudget(w, input, budget)
        : samePropertyAcrossSectors(w, input);
      return JSON.stringify({
        presupuesto: budget ? money(budget) : null,
        sectores: list.map((o) => ({
          sector: o.sector,
          estimado: money(o.estimate),
          diferencia: money(o.delta),
        })),
      });
    }

    case 'panorama_del_mercado':
      return JSON.stringify({
        promedios_por_sector: Object.fromEntries(
          Object.entries(model.avgPriceBySector).map(([k, v]) => [k, money(v)])
        ),
        precision_r2: model.metrics.r2,
        error_medio: money(model.metrics.mae),
        version_modelo: model.version,
      });

    default:
      return JSON.stringify({ error: `Herramienta desconocida: ${name}` });
  }
}

export function toolResult(id: string, name: string, content: string): ToolResult {
  return { id, name, content };
}
