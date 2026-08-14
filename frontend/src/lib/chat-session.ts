const ACTIVE_THREAD_KEY = "pharma-ai-active-thread";

function storageKey(userId?: number | null): string {
  return userId != null ? `${ACTIVE_THREAD_KEY}:${userId}` : ACTIVE_THREAD_KEY;
}

export function getStoredActiveThreadId(userId?: number | null): string | null {
  if (typeof window === "undefined") return null;
  try {
    const id = localStorage.getItem(storageKey(userId));
    return id && id.length > 0 ? id : null;
  } catch {
    return null;
  }
}

export function setStoredActiveThreadId(threadId: string | null, userId?: number | null): void {
  if (typeof window === "undefined") return;
  try {
    const key = storageKey(userId);
    if (threadId) {
      localStorage.setItem(key, threadId);
    } else {
      localStorage.removeItem(key);
    }
  } catch {
    /* ignore */
  }
}
