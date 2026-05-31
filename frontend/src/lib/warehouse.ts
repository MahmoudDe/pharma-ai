import type {
  DiscoverResponse,
  ResolveResponse,
  UploadResponse,
} from "@/types/warehouse";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

function buildApiError(status: number, body: unknown): Error {
  if (body && typeof body === "object" && "detail" in body) {
    return new Error(String((body as { detail: unknown }).detail));
  }
  if (body && typeof body === "object" && "message" in body) {
    return new Error(String((body as { message: unknown }).message));
  }
  return new Error(`Request failed with status ${status}`);
}

async function parseJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export async function uploadWarehouseFile(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${BACKEND_URL}/api/warehouse/upload`, {
    method: "POST",
    body: form,
  });
  const body = await parseJson(response);
  if (!response.ok) {
    throw buildApiError(response.status, body);
  }
  return body as UploadResponse;
}

export async function resolveWarehouse(uploadId?: string): Promise<ResolveResponse> {
  const response = await fetch(`${BACKEND_URL}/api/warehouse/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(uploadId ? { upload_id: uploadId } : {}),
  });
  const body = await parseJson(response);
  if (!response.ok) {
    throw buildApiError(response.status, body);
  }
  return body as ResolveResponse;
}

export async function setMaterialAlias(
  materialId: number,
  canonicalName: string,
): Promise<import("@/types/warehouse").WarehouseMaterialRow> {
  const response = await fetch(`${BACKEND_URL}/api/warehouse/materials/${materialId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ canonical_name: canonicalName }),
  });
  const body = await parseJson(response);
  if (!response.ok) {
    throw buildApiError(response.status, body);
  }
  return body as import("@/types/warehouse").WarehouseMaterialRow;
}

export async function discoverProducts(
  uploadId: string,
  minCoverage = 50,
  productType?: string,
): Promise<DiscoverResponse> {
  const response = await fetch(`${BACKEND_URL}/api/warehouse/discover`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({
      upload_id: uploadId,
      min_coverage: minCoverage,
      product_type: productType || undefined,
    }),
  });
  const body = await parseJson(response);
  if (!response.ok) {
    throw buildApiError(response.status, body);
  }
  return body as DiscoverResponse;
}
