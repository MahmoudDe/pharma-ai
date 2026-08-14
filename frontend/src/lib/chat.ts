import type {
  ChatThreadDetail,
  ChatThreadSummary,
  ChatTurnRequest,
  ChatTurnResponse,
} from "@/types/chat";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const CHAT_TIMEOUT_MS = 45000;

function buildApiError(status: number, body: unknown): Error {
  if (body && typeof body === "object" && "message" in body) {
    return new Error(String((body as { message: unknown }).message));
  }

  return new Error(`Request failed with status ${status}`);
}

async function parseJsonResponse(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export async function fetchChatThreads(): Promise<ChatThreadSummary[]> {
  const response = await fetch(`${BACKEND_URL}/api/chat/threads`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  const body = await parseJsonResponse(response);

  if (!response.ok) {
    throw buildApiError(response.status, body);
  }

  if (!body || typeof body !== "object" || !("threads" in body)) {
    throw new Error("Invalid threads response format from backend");
  }

  return (body as { threads: ChatThreadSummary[] }).threads;
}

export async function createChatThread(): Promise<string> {
  const response = await fetch(`${BACKEND_URL}/api/chat/threads`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });

  const body = await parseJsonResponse(response);

  if (!response.ok) {
    throw buildApiError(response.status, body);
  }

  if (!body || typeof body !== "object" || !("id" in body)) {
    throw new Error("Invalid create thread response format from backend");
  }

  return String((body as { id: string }).id);
}

export async function fetchChatThread(threadId: string): Promise<ChatThreadDetail> {
  const response = await fetch(`${BACKEND_URL}/api/chat/threads/${threadId}`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  const body = await parseJsonResponse(response);

  if (!response.ok) {
    throw buildApiError(response.status, body);
  }

  if (!body || typeof body !== "object" || !("messages" in body)) {
    throw new Error("Invalid thread response format from backend");
  }

  return body as ChatThreadDetail;
}

export async function updateChatThreadTitle(threadId: string, title: string): Promise<void> {
  const response = await fetch(`${BACKEND_URL}/api/chat/threads/${threadId}`, {
    method: "PATCH",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ title }),
  });

  if (!response.ok) {
    const body = await parseJsonResponse(response);
    throw buildApiError(response.status, body);
  }
}

export async function deleteChatThread(threadId: string): Promise<void> {
  const response = await fetch(`${BACKEND_URL}/api/chat/threads/${threadId}`, {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });

  if (!response.ok && response.status !== 204) {
    const body = await parseJsonResponse(response);
    throw buildApiError(response.status, body);
  }
}

export async function submitMessageFeedback(
  messageId: string,
  rating: 1 | -1,
  userMessage?: string,
): Promise<void> {
  const response = await fetch(`${BACKEND_URL}/api/chat/messages/${messageId}/feedback`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ rating, user_message: userMessage ?? null }),
  });
  const body = await parseJsonResponse(response);
  if (!response.ok) {
    throw buildApiError(response.status, body);
  }
}

function parseSseBlock(block: string): { event: string; data: string } | null {
  let event = "message";
  let data = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("event: ")) {
      event = line.slice(7).trim();
    } else if (line.startsWith("data: ")) {
      data += line.slice(6);
    }
  }
  if (!data && event === "message") {
    return null;
  }
  return { event, data };
}

export async function sendChatTurnStream(
  payload: ChatTurnRequest,
  handlers: {
    onToken: (delta: string) => void;
    onError?: (message: string) => void;
  },
  signal?: AbortSignal,
): Promise<ChatTurnResponse> {
  const response = await fetch(`${BACKEND_URL}/api/chat/messages/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    const body = await parseJsonResponse(response);
    throw buildApiError(response.status, body);
  }

  if (!response.body) {
    throw new Error("Streaming not supported in this browser.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResponse: ChatTurnResponse | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const frame = parseSseBlock(block);
      if (frame) {
        if (frame.event === "token") {
          try {
            const parsed = JSON.parse(frame.data) as { delta?: string };
            if (parsed.delta) {
              handlers.onToken(parsed.delta);
            }
          } catch {
            /* ignore malformed token frames */
          }
        } else if (frame.event === "error") {
          try {
            const parsed = JSON.parse(frame.data) as { message?: string };
            handlers.onError?.(parsed.message ?? "Stream failed");
          } catch {
            handlers.onError?.("Stream failed");
          }
        } else if (frame.event === "done") {
          finalResponse = JSON.parse(frame.data) as ChatTurnResponse;
        }
      }
      boundary = buffer.indexOf("\n\n");
    }
  }

  if (!finalResponse || !("assistant_message" in finalResponse)) {
    throw new Error("Stream ended without a complete response.");
  }

  return finalResponse;
}

export async function sendChatTurn(
  payload: ChatTurnRequest,
  options?: { stream?: boolean; onToken?: (delta: string) => void; signal?: AbortSignal },
): Promise<ChatTurnResponse> {
  if (options?.stream && options.onToken) {
    return sendChatTurnStream(
      payload,
      { onToken: options.onToken },
      options.signal,
    );
  }
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), CHAT_TIMEOUT_MS);

  try {
    const response = await fetch(`${BACKEND_URL}/api/chat/messages`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    const body = await parseJsonResponse(response);

    if (!response.ok) {
      throw buildApiError(response.status, body);
    }

    if (!body || typeof body !== "object" || !("assistant_message" in body)) {
      throw new Error("Invalid chat response format from backend");
    }

    return body as ChatTurnResponse;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("Chat request timed out. Please retry.");
    }

    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}
