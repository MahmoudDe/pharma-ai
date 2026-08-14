<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\ChatMessage;
use App\Models\ChatThread;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Str;

class ChatThreadController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        $threads = ChatThread::query()
            ->where('user_id', $request->user()->id)
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

    public function store(Request $request): JsonResponse
    {
        $thread = ChatThread::query()->create([
            'user_id' => $request->user()->id,
        ]);

        return response()->json([
            'id' => $thread->id,
            'title' => $thread->title,
            'updated_at' => $thread->updated_at?->toIso8601String(),
        ], 201);
    }

    public function show(Request $request, string $id): JsonResponse
    {
        $thread = ChatThread::ownedBy($request->user(), $id);

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
                'structured_formulation' => $message->structured_formulation,
                'structured_formulations' => $message->structured_formulations,
                'feedback_rating' => $message->feedback_rating,
            ]);

        return response()->json([
            'id' => $thread->id,
            'title' => $thread->title ?? 'New chat',
            'updated_at' => $thread->updated_at?->toIso8601String(),
            'messages' => $messages,
        ]);
    }

    public function update(Request $request, string $id): JsonResponse
    {
        $thread = ChatThread::ownedBy($request->user(), $id);

        $validated = $request->validate([
            'title' => ['required', 'string', 'max:120'],
        ]);

        $thread->title = $validated['title'];
        $thread->save();

        return response()->json([
            'id' => $thread->id,
            'title' => $thread->title,
            'updated_at' => $thread->updated_at?->toIso8601String(),
        ]);
    }

    public function destroy(Request $request, string $id): JsonResponse
    {
        $thread = ChatThread::ownedBy($request->user(), $id);
        $thread->delete();

        return response()->json(null, 204);
    }
}
