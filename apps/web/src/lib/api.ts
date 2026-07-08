// Thin client for the Tasador SD API: the web app never re-implements
// the model -- inference has exactly one source (apps/api).

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');

export interface ModelInfo {
  version: string;
  sectors: string[];
  avgPriceBySector: Record<string, number>;
  metrics: { mae: number; rmse: number; r2: number };
}

export interface AppraisalInput {
  sector: string;
  area_m2: number;
  bedrooms: number;
  bathrooms: number;
  parking_spots: number;
  furnished: number; // 1 furnished, 0 not (dataset contract)
  age_years: number;
}

export interface Appraisal {
  estimate: number;
  range_low: number;
  range_high: number;
  sector_avg: number;
  delta_vs_sector_pct: number;
  model_version: string;
}

export async function getModelInfo(): Promise<ModelInfo> {
  const response = await fetch(`${API_URL}/v1/model/params`);
  if (!response.ok) throw new Error(`API ${response.status}`);
  const body = await response.json();
  return {
    version: body.version,
    sectors: body.params.sectors,
    avgPriceBySector: body.params.avg_price_by_sector,
    metrics: body.params.metrics,
  };
}

export async function appraise(input: AppraisalInput): Promise<Appraisal> {
  const response = await fetch(`${API_URL}/v1/appraisals`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = Array.isArray(body?.detail) ? body.detail.join('; ') : `API ${response.status}`;
    throw new Error(detail);
  }
  return response.json();
}

export function formatDOP(value: number): string {
  const rounded = Math.round(value);
  const sign = rounded < 0 ? '-' : '';
  const digits = Math.abs(rounded)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return `${sign}RD$ ${digits}`;
}
