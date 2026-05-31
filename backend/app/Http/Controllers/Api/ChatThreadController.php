<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\ChatMessage;
use App\Models\ChatThread;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Str;

class ChatThreadController extends Controller
{
    public function index(): JsonResponse
    {
        $threads = ChatThread::query()
            ->with('latestMessage')
            ->orderByDesc('updated_at')
            ->get()
            ->map(static function (ChatThread $thread) {
                $latest = $thread->latestMessage;

                return [
                    'id' => $thread->id,
                    'title' => $thread->title ?? 'New chat',
                    'updated_at' => $thread->updated_at?->toIso8601String(),
                    'preview' => $latest ? Str::limit($latest->content, 80) : null,
                ];
            });

        return response()->json(['threads' => $threads]);
    }

    public function store(): JsonResponse
    {
        $thread = ChatThread::query()->create();

        return response()->json([
            'id' => $thread->id,
            'title' => $thread->title,
            'updated_at' => $thread->updated_at?->toIso8601String(),
        ], 201);
    }

    public function show(string $id): JsonResponse
    {
        $thread = ChatThread::query()->find($id);

        if ($thread === null) {
            return response()->json(['message' => 'Thread not found.'], 404);
        }

        $messages = $thread->messages()
            ->orderBy('created_at')
            ->get()
            ->map(static fn (ChatMessage $message) => [
                'id' => $message->id,
                'role' => $message->role,
                'content' => $message->content,
                'created_at' => $message->created_at?->toIso8601String(),
                'cited_evidence' => $message->cited_evidence,
                'suggested_next_actions' => $message->suggested_next_actions,
            ]);

        return response()->json([
            'id' => $thread->id,
            'title' => $thread->title ?? 'New chat',
            'updated_at' => $thread->updated_at?->toIso8601String(),
            'messages' => $messages,
        ]);
    }
}
