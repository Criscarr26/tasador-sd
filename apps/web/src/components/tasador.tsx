'use client';

import { FormEvent, useEffect, useState } from 'react';

import { Appraisal, AppraisalInput, appraise, formatDOP, getModelInfo, ModelInfo } from '@/lib/api';
import { isCloudConfigured, supabase } from '@/lib/supabase';
import { useSession } from '@/lib/use-session';

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

  useEffect(() => {
    getModelInfo()
      .then((info) => {
        setModel(info);
        if (!info.sectors.includes('Bella Vista')) setSector(info.sectors[0]);
      })
      .catch(() => setApiDown(true));
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

  return (
    <>
      <section className="hero container">
        <div className="hero-badge">TASACIÓN INTELIGENTE</div>
        <h1>
          El precio justo de tu alquiler,
          <br />
          <span className="accent">en segundos</span>
        </h1>
        <p>
          Machine learning calibrado por sector para el mercado de alquileres de Santo
          Domingo. Estima, guarda y compara desde el navegador o desde tu teléfono.
        </p>
        <div className="hero-stats">
          <div className="stat">
            <b>{model ? `${Math.round(model.metrics.r2 * 100)}%` : '—'}</b>
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
      </section>

      <section className="container appraise-grid" id="tasar">
        <form className="card" onSubmit={onSubmit} aria-busy={busy}>
          <div className="card-title">Parámetros del inmueble</div>

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
              <div className="field-row">
                <div className="field">
                  <label htmlFor="area">Área (m²)</label>
                  <input id="area" type="number" min={20} max={1000} value={area}
                    onChange={(e) => setArea(e.target.value)} required />
                </div>
                <div className="field">
                  <label htmlFor="age">Antigüedad (años)</label>
                  <input id="age" type="number" min={0} max={80} value={age}
                    onChange={(e) => setAge(e.target.value)} required />
                </div>
              </div>
              <div className="field-row">
                <div className="field">
                  <label htmlFor="bedrooms">Habitaciones</label>
                  <input id="bedrooms" type="number" min={0} max={10} value={bedrooms}
                    onChange={(e) => setBedrooms(e.target.value)} required />
                </div>
                <div className="field">
                  <label htmlFor="bathrooms">Baños</label>
                  <input id="bathrooms" type="number" min={1} max={10} value={bathrooms}
                    onChange={(e) => setBathrooms(e.target.value)} required />
                </div>
              </div>
              <div className="field-row">
                <div className="field">
                  <label htmlFor="parking">Parqueos</label>
                  <input id="parking" type="number" min={0} max={10} value={parking}
                    onChange={(e) => setParking(e.target.value)} required />
                </div>
                <div className="field field-check" style={{ alignSelf: 'end' }}>
                  <input id="furnished" type="checkbox" checked={furnished}
                    onChange={(e) => setFurnished(e.target.checked)} />
                  <label htmlFor="furnished">Amueblado</label>
                </div>
              </div>

              {error && <div className="error-banner">{error}</div>}

              <button className="btn-primary" type="submit" disabled={busy || !model}>
                {busy ? 'Tasando…' : 'Tasar propiedad'}
              </button>
            </>
          )}
        </form>

        <div className="card">
          <div className="card-title">Resultado</div>
          {result ? (
            <div data-testid="result">
              <div className="result-label">Precio estimado</div>
              <div className="result-price">
                {formatDOP(result.estimate)}
                <span className="per"> /mes</span>
              </div>
              <div
                className={`result-chip ${result.delta_vs_sector_pct >= 0 ? 'chip-positive' : 'chip-negative'}`}>
                {result.delta_vs_sector_pct >= 0 ? '+' : ''}
                {result.delta_vs_sector_pct.toFixed(1)}% vs promedio de {result.input.sector}
              </div>
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
                <div className="result-row">
                  <span className="k">Modelo</span>
                  <span className="v">v{result.model_version.slice(0, 8)}</span>
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
              Complete los parámetros del inmueble y presione <b>Tasar propiedad</b> para
              obtener la estimación.
            </div>
          )}
        </div>
      </section>

      {model && (
        <section className="container market-card">
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
    </>
  );
}
