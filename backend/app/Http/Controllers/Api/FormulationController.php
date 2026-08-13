<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Throwable;

class FormulationController extends Controller
{
    private function aiBaseUrl(): string
    {
        return rtrim((string) config('services.ai.url'), '/');
    }

    public function index(Request $request): JsonResponse
    {
        return $this->proxyGet("{$this->aiBaseUrl()}/formulations", $request->query());
    }

    public function review(Request $request): JsonResponse
    {
        return $this->proxyGet("{$this->aiBaseUrl()}/formulations/review", $request->query());
    }

    public function patch(Request $request, string $formulationId): JsonResponse
    {
        $baseUrl = $this->aiBaseUrl();
        if ($baseUrl === '') {
            return response()->json(['message' => 'AI_SERVICE_URL is not configured.'], 503);
        }

        try {
            $response = Http::timeout(30)
                ->acceptJson()
                ->asJson()
                ->patch("{$baseUrl}/formulations/{$formulationId}", $request->all());

            return response()->json($response->json() ?? [], $response->status());
        } catch (Throwable $e) {
            return response()->json(['message' => $e->getMessage()], 502);
        }
    }

    public function show(string $formulationId): JsonResponse
    {
        $baseUrl = $this->aiBaseUrl();
        if ($baseUrl === '') {
            return response()->json(['message' => 'AI_SERVICE_URL is not configured.'], 503);
        }

        try {
            $response = Http::timeout(30)
                ->acceptJson()
                ->get("{$baseUrl}/formulations/{$formulationId}");

            return response()->json($response->json() ?? [], $response->status());
        } catch (Throwable $e) {
            return response()->json(['message' => $e->getMessage()], 502);
        }
    }

    public function search(Request $request): JsonResponse
    {
        return $this->proxyPost("{$this->aiBaseUrl()}/formulations/search", $request->all());
    }

    public function substitutions(Request $request, string $formulationId): JsonResponse
    {
        return $this->proxyPost(
            "{$this->aiBaseUrl()}/formulations/{$formulationId}/substitutions",
            $request->all(),
        );
    }

    public function compliance(Request $request, string $formulationId): JsonResponse
    {
        return $this->proxyPost(
            "{$this->aiBaseUrl()}/formulations/{$formulationId}/compliance",
            $request->all(),
        );
    }

    public function kbsReport(string $formulationId): JsonResponse
    {
        return $this->proxyGet("{$this->aiBaseUrl()}/kbs/report/{$formulationId}", []);
    }

    public function kbsValidate(Request $request, string $formulationId): JsonResponse
    {
        return $this->proxyPost(
            "{$this->aiBaseUrl()}/kbs/validate/{$formulationId}",
            $request->all(),
        );
    }

    public function kbsRules(): JsonResponse
    {
        return $this->proxyGet("{$this->aiBaseUrl()}/kbs/rules", []);
    }

    private function proxyPost(string $url, array $body): JsonResponse
    {
        $baseUrl = $this->aiBaseUrl();
        if ($baseUrl === '') {
            return response()->json(['message' => 'AI_SERVICE_URL is not configured.'], 503);
        }

        try {
            $response = Http::timeout(30)
                ->acceptJson()
                ->asJson()
                ->post($url, $body);

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
            $response = Http::timeout(30)->acceptJson()->get($url, $query);

            return response()->json($response->json() ?? [], $response->status());
        } catch (Throwable $e) {
            return response()->json(['message' => $e->getMessage()], 502);
        }
    }
}
