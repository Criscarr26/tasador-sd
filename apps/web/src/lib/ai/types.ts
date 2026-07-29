// Provider-neutral chat types.
//
// Everything above this file (tools, prompt, route handler, UI) is written
// against these types only, so swapping Anthropic for OpenAI or a local
// model is a change of one environment variable -- no other code moves.

export type Role = 'user' | 'assistant';

export interface ChatMessage {
  role: Role;
  content: string;
}

/** A tool the model may call. JSON Schema, translated per provider. */
export interface ToolSpec {
  name: string;
  description: string;
  parameters: {
    type: 'object';
    properties: Record<string, unknown>;
    required?: string[];
  };
}

export interface ToolCall {
  id: string;
  name: string;
  input: Record<string, unknown>;
}

export interface ToolResult {
  id: string;
  name: string;
  /** Serialized result handed back to the model. */
  content: string;
}

/** One turn of the model: either it answers, or it asks for tools. */
export interface ProviderReply {
  text: string;
  toolCalls: ToolCall[];
}

export interface AIProvider {
  readonly id: string;
  readonly model: string;
  /**
   * One round trip. `history` carries prior tool calls/results already
   * folded in by the caller, so providers stay stateless.
   */
  complete(args: {
    system: string;
    messages: ChatMessage[];
    tools: ToolSpec[];
    priorCalls?: { call: ToolCall; result: ToolResult }[];
  }): Promise<ProviderReply>;
}

export class AIConfigError extends Error {}
