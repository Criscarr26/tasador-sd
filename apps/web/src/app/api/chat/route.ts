// Chat endpoint. Runs the tool loop server-side so the browser never sees
// a provider key and `connect-src 'self'` in the CSP stays closed.

import { getProvider, AIConfigError } from '@/lib/ai';
import { runTool, TOOLS, toolResult } from '@/lib/ai/tools';
import type { ChatMessage, ToolCall, ToolResult } from '@/lib/ai/types';
import type { ModelInfo as ApiModelInfo } from '@/lib/api';

export const runtime = 'nodejs';
export const maxDuration = 30;

const MAX_TOOL_ROUNDS = 4; // bounds worst-case latency and cost per message
const MAX_MESSAGES = 20; // trims runaway histories before they reach the model

const SYSTEM = `Eres el asistente de Tasador SD, una plataforma de tasación de alquileres en Santo Domingo, República Dominicana.

REGLA ABSOLUTA: nunca inventes ni calcules precios de memoria. Para cualquier cifra usa las herramientas. Si una herramienta falla, dilo con franqueza en vez de estimar.

Puedes: explicar cómo funciona la plataforma, tasar propiedades, explicar por qué una propiedad vale lo que vale, recomendar mejoras que suban el alquiler, comparar sectores y orientar según presupuesto.

Contexto del producto:
- El modelo es una regresión lineal calibrada por sector; explica el ~93% de la variación de precios.
- Cubre 10 sectores de Santo Domingo. Si preguntan por uno que no está, dilo claramente.
- Los precios son en pesos dominicanos (RD$), alquiler mensual.
- LIMITACIÓN QUE DEBES ADMITIR SI VIENE AL CASO: el modelo está entrenado con datos sintéticos calibrados al mercado, no con listados reales todavía. Es orientativo, no una tasación oficial.
- Todavía no hay inventario de propiedades reales, así que no puedes mostrar propiedades concretas en venta o alquiler.

Estilo: español dominicano neutro, directo y breve (2-4 frases salvo que pidan detalle). Usa cifras concretas. No prometas lo que la plataforma no hace.`;

/**
 * Availability probe. Costs nothing (no model call) and lets the UI hide
 * the assistant entirely where no provider is configured, instead of
 * offering a button that answers "not available".
 */
export async function GET() {
  try {
    const p = getProvider();
    return Response.json({ available: true, provider: p.id });
  } catch {
    return Response.json({ available: false });
  }
}

export async function POST(request: Request) {
  let provider;
  try {
    provider = getProvider();
  } catch (err) {
    if (err instanceof AIConfigError) {
      return Response.json(
        { error: 'El asistente no está configurado en este entorno.', kind: 'unconfigured' },
        { status: 503 }
      );
    }
    throw err;
  }

  let messages: ChatMessage[];
  let context: string | undefined;
  try {
    const body = await request.json();
    messages = Array.isArray(body?.messages) ? body.messages : [];
    context = typeof body?.context === 'string' ? body.context : undefined;
  } catch {
    return Response.json({ error: 'Petición inválida.' }, { status: 400 });
  }

  if (!messages.length) {
    return Response.json({ error: 'No hay mensajes.' }, { status: 400 });
  }

  // Only role/content survive; anything else the client sent is dropped.
  const clean: ChatMessage[] = messages
    .slice(-MAX_MESSAGES)
    .filter((m) => m && (m.role === 'user' || m.role === 'assistant'))
    .map((m) => ({ role: m.role, content: String(m.content ?? '').slice(0, 4000) }));

  const system = context ? `${SYSTEM}\n\nLa tasación que el usuario tiene en pantalla:\n${context.slice(0, 800)}` : SYSTEM;

  const cache: { model?: ApiModelInfo } = {};
  const priorCalls: { call: ToolCall; result: ToolResult }[] = [];

  try {
    for (let round = 0; round <= MAX_TOOL_ROUNDS; round++) {
      const reply = await provider.complete({
        system,
        messages: clean,
        tools: TOOLS,
        priorCalls,
      });

      if (!reply.toolCalls.length) {
        return Response.json({
          reply: reply.text || 'No pude generar una respuesta. Intenta de nuevo.',
          provider: provider.id,
          toolsUsed: priorCalls.map((p) => p.call.name),
        });
      }

      // Last round reached and it still wants tools: stop and answer with
      // what we have rather than looping.
      if (round === MAX_TOOL_ROUNDS) {
        return Response.json({
          reply:
            reply.text ||
            'Necesité demasiados pasos para responder eso. ¿Puedes preguntarlo de forma más concreta?',
          provider: provider.id,
          toolsUsed: priorCalls.map((p) => p.call.name),
        });
      }

      for (const call of reply.toolCalls) {
        let content: string;
        try {
          content = await runTool(call.name, call.input, cache);
        } catch (err) {
          content = JSON.stringify({
            error: err instanceof Error ? err.message : 'fallo la herramienta',
          });
        }
        priorCalls.push({ call, result: toolResult(call.id, call.name, content) });
      }
    }

    return Response.json({ reply: 'No pude completar la respuesta.', provider: provider.id });
  } catch (err) {
    console.error('[chat]', err);
    return Response.json(
      { error: 'El asistente no está disponible en este momento.' },
      { status: 502 }
    );
  }
}
