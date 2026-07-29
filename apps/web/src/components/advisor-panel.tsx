'use client';

import {
  Contribution,
  decompose,
  improvements,
  samePropertyAcrossSectors,
  totalFromContributions,
} from '@/lib/advisor';
import { AppraisalInput, formatDOP, ModelWeights } from '@/lib/api';

/**
 * "Asesor de valor": why the property is worth this, and what would move
 * the number. Everything here is arithmetic on the deployed model's own
 * weights, so it always agrees with the appraisal shown above it.
 */
export function AdvisorPanel({
  weights,
  input,
  estimate,
}: {
  weights: ModelWeights;
  input: AppraisalInput;
  estimate: number;
}) {
  const parts = decompose(weights, input);
  const rebuilt = totalFromContributions(parts);
  const ideas = improvements(weights, input);
  const elsewhere = samePropertyAcrossSectors(weights, input);

  // The breakdown must reconstruct the API's number. If it ever drifts (a
  // retrained model with a different shape, say), hide the panel rather
  // than show a decomposition that does not add up.
  if (Math.abs(rebuilt - estimate) > Math.max(50, estimate * 0.01)) return null;

  const swing = Math.max(...parts.filter((p) => p.feature !== 'base').map((p) => Math.abs(p.amount)), 1);
  const best = elsewhere[0];
  const currentIdx = elsewhere.findIndex((o) => o.sector === input.sector);

  return (
    <section className="container">
      <div className="section-head">
        <h2>Asesor de valor</h2>
        <span className="feed-chip">
          <i /> CALCULADO DEL MODELO
        </span>
      </div>

      <div className="advisor-grid">
        {/* Why it is worth this */}
        <div className="card">
          <div className="card-title">Por qué vale esto</div>
          <p className="advisor-lead">
            Cada característica suma o resta sobre la base del mercado. Las partes
            reconstruyen exactamente el estimado.
          </p>
          <ul className="breakdown">
            {parts.map((p) => (
              <BreakdownRow key={p.feature} part={p} swing={swing} />
            ))}
          </ul>
          <div className="breakdown-total">
            <span>Estimado</span>
            <b>{formatDOP(estimate)}</b>
          </div>
        </div>

        {/* What would raise it */}
        <div className="card">
          <div className="card-title">Cómo subir el valor</div>
          <p className="advisor-lead">
            Lo que cada mejora añadiría al alquiler mensual, según el modelo.
          </p>
          {ideas.length ? (
            <ul className="ideas">
              {ideas.map((i) => (
                <li key={i.feature}>
                  <div className="idea-text">
                    <b>{i.action}</b>
                    {i.oneOff && <span className="idea-tag">una sola vez</span>}
                  </div>
                  <span className="idea-gain">+{formatDOP(i.gain)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="advisor-lead">
              Esta propiedad ya tiene las características que más suman en su sector.
            </p>
          )}

          {best && currentIdx > 0 && (
            <p className="advisor-note">
              La misma propiedad en <b>{best.sector}</b> se estimaría en{' '}
              <b>{formatDOP(best.estimate)}</b> — {formatDOP(best.delta)} más que en{' '}
              {input.sector}. La ubicación es la palanca más grande del modelo.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

function BreakdownRow({ part, swing }: { part: Contribution; swing: number }) {
  const isBase = part.feature === 'base';
  const positive = part.amount >= 0;
  const width = isBase ? 100 : (Math.abs(part.amount) / swing) * 100;

  return (
    <li className={isBase ? 'is-base' : ''}>
      <span className="bd-label">{part.label}</span>
      <span className="bd-bar">
        <i
          className={isBase ? 'base' : positive ? 'pos' : 'neg'}
          style={{ width: `${Math.min(100, width)}%` }}
        />
      </span>
      <span className={`bd-amount ${isBase ? '' : positive ? 'pos' : 'neg'}`}>
        {isBase ? '' : positive ? '+' : '−'}
        {formatDOP(Math.abs(part.amount))}
      </span>
    </li>
  );
}
