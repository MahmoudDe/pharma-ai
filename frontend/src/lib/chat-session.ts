const ACTIVE_THREAD_KEY = "pharma-ai-active-thread";

export function getStoredActiveThreadId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const id = localStorage.getItem(ACTIVE_THREAD_KEY);
    return id && id.length > 0 ? id : null;
  } catch {
    return null;
  }
}

export function setStoredActiveThreadId(threadId: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (threadId) {
      localStorage.setItem(ACTIVE_THREAD_KEY, threadId);
    } else {
      localStorage.removeItem(ACTIVE_THREAD_KEY);
    }
  } catch {
    /* ignore */
  }
}
