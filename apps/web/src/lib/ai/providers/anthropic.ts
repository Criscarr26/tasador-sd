import { AIConfigError, AIProvider, ProviderReply, ToolCall } from '@/lib/ai/types';

/** Anthropic Messages API. Default provider. */
export function anthropicProvider(): AIProvider {
  const key = process.env.ANTHROPIC_API_KEY;
  if (!key) throw new AIConfigError('Falta ANTHROPIC_API_KEY');
  const model = process.env.AI_MODEL || 'claude-haiku-4-5-20251001';

  return {
    id: 'anthropic',
    model,
    async complete({ system, messages, tools, priorCalls = [] }) {
      // Anthropic represents a tool round as an assistant message holding
      // tool_use blocks, followed by a user message with tool_result blocks.
      const body: Record<string, unknown> = {
        model,
        max_tokens: 1024,
        system,
        tools: tools.map((t) => ({
          name: t.name,
          description: t.description,
          input_schema: t.parameters,
        })),
        messages: [
          ...messages.map((m) => ({ role: m.role, content: m.content })),
          ...(priorCalls.length
            ? [
                {
                  role: 'assistant',
                  content: priorCalls.map(({ call }) => ({
                    type: 'tool_use',
                    id: call.id,
                    name: call.name,
                    input: call.input,
                  })),
                },
                {
                  role: 'user',
                  content: priorCalls.map(({ result }) => ({
                    type: 'tool_result',
                    tool_use_id: result.id,
                    content: result.content,
                  })),
                },
              ]
            : []),
        ],
      };

      const res = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          'x-api-key': key,
          'anthropic-version': '2023-06-01',
        },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(30000),
      });

      if (!res.ok) {
        throw new Error(`Anthropic ${res.status}: ${(await res.text()).slice(0, 200)}`);
      }

      const data = await res.json();
      let text = '';
      const toolCalls: ToolCall[] = [];
      for (const block of data.content ?? []) {
        if (block.type === 'text') text += block.text;
        if (block.type === 'tool_use') {
          toolCalls.push({ id: block.id, name: block.name, input: block.input ?? {} });
        }
      }
      return { text, toolCalls } satisfies ProviderReply;
    },
  };
}
