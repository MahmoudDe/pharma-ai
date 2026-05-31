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

export async function sendChatTurn(
  payload: ChatTurnRequest,
): Promise<ChatTurnResponse> {
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
