'use client';

import { FormEvent, useEffect, useRef, useState } from 'react';

interface Msg {
  role: 'user' | 'assistant';
  content: string;
}

const SUGERENCIAS = [
  '¿Por qué mi propiedad vale eso?',
  '¿Qué mejora sube más el alquiler?',
  '¿Qué sector me conviene con RD$ 50,000?',
  '¿Cómo funciona la plataforma?',
];

/**
 * Assistant panel. Carries the on-screen appraisal as context so questions
 * like "why is it worth that?" resolve without the user retyping anything.
 */
export function Chat({ context }: { context?: string }) {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [available, setAvailable] = useState<boolean | null>(null);
  const feed = useRef<HTMLDivElement>(null);

  // Don't advertise the assistant where no provider is configured.
  useEffect(() => {
    fetch('/api/chat')
      .then((r) => r.json())
      .then((d) => setAvailable(!!d?.available))
      .catch(() => setAvailable(false));
  }, []);

  useEffect(() => {
    feed.current?.scrollTo({ top: feed.current.scrollHeight, behavior: 'smooth' });
  }, [msgs, busy]);

  async function send(text: string) {
    const question = text.trim();
    if (!question || busy) return;

    const next = [...msgs, { role: 'user' as const, content: question }];
    setMsgs(next);
    setDraft('');
    setBusy(true);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ messages: next, context }),
      });
      const data = await res.json();

      if (res.status === 503 && data?.kind === 'unconfigured') {
        setUnavailable(true);
        setMsgs([...next, {
          role: 'assistant',
          content: 'El asistente todavía no está activado en este entorno.',
        }]);
        return;
      }

      setMsgs([...next, {
        role: 'assistant',
        content: data?.reply ?? data?.error ?? 'No pude responder. Intenta de nuevo.',
      }]);
    } catch {
      setMsgs([...next, {
        role: 'assistant',
        content: 'No pude conectar con el asistente. Revisa tu conexión e intenta de nuevo.',
      }]);
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    send(draft);
  }

  // Render nothing until the probe answers: showing the button first and
  // pulling it away a moment later reads as a glitch.
  if (!available) return null;

  return (
    <>
      <button
        className={`chat-fab ${open ? 'is-open' : ''}`}
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-controls="chat-panel"
        aria-label={open ? 'Cerrar asistente' : 'Abrir asistente'}>
        {open ? '×' : 'Asistente'}
      </button>

      {open && (
        <div className="chat-panel" id="chat-panel" role="dialog" aria-label="Asistente de Tasador SD">
          <header className="chat-head">
            <div>
              <b>Asistente</b>
              <span>Pregunta sobre tu tasación o el mercado</span>
            </div>
          </header>

          <div className="chat-feed" ref={feed}>
            {!msgs.length && (
              <div className="chat-empty">
                <p>
                  Puedo explicarte de dónde sale una tasación, qué mejoras suben más el
                  alquiler y qué sector conviene a tu presupuesto.
                </p>
                <div className="chat-suggestions">
                  {SUGERENCIAS.map((s) => (
                    <button key={s} type="button" onClick={() => send(s)} disabled={busy}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {msgs.map((m, i) => (
              <div key={i} className={`bubble ${m.role}`}>
                {m.content}
              </div>
            ))}

            {busy && (
              <div className="bubble assistant thinking" aria-live="polite">
                <i /><i /><i />
              </div>
            )}
          </div>

          <form className="chat-input" onSubmit={onSubmit}>
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={unavailable ? 'Asistente no disponible' : 'Escribe tu pregunta…'}
              disabled={busy || unavailable}
              aria-label="Mensaje"
            />
            <button type="submit" disabled={busy || unavailable || !draft.trim()}>
              Enviar
            </button>
          </form>
        </div>
      )}
    </>
  );
}
