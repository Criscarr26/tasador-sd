import { anthropicProvider } from '@/lib/ai/providers/anthropic';
import { openAICompatibleProvider } from '@/lib/ai/providers/openai-compatible';
import { AIConfigError, AIProvider } from '@/lib/ai/types';

/**
 * Provider factory. Switching model vendors is a change of AI_PROVIDER in
 * the environment -- nothing else in the codebase knows which one is live.
 *
 *   AI_PROVIDER=anthropic   ANTHROPIC_API_KEY=...        (default, production)
 *   AI_PROVIDER=openai      OPENAI_API_KEY=...
 *   AI_PROVIDER=ollama      OLLAMA_URL=http://localhost:11434/v1  (free, local)
 *
 * Optional AI_MODEL overrides the per-provider default.
 */
export function getProvider(): AIProvider {
  const which = (process.env.AI_PROVIDER || 'anthropic').toLowerCase();

  switch (which) {
    case 'anthropic':
      return anthropicProvider();

    case 'openai':
      return openAICompatibleProvider({
        id: 'openai',
        baseUrl: process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1',
        apiKey: process.env.OPENAI_API_KEY,
        model: process.env.AI_MODEL || 'gpt-4o-mini',
        requireKey: true,
      });

    case 'ollama':
      return openAICompatibleProvider({
        id: 'ollama',
        baseUrl: process.env.OLLAMA_URL || 'http://localhost:11434/v1',
        model: process.env.AI_MODEL || 'qwen2.5:7b',
        requireKey: false,
        // A 7B model on CPU can take minutes on the first call (model load
        // plus prompt processing). Local development only, so a long wait
        // beats a spurious failure.
        timeoutMs: Number(process.env.AI_TIMEOUT_MS) || 300000,
      });

    default:
      throw new AIConfigError(`Proveedor de IA desconocido: ${which}`);
  }
}

export { AIConfigError };
export type { AIProvider };
