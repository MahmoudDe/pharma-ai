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
            $response = Http::timeout(120)
                ->attach('file', fopen($file->getRealPath(), 'r'), $file->getClientOriginalName())
                ->post("{$baseUrl}/warehouse/upload");

            return response()->json($response->json() ?? [], $response->status());
        } catch (Throwable $e) {
            Log::warning('Warehouse upload proxy failed', ['error' => $e->getMessage()]);

            return response()->json(['message' => $e->getMessage()], 502);
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
}
