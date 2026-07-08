'use client';

import { FormEvent, useCallback, useEffect, useState } from 'react';

import { formatDOP } from '@/lib/api';
import { isCloudConfigured, SavedEstimate, supabase } from '@/lib/supabase';
import { useSession } from '@/lib/use-session';

export default function HistorialPage() {
  const { session, loading } = useSession();

  if (!isCloudConfigured) {
    return (
      <div className="container">
        <h1 className="page-title">Historial</h1>
        <p className="page-sub">
          La nube no está configurada en este despliegue, así que el historial está
          deshabilitado. El tasador funciona igual.
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="container auth-card">
        <div className="skeleton" style={{ height: 220 }} />
      </div>
    );
  }

  if (!session) return <AuthCard />;
  return <HistoryList />;
}

function AuthCard() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function signIn(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    const { error } = await supabase!.auth.signInWithPassword({ email: email.trim(), password });
    setBusy(false);
    if (error) {
      setMessage(
        error.message === 'Invalid login credentials'
          ? 'Correo o contraseña incorrectos. Si no tienes cuenta, usa "Crear cuenta".'
          : `No se pudo iniciar sesión: ${error.message}`
      );
    }
  }

  async function signUp() {
    setBusy(true);
    setMessage(null);
    const { data, error } = await supabase!.auth.signUp({ email: email.trim(), password });
    setBusy(false);
    if (error) {
      setMessage(`No se pudo crear la cuenta: ${error.message}`);
    } else if (!data.session) {
      setMessage('Cuenta creada. Revisa tu correo y confírmala para poder entrar.');
    }
  }

  return (
    <div className="container auth-card">
      <form className="card" onSubmit={signIn}>
        <div className="card-title">Tu historial de tasaciones</div>
        <p className="page-sub" style={{ marginBottom: '1.2rem' }}>
          La misma cuenta de la app móvil: tus tasaciones te siguen entre dispositivos.
        </p>
        <div className="field">
          <label htmlFor="email">Correo</label>
          <input id="email" type="email" autoComplete="email" value={email}
            onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="password">Contraseña</label>
          <input id="password" type="password" minLength={6} value={password}
            onChange={(e) => setPassword(e.target.value)} required />
        </div>
        {message && <div className="error-banner">{message}</div>}
        <button className="btn-primary" type="submit" disabled={busy}>
          {busy ? 'Un momento…' : 'Iniciar sesión'}
        </button>
        <button className="btn-secondary" type="button" onClick={signUp} disabled={busy}>
          Crear cuenta
        </button>
      </form>
    </div>
  );
}

function HistoryList() {
  const [items, setItems] = useState<SavedEstimate[]>([]);
  const [busy, setBusy] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const fetchItems = useCallback(async () => {
    const { data, error } = await supabase!
      .from('saved_estimates')
      .select('*')
      .order('created_at', { ascending: false });
    if (error) setMessage(`Error al cargar: ${error.message}`);
    else setItems((data ?? []) as SavedEstimate[]);
    setBusy(false);
  }, []);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  function toggleSelect(id: string) {
    setSelected((current) => {
      if (current.includes(id)) return current.filter((s) => s !== id);
      if (current.length >= 2) return [current[1], id];
      return [...current, id];
    });
  }

  async function deleteItem(id: string) {
    const { error } = await supabase!.from('saved_estimates').delete().eq('id', id);
    if (error) setMessage(`Error al eliminar: ${error.message}`);
    else {
      setItems((current) => current.filter((item) => item.id !== id));
      setSelected((current) => current.filter((s) => s !== id));
    }
    setConfirmDelete(null);
  }

  const [a, b] = selected.map((id) => items.find((item) => item.id === id));
  const comparison =
    a && b
      ? {
          cheaper: a.predicted_price <= b.predicted_price ? a : b,
          pricier: a.predicted_price <= b.predicted_price ? b : a,
        }
      : null;

  return (
    <div className="container">
      <h1 className="page-title">Historial</h1>
      <p className="page-sub">
        Cada tasación se guarda automáticamente. Selecciona dos tarjetas para compararlas.
      </p>

      {comparison && (
        <div className="card compare-card">
          <div className="card-title">Comparación</div>
          <div className="result-row">
            <span className="k">{comparison.pricier.label}</span>
            <span className="v">{formatDOP(comparison.pricier.predicted_price)}</span>
          </div>
          <div className="result-row">
            <span className="k">{comparison.cheaper.label}</span>
            <span className="v">{formatDOP(comparison.cheaper.predicted_price)}</span>
          </div>
          <div className="compare-diff">
            Diferencia: {formatDOP(comparison.pricier.predicted_price - comparison.cheaper.predicted_price)}
            {comparison.cheaper.predicted_price > 0 &&
              ` (${(((comparison.pricier.predicted_price - comparison.cheaper.predicted_price) /
                comparison.cheaper.predicted_price) * 100).toFixed(0)}% más caro)`}
          </div>
        </div>
      )}

      {message && <div className="error-banner">{message}</div>}

      {busy ? (
        <div className="history-grid">
          {[0, 1, 2].map((i) => (
            <div key={i} className="skeleton" style={{ height: 150 }} />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="empty-state">
          Aún no hay tasaciones en tu historial.
          <br />
          Haz una en la pestaña Tasador: se guardará sola.
        </div>
      ) : (
        <div className="history-grid">
          {items.map((item) => (
            <div
              key={item.id}
              className={`history-card ${selected.includes(item.id) ? 'selected' : ''}`}
              onClick={() => toggleSelect(item.id)}>
              <div className="top">
                <span className="label">{item.label}</span>
                <button
                  className="delete"
                  onClick={(event) => {
                    event.stopPropagation();
                    if (confirmDelete === item.id) deleteItem(item.id);
                    else setConfirmDelete(item.id);
                  }}>
                  {confirmDelete === item.id ? '¿Eliminar?' : 'Eliminar'}
                </button>
              </div>
              <div className="detail">
                {item.sector} · {item.area_m2} m² · {item.bedrooms} hab · {item.bathrooms} baños
                <br />
                {item.parking_spots} parqueos · {item.furnished ? 'amueblado' : 'sin amueblar'} ·{' '}
                {item.age_years} años
              </div>
              <div className="bottom">
                <span className="price">{formatDOP(item.predicted_price)}</span>
                <span className="date">{item.created_at.slice(0, 10)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
