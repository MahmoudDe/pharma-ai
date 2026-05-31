<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Throwable;

class WarehouseController extends Controller
{
    private function aiBaseUrl(): string
    {
        return rtrim((string) config('services.ai.url'), '/');
    }

    public function upload(Request $request): JsonResponse
    {
        $baseUrl = $this->aiBaseUrl();
        if ($baseUrl === '') {
            return response()->json(['message' => 'AI_SERVICE_URL is not configured.'], 503);
        }

        $request->validate([
            'file' => ['required', 'file', 'mimes:csv,txt,xlsx,xls', 'max:5120'],
        ]);

        try {
            $file = $request->file('file');
            $response = Http::connectTimeout(5)
                ->timeout(120)
                ->attach('file', fopen($file->getRealPath(), 'r'), $file->getClientOriginalName())
                ->post("{$baseUrl}/warehouse/upload");

            return response()->json($response->json() ?? [], $response->status());
        } catch (Throwable $e) {
            Log::warning('Warehouse upload proxy failed', ['error' => $e->getMessage()]);

            $message = $e->getMessage();
            if (str_contains($message, '9000') || str_contains($message, 'Connection refused')) {
                $message = 'AI service is not running. Start it: cd ai-service && .venv/bin/uvicorn app.main:app --port 9000 --reload';
            }

            return response()->json(['message' => $message], 502);
        }
    }

    public function resolve(Request $request): JsonResponse
    {
        return $this->proxyPost("{$this->aiBaseUrl()}/warehouse/resolve", $request->all());
    }

    public function materials(Request $request): JsonResponse
    {
        return $this->proxyGet("{$this->aiBaseUrl()}/warehouse/materials", $request->query());
    }

    public function setAlias(Request $request, int $materialId): JsonResponse
    {
        $request->validate([
            'canonical_name' => ['required', 'string', 'min:1', 'max:200'],
        ]);

        return $this->proxyPatch(
            "{$this->aiBaseUrl()}/warehouse/materials/{$materialId}",
            $request->only('canonical_name'),
        );
    }

    public function discover(Request $request): JsonResponse
    {
        return $this->proxyPost("{$this->aiBaseUrl()}/warehouse/discover", $request->all());
    }

    public function discoverResults(string $uploadId): JsonResponse
    {
        $baseUrl = $this->aiBaseUrl();
        if ($baseUrl === '') {
            return response()->json(['message' => 'AI_SERVICE_URL is not configured.'], 503);
        }

        try {
            $response = Http::timeout(60)
                ->acceptJson()
                ->get("{$baseUrl}/warehouse/discover/{$uploadId}");

            return response()->json($response->json() ?? [], $response->status());
        } catch (Throwable $e) {
            return response()->json(['message' => $e->getMessage()], 502);
        }
    }

    private function proxyPost(string $url, array $body): JsonResponse
    {
        if ($this->aiBaseUrl() === '') {
            return response()->json(['message' => 'AI_SERVICE_URL is not configured.'], 503);
        }

        try {
            $response = Http::timeout(120)->acceptJson()->asJson()->post($url, $body);

            return response()->json($response->json() ?? [], $response->status());
        } catch (Throwable $e) {
            return response()->json(['message' => $e->getMessage()], 502);
        }
    }

    private function proxyGet(string $url, array $query): JsonResponse
    {
        if ($this->aiBaseUrl() === '') {
            return response()->json(['message' => 'AI_SERVICE_URL is not configured.'], 503);
        }

        try {
            $response = Http::timeout(60)->acceptJson()->get($url, $query);

            return response()->json($response->json() ?? [], $response->status());
        } catch (Throwable $e) {
            return response()->json(['message' => $e->getMessage()], 502);
        }
    }

    private function proxyPatch(string $url, array $body): JsonResponse
    {
        if ($this->aiBaseUrl() === '') {
            return response()->json(['message' => 'AI_SERVICE_URL is not configured.'], 503);
        }

        try {
            $response = Http::timeout(60)->acceptJson()->asJson()->patch($url, $body);

            return response()->json($response->json() ?? [], $response->status());
        } catch (Throwable $e) {
            return response()->json(['message' => $e->getMessage()], 502);
        }
    }
}
