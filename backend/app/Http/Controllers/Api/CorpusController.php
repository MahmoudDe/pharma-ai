<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\Http;
use Throwable;

class CorpusController extends Controller
{
    public function stats(): JsonResponse
    {
        return $this->proxyGet("{$this->aiBaseUrl()}/corpus/stats");
    }

    public function manifest(): JsonResponse
    {
        return $this->proxyGet("{$this->aiBaseUrl()}/corpus/manifest");
    }

    public function startIngest(\Illuminate\Http\Request $request): JsonResponse
    {
        return $this->proxyPost("{$this->aiBaseUrl()}/corpus/ingest", $request->all());
    }

    public function listIngestJobs(): JsonResponse
    {
        return $this->proxyGet("{$this->aiBaseUrl()}/corpus/ingest");
    }

    public function getIngestJob(string $jobId): JsonResponse
    {
        $baseUrl = $this->aiBaseUrl();
        if ($baseUrl === '') {
            return response()->json(['message' => 'AI_SERVICE_URL is not configured.'], 503);
        }

        try {
            $response = \Illuminate\Support\Facades\Http::timeout(30)
                ->acceptJson()
                ->get("{$baseUrl}/corpus/ingest/{$jobId}");

            return response()->json($response->json() ?? [], $response->status());
        } catch (\Throwable $e) {
            return response()->json(['message' => $e->getMessage()], 502);
        }
    }

    private function aiBaseUrl(): string
    {
        return rtrim((string) config('services.ai.url'), '/');
    }

    private function proxyGet(string $url, array $query = []): JsonResponse
    {
        $baseUrl = $this->aiBaseUrl();
        if ($baseUrl === '') {
            return response()->json(['message' => 'AI_SERVICE_URL is not configured.'], 503);
        }

        try {
            $response = \Illuminate\Support\Facades\Http::timeout(30)
                ->acceptJson()
                ->get($url, $query);

            return response()->json($response->json() ?? [], $response->status());
        } catch (\Throwable $e) {
            return response()->json(['message' => $e->getMessage()], 502);
        }
    }

    private function proxyPost(string $url, array $body): JsonResponse
    {
        $baseUrl = $this->aiBaseUrl();
        if ($baseUrl === '') {
            return response()->json(['message' => 'AI_SERVICE_URL is not configured.'], 503);
        }

        try {
            $response = \Illuminate\Support\Facades\Http::timeout(60)
                ->acceptJson()
                ->asJson()
                ->post($url, $body);

            return response()->json($response->json() ?? [], $response->status());
        } catch (\Throwable $e) {
            return response()->json(['message' => $e->getMessage()], 502);
        }
    }
}
