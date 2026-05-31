const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export interface BackendHealth {
  status: string;
  service: string;
}

export interface ReadinessDependency {
  name: string;
  ok: boolean;
  detail: string;
}

export interface BackendReadiness {
  status: string;
  service: string;
  ready: boolean;
  dependencies?: ReadinessDependency[];
}

export async function fetchBackendHealth(): Promise<BackendHealth> {
  const response = await fetch(`${BACKEND_URL}/api/health`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Backend health check failed with status ${response.status}`);
  }

  return response.json();
}

export async function fetchBackendReadiness(): Promise<BackendReadiness> {
  const response = await fetch(`${BACKEND_URL}/api/health/ready`, {
    cache: "no-store",
  });

  const body = (await response.json().catch(() => ({}))) as BackendReadiness & {
    message?: string;
  };

  // Laravel returns 502 when AI service is down; still parse body for UI.
  if (!response.ok && !body.dependencies) {
    throw new Error(body.message ?? `Readiness check failed (${response.status})`);
  }

  return {
    status: body.status ?? "degraded",
    service: body.service ?? "ai-service",
    ready: Boolean(body.ready),
    dependencies: body.dependencies,
  };
}
