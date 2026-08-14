import { apiFetch, parseJsonResponse, readApiError, setAuthToken } from "@/lib/api";

export interface AuthUser {
  id: number;
  name: string;
  email: string;
  created_at: string | null;
}

interface AuthPayload {
  token: string;
  user: AuthUser;
}

function asAuthError(status: number, body: unknown, fallback: string): Error {
  return new Error(readApiError(body, fallback || `Request failed with status ${status}`));
}

async function parseAuthPayload(response: Response, fallback: string): Promise<AuthPayload> {
  const body = await parseJsonResponse(response);
  if (!response.ok) {
    throw asAuthError(response.status, body, fallback);
  }
  if (
    !body ||
    typeof body !== "object" ||
    !("token" in body) ||
    !("user" in body)
  ) {
    throw new Error(fallback);
  }
  return body as AuthPayload;
}

export async function registerAccount(
  name: string,
  email: string,
  password: string,
  passwordConfirmation: string,
): Promise<AuthPayload> {
  const response = await apiFetch("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      email,
      password,
      password_confirmation: passwordConfirmation,
    }),
  });
  const payload = await parseAuthPayload(response, "Could not create the account.");
  setAuthToken(payload.token);
  return payload;
}

export async function loginAccount(email: string, password: string): Promise<AuthPayload> {
  const response = await apiFetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const payload = await parseAuthPayload(response, "Could not sign in.");
  setAuthToken(payload.token);
  return payload;
}

export async function logoutAccount(): Promise<void> {
  try {
    await apiFetch("/api/auth/logout", { method: "POST" });
  } finally {
    setAuthToken(null);
  }
}

export async function fetchCurrentUser(): Promise<AuthUser> {
  const response = await apiFetch("/api/auth/me");
  const body = await parseJsonResponse(response);
  if (!response.ok) {
    throw asAuthError(response.status, body, "Session expired.");
  }
  if (!body || typeof body !== "object" || !("user" in body)) {
    throw new Error("Invalid profile response.");
  }
  return (body as { user: AuthUser }).user;
}

export async function updateAccountProfile(name: string, email: string): Promise<AuthUser> {
  const response = await apiFetch("/api/auth/profile", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email }),
  });
  const body = await parseJsonResponse(response);
  if (!response.ok) {
    throw asAuthError(response.status, body, "Could not update profile.");
  }
  if (!body || typeof body !== "object" || !("user" in body)) {
    throw new Error("Invalid profile response.");
  }
  return (body as { user: AuthUser }).user;
}

export async function updateAccountPassword(
  currentPassword: string,
  password: string,
  passwordConfirmation: string,
): Promise<AuthPayload> {
  const response = await apiFetch("/api/auth/password", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      current_password: currentPassword,
      password,
      password_confirmation: passwordConfirmation,
    }),
  });
  const payload = await parseAuthPayload(response, "Could not update password.");
  setAuthToken(payload.token);
  return payload;
}

export async function deleteAccount(password: string): Promise<void> {
  const response = await apiFetch("/api/auth/account", {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!response.ok && response.status !== 204) {
    const body = await parseJsonResponse(response);
    throw asAuthError(response.status, body, "Could not delete account.");
  }
  setAuthToken(null);
}
