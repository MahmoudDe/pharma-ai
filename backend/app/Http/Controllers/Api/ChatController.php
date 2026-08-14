<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\ChatMessage;
use App\Models\ChatThread;
use App\Models\User;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Str;
use Symfony\Component\HttpFoundation\StreamedResponse;
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
            'assistant_message_id' => ['sometimes', 'string', 'uuid'],
        ]);

        $baseUrl = rtrim((string) config('services.ai.url'), '/');
        $timeout = (int) config('services.ai.timeout', 45);

        if ($baseUrl === '') {
            return response()->json(
                ['message' => 'AI_SERVICE_URL is not configured.'],
                503,
            );
        }

        $user = $request->user();
        if (! $user instanceof User) {
            abort(401);
        }

        try {
            return DB::transaction(function () use ($validated, $baseUrl, $timeout, $user) {
                $thread = $this->resolveThreadForUser($user, $validated['thread_id']);

                if ($thread->title === null) {
                    $thread->title = Str::limit($validated['message'], 60);
                    $thread->save();
                }

                $validated['history'] = $this->chatHistoryForThread($thread->id);

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

                    throw new \RuntimeException(
                        $this->aiConnectionMessage($exception),
                        502,
                        $exception,
                    );
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
                    'id' => $validated['assistant_message_id'] ?? Str::uuid()->toString(),
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

    /**
     * Stream a chat turn via SSE from the AI service; persist messages when complete.
     */
    public function messagesStream(Request $request): StreamedResponse|JsonResponse
    {
        $validated = $request->validate([
            'thread_id' => ['required', 'string', 'uuid'],
            'message' => ['required', 'string'],
            'structured_brief' => ['sometimes', 'array'],
            'assistant_message_id' => ['sometimes', 'string', 'uuid'],
        ]);

        $baseUrl = rtrim((string) config('services.ai.url'), '/');
        $timeout = (int) config('services.ai.timeout', 120);

        if ($baseUrl === '') {
            return response()->json(
                ['message' => 'AI_SERVICE_URL is not configured.'],
                503,
            );
        }

        try {
            $user = $request->user();
            if (! $user instanceof User) {
                abort(401);
            }

            $thread = $this->resolveThreadForUser($user, $validated['thread_id']);

            if ($thread->title === null) {
                $thread->title = Str::limit($validated['message'], 60);
                $thread->save();
            }

            $validated['history'] = $this->chatHistoryForThread($thread->id);

            ChatMessage::query()->create([
                'thread_id' => $thread->id,
                'role' => 'user',
                'content' => $validated['message'],
                'created_at' => now(),
            ]);

            return response()->stream(
                function () use ($validated, $baseUrl, $timeout, $thread): void {
                    $donePayload = null;

                    try {
                        $response = Http::withOptions(['stream' => true])
                            ->timeout($timeout)
                            ->withHeaders(['Accept' => 'text/event-stream'])
                            ->asJson()
                            ->post("{$baseUrl}/chat/stream", $validated);

                        if ($response->failed()) {
                            $detail = $response->json('detail') ?? 'AI service returned an error.';
                            echo "event: error\ndata: ".json_encode(['message' => $detail])."\n\n";
                            if (function_exists('ob_flush')) {
                                @ob_flush();
                            }
                            flush();

                            return;
                        }

                        $body = $response->toPsrResponse()->getBody();
                        $carry = '';

                        while (! $body->eof()) {
                            $chunk = $body->read(2048);
                            if ($chunk === '') {
                                continue;
                            }

                            echo $chunk;
                            if (function_exists('ob_flush')) {
                                @ob_flush();
                            }
                            flush();

                            $carry .= $chunk;
                            while (($pos = strpos($carry, "\n\n")) !== false) {
                                $block = substr($carry, 0, $pos);
                                $carry = substr($carry, $pos + 2);
                                if (str_contains($block, 'event: done')) {
                                    foreach (explode("\n", $block) as $line) {
                                        if (str_starts_with($line, 'data: ')) {
                                            $donePayload = json_decode(substr($line, 6), true);
                                        }
                                    }
                                }
                            }
                        }
                    } catch (Throwable $exception) {
                        Log::warning('AI stream failed', [
                            'error' => $exception->getMessage(),
                            'thread_id' => $validated['thread_id'],
                        ]);
                        echo 'event: error'."\ndata: ".json_encode([
                            'message' => $this->aiConnectionMessage($exception),
                        ])."\n\n";
                        if (function_exists('ob_flush')) {
                            @ob_flush();
                        }
                        flush();

                        return;
                    }

                    if (is_array($donePayload)) {
                        ChatMessage::query()->create([
                            'id' => $validated['assistant_message_id'] ?? Str::uuid()->toString(),
                            'thread_id' => $thread->id,
                            'role' => 'assistant',
                            'content' => (string) ($donePayload['assistant_message'] ?? ''),
                            'cited_evidence' => $donePayload['cited_evidence'] ?? null,
                            'suggested_next_actions' => $donePayload['suggested_next_actions'] ?? null,
                            'structured_formulation' => $donePayload['structured_formulation'] ?? null,
                            'structured_formulations' => $donePayload['structured_formulations'] ?? null,
                            'created_at' => now(),
                        ]);
                        $thread->touch();
                    }
                },
                200,
                [
                    'Content-Type' => 'text/event-stream',
                    'Cache-Control' => 'no-cache',
                    'Connection' => 'keep-alive',
                    'X-Accel-Buffering' => 'no',
                ],
            );
        } catch (Throwable $exception) {
            Log::warning('Chat stream setup failed', [
                'error' => $exception->getMessage(),
                'thread_id' => $validated['thread_id'] ?? null,
            ]);

            return response()->json(
                ['message' => $exception->getMessage() ?: 'AI service is unreachable. Please try again.'],
                502,
            );
        }
    }

    public function feedback(Request $request, string $messageId): JsonResponse
    {
        $validated = $request->validate([
            'rating' => ['required', 'integer', 'in:1,-1'],
            'user_message' => ['sometimes', 'string', 'nullable'],
        ]);

        $message = ChatMessage::query()->with('thread')->find($messageId);
        if ($message === null || $message->role !== 'assistant') {
            return response()->json(['message' => 'Assistant message not found.'], 404);
        }

        if ($message->thread === null || (int) $message->thread->user_id !== (int) $request->user()->id) {
            return response()->json(['message' => 'Assistant message not found.'], 404);
        }

        $message->feedback_rating = (int) $validated['rating'];
        $message->save();

        $baseUrl = rtrim((string) config('services.ai.url'), '/');
        if ($baseUrl !== '') {
            try {
                Http::timeout(10)
                    ->acceptJson()
                    ->asJson()
                    ->post("{$baseUrl}/eval/feedback", [
                        'message_id' => $messageId,
                        'thread_id' => $message->thread_id,
                        'rating' => (int) $validated['rating'],
                        'user_message' => $validated['user_message'] ?? null,
                        'assistant_message' => $message->content,
                    ]);
            } catch (Throwable $exception) {
                Log::warning('Feedback eval log failed', ['error' => $exception->getMessage()]);
            }
        }

        return response()->json(['ok' => true, 'feedback_rating' => $message->feedback_rating]);
    }

    private function aiConnectionMessage(Throwable $exception): string
    {
        $message = $exception->getMessage();

        if (
            str_contains($message, '9000')
            || str_contains($message, 'Connection refused')
            || str_contains($message, 'Could not connect')
        ) {
            return 'AI service is not running. Start it: cd ai-service && .venv/bin/uvicorn app.main:app --port 9000 --reload';
        }

        return $message;
    }

    private function resolveThreadForUser(User $user, string $threadId): ChatThread
    {
        $thread = ChatThread::query()->find($threadId);

        if ($thread === null) {
            return ChatThread::query()->create([
                'id' => $threadId,
                'user_id' => $user->id,
            ]);
        }

        if ((int) $thread->user_id !== (int) $user->id) {
            abort(404, 'Thread not found.');
        }

        return $thread;
    }

    /**
     * @return list<array{role: string, content: string}>
     */
    private function chatHistoryForThread(string $threadId, int $limit = 10): array
    {
        $rows = ChatMessage::query()
            ->where('thread_id', $threadId)
            ->orderByDesc('created_at')
            ->orderByDesc('id')
            ->limit($limit)
            ->get(['role', 'content']);

        return $rows
            ->reverse()
            ->values()
            ->map(fn (ChatMessage $message) => [
                'role' => $message->role,
                'content' => $message->content,
            ])
            ->all();
    }
}
