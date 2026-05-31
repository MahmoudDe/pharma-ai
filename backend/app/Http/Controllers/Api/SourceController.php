<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Symfony\Component\HttpFoundation\StreamedResponse;
use Throwable;

class SourceController extends Controller
{
    public function show(string $docId, Request $request): StreamedResponse|\Illuminate\Http\JsonResponse
    {
        $baseUrl = rtrim((string) config('services.ai.url'), '/');
        if ($baseUrl === '') {
            return response()->json(['message' => 'AI_SERVICE_URL is not configured.'], 503);
        }

        try {
            $response = Http::timeout(60)
                ->withOptions(['stream' => true])
                ->get("{$baseUrl}/sources/{$docId}");

            if (! $response->successful()) {
                return response()->json($response->json() ?? ['message' => 'Source not found.'], $response->status());
            }

            $filename = $response->header('Content-Disposition') ?? 'inline';
            $contentType = $response->header('Content-Type') ?? 'application/pdf';

            return response()->stream(function () use ($response): void {
                $body = $response->toPsrResponse()->getBody();
                while (! $body->eof()) {
                    echo $body->read(8192);
                }
            }, 200, [
                'Content-Type' => $contentType,
                'Content-Disposition' => $filename,
            ]);
        } catch (Throwable $e) {
            Log::warning('Source PDF proxy failed', ['doc_id' => $docId, 'error' => $e->getMessage()]);

            return response()->json(['message' => $e->getMessage()], 502);
        }
    }
}
