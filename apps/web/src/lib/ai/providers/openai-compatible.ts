import { AIConfigError, AIProvider, ProviderReply, ToolCall } from '@/lib/ai/types';

/**
 * One implementation covers every OpenAI-compatible /chat/completions
 * endpoint: OpenAI itself, Ollama's compatibility layer, and most
 * self-hosted gateways. Only the base URL, key and model change.
 */
export function openAICompatibleProvider(opts: {
  id: string;
  baseUrl: string;
  apiKey?: string;
  model: string;
  /** Local runtimes need no credentials. */
  requireKey: boolean;
  /** A 7B model on CPU needs far longer than a hosted one. */
  timeoutMs?: number;
}): AIProvider {
  if (opts.requireKey && !opts.apiKey) {
    throw new AIConfigError(`Falta la API key para el proveedor ${opts.id}`);
  }

  return {
    id: opts.id,
    model: opts.model,
    async complete({ system, messages, tools, priorCalls = [] }) {
      const body = {
        model: opts.model,
        messages: [
          { role: 'system', content: system },
          ...messages.map((m) => ({ role: m.role, content: m.content })),
          ...(priorCalls.length
            ? [
                {
                  role: 'assistant',
                  content: null,
                  tool_calls: priorCalls.map(({ call }) => ({
                    id: call.id,
                    type: 'function',
                    function: { name: call.name, arguments: JSON.stringify(call.input) },
                  })),
                },
                ...priorCalls.map(({ result }) => ({
                  role: 'tool',
                  tool_call_id: result.id,
                  content: result.content,
                })),
              ]
            : []),
        ],
        tools: tools.map((t) => ({
          type: 'function',
          function: {
            name: t.name,
            description: t.description,
            parameters: t.parameters,
          },
        })),
        max_tokens: 1024,
      };

      const res = await fetch(`${opts.baseUrl}/chat/completions`, {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          ...(opts.apiKey ? { authorization: `Bearer ${opts.apiKey}` } : {}),
        },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(opts.timeoutMs ?? 60000),
      });

      if (!res.ok) {
        throw new Error(`${opts.id} ${res.status}: ${(await res.text()).slice(0, 200)}`);
      }

      const data = await res.json();
      const choice = data.choices?.[0]?.message ?? {};
      const toolCalls: ToolCall[] = (choice.tool_calls ?? []).map(
        (c: { id: string; function: { name: string; arguments: string } }) => ({
          id: c.id,
          name: c.function.name,
          input: safeParse(c.function.arguments),
        })
      );
      return { text: choice.content ?? '', toolCalls } satisfies ProviderReply;
    },
  };
}

function safeParse(raw: string): Record<string, unknown> {
  try {
    return JSON.parse(raw || '{}');
  } catch {
    return {};
  }
}
