// Asesor de valor: turns the model's own weights into advice.
//
// The appraiser answers "how much". This answers "why" and "what would
// change it" -- and it does so by arithmetic on the deployed model, not by
// generation, so it can never contradict the appraisal or invent a figure.
//
// The pipeline is: one-hot(sector) + StandardScaler(numeric) -> LinearRegression
//
//   price = intercept + coef_sector + Σ coef_i · (x_i − mean_i) / scale_i
//
// Therefore one extra unit of a numeric feature is worth exactly
// coef_i / scale_i pesos. Verified against the model's own reference case
// (Piantini, 120 m² -> RD$ 83,862).

import type { AppraisalInput, ModelWeights } from '@/lib/api';

export interface Contribution {
  /** Machine key: sector | area_m2 | bedrooms | ... | base */
  feature: string;
  label: string;
  /** Pesos this component adds to (or subtracts from) the estimate. */
  amount: number;
}

export interface Improvement {
  feature: string;
  label: string;
  /** What the owner would change, in plain Spanish. */
  action: string;
  /** Pesos per month gained. Always positive here. */
  gain: number;
  /** True when it is a one-off state change (furnishing) rather than a unit. */
  oneOff?: boolean;
}

const LABELS: Record<string, string> = {
  area_m2: 'Área',
  bedrooms: 'Habitaciones',
  bathrooms: 'Baños',
  parking_spots: 'Parqueos',
  furnished: 'Amueblado',
  age_years: 'Antigüedad',
};

/** Pesos gained per one extra unit of each numeric feature. */
export function marginalValues(w: ModelWeights): Record<string, number> {
  const out: Record<string, number> = {};
  const offset = w.sectors.length;
  w.numericFeatures.forEach((name, i) => {
    const scale = w.scalerScale[i];
    // A zero-variance feature would make this blow up; skip instead.
    out[name] = scale ? w.coef[offset + i] / scale : 0;
  });
  return out;
}

/** Pesos each sector adds relative to the model's baseline. */
export function sectorPremiums(w: ModelWeights): Record<string, number> {
  const out: Record<string, number> = {};
  w.sectors.forEach((s, i) => {
    out[s] = w.coef[i];
  });
  return out;
}

function numericValue(input: AppraisalInput, name: string): number {
  return (input as unknown as Record<string, number>)[name] ?? 0;
}

/**
 * Break an appraisal into what each characteristic contributes.
 * The parts add up to the model's prediction, so the panel is auditable.
 */
export function decompose(w: ModelWeights, input: AppraisalInput): Contribution[] {
  const offset = w.sectors.length;
  const parts: Contribution[] = [
    { feature: 'base', label: 'Base del mercado', amount: w.intercept },
  ];

  const sectorIndex = w.sectors.indexOf(input.sector);
  if (sectorIndex >= 0) {
    parts.push({
      feature: 'sector',
      label: `Sector: ${input.sector}`,
      amount: w.coef[sectorIndex],
    });
  }

  w.numericFeatures.forEach((name, i) => {
    const scale = w.scalerScale[i];
    if (!scale) return;
    const standardized = (numericValue(input, name) - w.scalerMean[i]) / scale;
    parts.push({
      feature: name,
      label: LABELS[name] ?? name,
      amount: w.coef[offset + i] * standardized,
    });
  });

  return parts;
}

/** The estimate rebuilt from its parts. Used to self-check the breakdown. */
export function totalFromContributions(parts: Contribution[]): number {
  return parts.reduce((sum, p) => sum + p.amount, 0);
}

/**
 * Ranked, actionable ways to raise the rent, given what the property
 * already has. Only suggests what is physically sensible: no "remove a
 * year of age", no furnishing something already furnished.
 */
export function improvements(w: ModelWeights, input: AppraisalInput): Improvement[] {
  const m = marginalValues(w);
  const list: Improvement[] = [];

  if (m.parking_spots > 0 && input.parking_spots < 4) {
    list.push({
      feature: 'parking_spots',
      label: 'Parqueo',
      action: 'Añadir un parqueo',
      gain: m.parking_spots,
    });
  }

  if (m.furnished > 0 && input.furnished === 0) {
    list.push({
      feature: 'furnished',
      label: 'Amueblado',
      action: 'Amueblar la propiedad',
      gain: m.furnished,
      oneOff: true,
    });
  }

  if (m.bathrooms > 0 && input.bathrooms < 5) {
    list.push({
      feature: 'bathrooms',
      label: 'Baño',
      action: 'Añadir un baño',
      gain: m.bathrooms,
    });
  }

  if (m.bedrooms > 0 && input.bedrooms < 6) {
    list.push({
      feature: 'bedrooms',
      label: 'Habitación',
      action: 'Añadir una habitación',
      gain: m.bedrooms,
    });
  }

  if (m.area_m2 > 0) {
    list.push({
      feature: 'area_m2',
      label: 'Área',
      action: 'Ampliar 10 m²',
      gain: m.area_m2 * 10,
    });
  }

  return list.sort((a, b) => b.gain - a.gain);
}

export interface SectorOption {
  sector: string;
  estimate: number;
  /** Difference against the property's current sector. */
  delta: number;
}

/**
 * What the very same property would rent for in every other sector.
 * Answers "where does my budget go further" and "what does location cost".
 */
export function samePropertyAcrossSectors(
  w: ModelWeights,
  input: AppraisalInput
): SectorOption[] {
  const current = totalFromContributions(decompose(w, input));
  return w.sectors
    .map((sector) => {
      const estimate = totalFromContributions(decompose(w, { ...input, sector }));
      return { sector, estimate, delta: estimate - current };
    })
    .sort((a, b) => b.estimate - a.estimate);
}

/**
 * Sectors where a given monthly budget is enough for this property, best
 * value first (most square metres per peso).
 */
export function sectorsWithinBudget(
  w: ModelWeights,
  input: AppraisalInput,
  budget: number
): SectorOption[] {
  return samePropertyAcrossSectors(w, input)
    .filter((o) => o.estimate <= budget)
    .sort((a, b) => a.estimate - b.estimate);
}
