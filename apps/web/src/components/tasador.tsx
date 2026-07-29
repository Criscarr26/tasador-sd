'use client';

import { FormEvent, useEffect, useState } from 'react';

import { Appraisal, AppraisalInput, appraise, formatDOP, getModelInfo, ModelInfo } from '@/lib/api';
import { AdvisorPanel } from '@/components/advisor-panel';
import { Chat } from '@/components/chat';
import { SectorMap } from '@/components/sector-map';
import { isCloudConfigured, supabase } from '@/lib/supabase';
import { useSession } from '@/lib/use-session';

import 'leaflet/dist/leaflet.css';

// Placeholder rows for the "comparables" panel of the design system. They are
// rendered behind an explicit "Ejemplo" badge and are NOT market data: the
// listings table is still empty and the domain model has no geolocation.
// Swapping them for real rows is a single fetch once the agent has collected.
const COMPARABLES_EJEMPLO = [
  { calle: 'Av. Abraham Lincoln', dist: '200 m', specs: '165 m² · 3 hab · 2 baños', precio: 145000, estado: 'Alquilado' },
  { calle: 'Calle Lope de Vega', dist: '450 m', specs: '140 m² · 2 hab · 2 baños', precio: 125000, estado: 'Activo' },
  { calle: 'Av. Winston Churchill', dist: '600 m', specs: '110 m² · 2 hab · 2 baños', precio: 98000, estado: 'Activo' },
];

export function Tasador() {
  const { session } = useSession();

  const [model, setModel] = useState<ModelInfo | null>(null);
  const [apiDown, setApiDown] = useState(false);

  const [sector, setSector] = useState('Bella Vista');
  const [area, setArea] = useState('85');
  const [bedrooms, setBedrooms] = useState('2');
  const [bathrooms, setBathrooms] = useState('2');
  const [parking, setParking] = useState('1');
  const [furnished, setFurnished] = useState(false);
  const [age, setAge] = useState('10');

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<(Appraisal & { input: AppraisalInput }) | null>(null);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [fx, setFx] = useState<{ dopPerUsd: number; updated: string | null } | null>(null);

  useEffect(() => {
    getModelInfo()
      .then((info) => {
        setModel(info);
        if (!info.sectors.includes('Bella Vista')) setSector(info.sectors[0]);
      })
      .catch(() => setApiDown(true));
  }, []);

  // Reference USD rate. Same-origin route, cached server-side. If it is
  // unavailable the USD line simply does not render -- never a stale rate.
  useEffect(() => {
    fetch('/api/fx')
      .then((r) => r.json())
      .then((d) => {
        if (d?.ok && typeof d.dopPerUsd === 'number') {
          setFx({ dopPerUsd: d.dopPerUsd, updated: d.updated ?? null });
        }
      })
      .catch(() => {});
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!model) return;
    const input: AppraisalInput = {
      sector,
      area_m2: Number(area),
      bedrooms: Number(bedrooms),
      bathrooms: Number(bathrooms),
      parking_spots: Number(parking),
      furnished: furnished ? 1 : 0,
      age_years: Number(age),
    };
    setBusy(true);
    setError(null);
    setSaveStatus(null);
    try {
      const appraisal = await appraise(input);
      setResult({ ...appraisal, input });
      autoSave(input, appraisal);
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : 'No se pudo tasar. Intenta de nuevo.');
    } finally {
      setBusy(false);
    }
  }

  // Same behavior as the mobile app: every appraisal is logged to the
  // shared history when the user is signed in. Silent otherwise.
  async function autoSave(input: AppraisalInput, appraisal: Appraisal) {
    if (!isCloudConfigured || !supabase || !session) return;
    const { error: insertError } = await supabase.from('saved_estimates').insert({
      label: `${input.sector} · ${input.area_m2} m²`,
      sector: input.sector,
      area_m2: input.area_m2,
      bedrooms: input.bedrooms,
      bathrooms: input.bathrooms,
      parking_spots: input.parking_spots,
      furnished: input.furnished === 1,
      age_years: input.age_years,
      predicted_price: Math.round(appraisal.estimate),
    });
    setSaveStatus(
      insertError
        ? `No se pudo guardar en el historial: ${insertError.message}`
        : 'Guardada en tu historial.'
    );
  }

  const sectors = model?.sectors ?? [];
  const averages = model?.avgPriceBySector ?? {};
  const maxAvg = Math.max(...Object.values(averages), 1);
  const ranked = Object.entries(averages).sort((a, b) => b[1] - a[1]);

  // Real confidence: the model's R² on the hold-out set. Not invented.
  const confidence = model ? Math.round(model.metrics.r2 * 100) : null;

  return (
    <>
      {/* Hero + form, side by side (design system: dashboard header) */}
      <section className="container hero-split">
        <div className="hero-copy">
          <h1>
            El precio justo de tu alquiler,
            <br />
            <span className="accent">en segundos.</span>
          </h1>
          <p>
            Datos del mercado de Santo Domingo para propietarios, inquilinos e
            inmobiliarias. Valoración de precisión calibrada por sector, de Piantini
            y Naco en adelante.
          </p>
          <div className="hero-stats">
            <div className="stat">
              <b>{confidence !== null ? `${confidence}%` : '—'}</b>
              <span>precisión (R²)</span>
            </div>
            <div className="stat">
              <b>{model ? formatDOP(model.metrics.mae) : '—'}</b>
              <span>error medio</span>
            </div>
            <div className="stat">
              <b>{sectors.length || '—'}</b>
              <span>sectores cubiertos</span>
            </div>
          </div>
        </div>

        <form className="card form-card" onSubmit={onSubmit} aria-busy={busy} id="tasar">
          {apiDown && (
            <div className="error-banner">
              El servicio de tasación no está disponible en este momento. Intenta de nuevo
              en unos minutos.
            </div>
          )}

          {!model && !apiDown ? (
            <div>
              {[44, 44, 44, 44].map((h, i) => (
                <div key={i} className="skeleton" style={{ height: h, marginBottom: 14 }} />
              ))}
            </div>
          ) : (
            <>
              <div className="field-row">
                <div className="field">
                  <label htmlFor="sector">Sector</label>
                  <select id="sector" value={sector} onChange={(e) => setSector(e.target.value)}>
                    {sectors.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                </div>
                <Slider id="area" label="Área" value={area} onChange={setArea}
                  min={20} max={1000} step={5} unit="m²" hint="Superficie construida" />
              </div>

              <Segmented label="Habitaciones" value={bedrooms} onChange={setBedrooms}
                options={['0', '1', '2', '3', '4']} lastPlus />
              <Segmented label="Baños" value={bathrooms} onChange={setBathrooms}
                options={['1', '2', '3', '4']} lastPlus />
              <Segmented label="Parqueos" value={parking} onChange={setParking}
                options={['0', '1', '2', '3']} lastPlus />

              <Slider id="age" label="Antigüedad" value={age} onChange={setAge}
                min={0} max={80} step={1} unit="años" hint="0 = a estrenar" />

              <button
                type="button"
                className={`toggle-chip ${furnished ? 'on' : ''}`}
                role="switch"
                aria-checked={furnished}
                onClick={() => setFurnished(!furnished)}>
                <span className="toggle-dot" />
                Amueblado
              </button>

              {error && <div className="error-banner">{error}</div>}

              <button className="btn-primary btn-cta" type="submit" disabled={busy || !model}>
                {busy ? 'Tasando…' : 'Calcular tasación'}
              </button>
            </>
          )}
        </form>
      </section>

      {/* Results: headline figure + confidence, per the design system */}
      <section className="container">
        <div className="section-head">
          <h2>Resultado de la tasación</h2>
          {model && (
            <span className="feed-chip">
              <i /> MODELO v{model.version.slice(0, 8)}
            </span>
          )}
        </div>

        <div className="result-grid">
          <div className="card result-card">
            {result ? (
              <div data-testid="result">
                <div className="result-label">Alquiler mensual estimado</div>
                <div className="result-price">
                  {formatDOP(result.estimate)}
                  <span className="per"> /mes</span>
                </div>
                {fx && (
                  <div className="result-usd" title={fx.updated ? `Tasa actualizada: ${fx.updated}` : undefined}>
                    ≈ US$ {Math.round(result.estimate / fx.dopPerUsd).toLocaleString('en-US')} /mes
                    <span className="fx-rate">a RD$ {fx.dopPerUsd.toFixed(2)} por US$</span>
                  </div>
                )}
                <p className="result-basis">
                  Calculado para {result.input.area_m2} m² en {result.input.sector}, con{' '}
                  {result.input.bedrooms} hab. y {result.input.bathrooms} baños
                  {result.input.furnished === 1 ? ', amueblado' : ''}.
                </p>

                <div className="result-rows">
                  <div className="result-row">
                    <span className="k">Rango de confianza</span>
                    <span className="v">
                      {formatDOP(result.range_low)} — {formatDOP(result.range_high)}
                    </span>
                  </div>
                  <div className="result-row">
                    <span className="k">Promedio del sector</span>
                    <span className="v">{formatDOP(result.sector_avg)}</span>
                  </div>
                </div>

                <div className="result-foot">
                  <div className="foot-metric">
                    <span className="k">Contra el sector</span>
                    <b className={result.delta_vs_sector_pct >= 0 ? 'up' : 'down'}>
                      {result.delta_vs_sector_pct >= 0 ? '▲ +' : '▼ '}
                      {result.delta_vs_sector_pct.toFixed(1)}%
                    </b>
                  </div>
                  <div className="foot-metric">
                    <span className="k">
                      Tendencia 6m <em className="tag-ejemplo">ejemplo</em>
                    </span>
                    <b className="up">▲ +4.2%</b>
                  </div>
                  <div className="foot-metric">
                    <span className="k">
                      Demanda <em className="tag-ejemplo">ejemplo</em>
                    </span>
                    <b className="neutral">Alta</b>
                  </div>
                </div>

                {saveStatus && <div className="save-status">{saveStatus}</div>}
                {!session && isCloudConfigured && (
                  <div className="save-status">
                    Inicia sesión en Historial para guardar tus tasaciones.
                  </div>
                )}
              </div>
            ) : (
              <div className="empty-state">
                Complete los parámetros del inmueble y presione <b>Calcular tasación</b> para
                obtener la estimación.
              </div>
            )}
          </div>

          <div className="card confidence-card">
            <div className="card-title">Confianza del modelo</div>
            <Donut value={confidence} />
            <p className="confidence-note">
              {confidence !== null
                ? `El modelo explica el ${confidence}% de la variación de precios en el conjunto de prueba. Error medio: ${formatDOP(model!.metrics.mae)}.`
                : 'Cargando métricas del modelo…'}
            </p>
          </div>
        </div>
      </section>

      {result && model?.weights && (
        <AdvisorPanel
          weights={model.weights}
          input={result.input}
          estimate={result.estimate}
        />
      )}

      {/* Comparables: placeholder rows, explicitly badged */}
      <section className="container">
        <div className="section-head">
          <h2>Comparables cercanos</h2>
          <span className="tag-ejemplo big">datos de ejemplo</span>
        </div>
        <div className="card table-card">
          <div className="table-scroll">
            <table className="comp-table">
            <thead>
              <tr>
                <th>Propiedad</th>
                <th>Características</th>
                <th>Alquiler</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {COMPARABLES_EJEMPLO.map((c) => (
                <tr key={c.calle}>
                  <td>
                    <b>{c.calle}</b>
                    <span className="sub">a {c.dist}</span>
                  </td>
                  <td>{c.specs}</td>
                  <td className="num">{formatDOP(c.precio)}</td>
                  <td>
                    <span className={`pill ${c.estado === 'Alquilado' ? 'pill-green' : 'pill-blue'}`}>
                      {c.estado}
                    </span>
                  </td>
                </tr>
              ))}
              </tbody>
            </table>
          </div>
          <p className="table-note">
            Estas filas son de muestra para ilustrar el reporte. Se reemplazan por
            comparables reales cuando el agente de datos complete su primera recolección.
          </p>
        </div>
      </section>

      {model && (
        <section className="container market-split">
          <SectorMap averages={averages} selected={result?.input.sector ?? sector} />
          <div className="card">
            <div className="card-title">Panorama del mercado</div>
            <div className="market-sub">Alquiler promedio por sector (RD$/mes)</div>
            {ranked.map(([name, avg]) => (
              <div
                key={name}
                className={`market-row ${result?.input.sector === name ? 'selected' : ''}`}>
                <span className="name">{name}</span>
                <span className="market-bar">
                  <i style={{ width: `${(avg / maxAvg) * 100}%` }} />
                </span>
                <span className="value">{formatDOP(avg)}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="container">
        <details className="collapsible">
          <summary>¿Cómo se calcula esta estimación?</summary>
          <div className="collapsible-body">
            <p>
              La estimación usa un modelo de <b>regresión lineal</b> entrenado con datos del
              mercado de alquileres de Santo Domingo, calibrado por sector. A partir del sector,
              el área, las habitaciones, los baños, los parqueos, si está amueblado y la
              antigüedad, predice el alquiler mensual y muestra un rango de confianza.
            </p>
            <p>
              {model
                ? `Precisión actual (R²): ${Math.round(model.metrics.r2 * 100)}% · error medio: ${formatDOP(model.metrics.mae)}. `
                : ''}
              Es una estimación orientativa, no una tasación oficial. Las secciones marcadas
              como <em>ejemplo</em> son marcadores de diseño, no datos de mercado.
            </p>
          </div>
        </details>
      </section>

      <Chat
        context={
          result
            ? `Sector ${result.input.sector}, ${result.input.area_m2} m², ${result.input.bedrooms} hab, ${result.input.bathrooms} baños, ${result.input.parking_spots} parqueos, ${result.input.furnished ? 'amueblado' : 'sin amueblar'}, ${result.input.age_years} años. Estimado: RD$ ${Math.round(result.estimate).toLocaleString('en-US')}/mes.`
            : undefined
        }
      />
    </>
  );
}

/* Confidence ring. Pure SVG: no chart library, no extra bytes. */
function Donut({ value }: { value: number | null }) {
  const pct = value ?? 0;
  const r = 52;
  const circumference = 2 * Math.PI * r;
  const dash = (pct / 100) * circumference;
  return (
    <div className="donut">
      <svg viewBox="0 0 130 130" role="img" aria-label={`Confianza ${pct}%`}>
        <circle cx="65" cy="65" r={r} className="donut-track" />
        <circle
          cx="65"
          cy="65"
          r={r}
          className="donut-value"
          strokeDasharray={`${dash} ${circumference - dash}`}
          transform="rotate(-90 65 65)"
        />
      </svg>
      <div className="donut-center">
        <b>{value !== null ? `${value}%` : '—'}</b>
        <span>R²</span>
      </div>
    </div>
  );
}

function Slider({
  id, label, value, onChange, min, max, step, unit, hint,
}: {
  id: string; label: string; value: string; onChange: (v: string) => void;
  min: number; max: number; step: number; unit?: string; hint?: string;
}) {
  const v = Number(value);
  const pct = ((v - min) / (max - min)) * 100;
  return (
    <div className="field">
      <div className="field-head">
        <label htmlFor={id}>{label}</label>
        <span className="field-value">
          {value}
          {unit ? ` ${unit}` : ''}
        </span>
      </div>
      <input
        id={id}
        className="slider"
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          background: `linear-gradient(to right, var(--accent) ${pct}%, var(--card-2) ${pct}%)`,
        }}
      />
      {hint && <span className="field-hint">{hint}</span>}
    </div>
  );
}

/* Segmented control: the design system's pattern for short numeric ranges.
   The last option acts as "N or more" so the domain range stays reachable. */
function Segmented({
  label, value, onChange, options, lastPlus,
}: {
  label: string; value: string; onChange: (v: string) => void;
  options: string[]; lastPlus?: boolean;
}) {
  const last = options[options.length - 1];
  const isOverflow = Number(value) > Number(last);
  return (
    <div className="field">
      <label>{label}</label>
      <div className="segmented" role="group" aria-label={label}>
        {options.map((opt, i) => {
          const isLast = i === options.length - 1;
          const active = value === opt || (isLast && lastPlus && isOverflow);
          return (
            <button
              key={opt}
              type="button"
              className={active ? 'on' : ''}
              aria-pressed={active}
              onClick={() => onChange(opt)}>
              {opt}
              {isLast && lastPlus ? '+' : ''}
            </button>
          );
        })}
      </div>
    </div>
  );
}
