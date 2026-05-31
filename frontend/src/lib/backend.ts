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

  if (!response.ok) {
    throw new Error(`Backend readiness check failed with status ${response.status}`);
  }

  return response.json();
}
