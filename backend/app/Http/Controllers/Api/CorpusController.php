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
        $baseUrl = rtrim((string) config('services.ai.url'), '/');
        if ($baseUrl === '') {
            return response()->json(['message' => 'AI_SERVICE_URL is not configured.'], 503);
        }

        try {
            $response = Http::timeout(30)->acceptJson()->get("{$baseUrl}/corpus/stats");

            return response()->json($response->json() ?? [], $response->status());
        } catch (Throwable $e) {
            return response()->json(['message' => $e->getMessage()], 502);
        }
    }
}
