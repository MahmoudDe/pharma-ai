<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\ChatMessage;
use App\Models\ChatThread;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Str;
use Throwable;

class ChatController extends Controller
{
    /**
     * Proxy a chat turn to the Python AI service and persist messages.
     */
    public function messages(Request $request): JsonResponse
    {
        $validated = $request->validate([
            'thread_id' => ['required', 'string', 'uuid'],
            'message' => ['required', 'string'],
            'structured_brief' => ['sometimes', 'array'],
        ]);

        $baseUrl = rtrim((string) config('services.ai.url'), '/');
        $timeout = (int) config('services.ai.timeout', 45);

        if ($baseUrl === '') {
            return response()->json(
                ['message' => 'AI_SERVICE_URL is not configured.'],
                503,
            );
        }

        try {
            return DB::transaction(function () use ($validated, $baseUrl, $timeout) {
                $thread = ChatThread::query()->firstOrCreate(
                    ['id' => $validated['thread_id']],
                );

                if ($thread->title === null) {
                    $thread->title = Str::limit($validated['message'], 60);
                    $thread->save();
                }

                ChatMessage::query()->create([
                    'thread_id' => $thread->id,
                    'role' => 'user',
                    'content' => $validated['message'],
                    'created_at' => now(),
                ]);

                try {
                    $response = Http::timeout($timeout)
                        ->acceptJson()
                        ->asJson()
                        ->post("{$baseUrl}/chat", $validated);
                } catch (Throwable $exception) {
                    Log::warning('AI service request failed', [
                        'error' => $exception->getMessage(),
                        'thread_id' => $validated['thread_id'],
                    ]);

                    throw $exception;
                }

                $body = $response->json();

                if ($response->failed()) {
                    $detail = is_array($body) && isset($body['detail'])
                        ? (is_string($body['detail']) ? $body['detail'] : json_encode($body['detail']))
                        : 'AI service returned an error.';

                    $status = $response->status() >= 500 ? 502 : $response->status();

                    throw new \RuntimeException($detail, $status);
                }

                ChatMessage::query()->create([
                    'thread_id' => $thread->id,
                    'role' => 'assistant',
                    'content' => (string) ($body['assistant_message'] ?? ''),
                    'cited_evidence' => $body['cited_evidence'] ?? null,
                    'suggested_next_actions' => $body['suggested_next_actions'] ?? null,
                    'structured_formulation' => $body['structured_formulation'] ?? null,
                    'structured_formulations' => $body['structured_formulations'] ?? null,
                    'created_at' => now(),
                ]);

                $thread->touch();

                return response()->json($body ?? [], 200);
            });
        } catch (Throwable $exception) {
            Log::warning('Chat transaction failed', [
                'error' => $exception->getMessage(),
                'thread_id' => $validated['thread_id'] ?? null,
            ]);

            $status = $exception->getCode();
            if (! is_int($status) || $status < 400 || $status > 599) {
                $status = 502;
            }

            return response()->json(
                ['message' => $exception->getMessage() ?: 'AI service is unreachable. Please try again.'],
                $status,
            );
        }
    }
}
