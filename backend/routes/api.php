<?php

use App\Http\Controllers\Api\ChatController;
use App\Http\Controllers\Api\ChatThreadController;
use App\Http\Controllers\Api\WarehouseController;
use Illuminate\Support\Facades\Route;

Route::get('/health', static function () {
    return response()->json([
        'status' => 'ok',
        'service' => 'backend',
    ]);
});

Route::get('/health/ready', static function () {
    $baseUrl = rtrim((string) config('services.ai.url'), '/');
    if ($baseUrl === '') {
        return response()->json(['ready' => false, 'message' => 'AI_SERVICE_URL is not configured.'], 503);
    }
    try {
        $response = \Illuminate\Support\Facades\Http::timeout(10)
            ->acceptJson()
            ->get("{$baseUrl}/health/ready");
        return response()->json($response->json() ?? [], $response->status());
    } catch (\Throwable $e) {
        return response()->json(['ready' => false, 'message' => $e->getMessage()], 502);
    }
});

Route::get('/chat/threads', [ChatThreadController::class, 'index']);
Route::post('/chat/threads', [ChatThreadController::class, 'store']);
Route::get('/chat/threads/{id}', [ChatThreadController::class, 'show']);
Route::patch('/chat/threads/{id}', [ChatThreadController::class, 'update']);
Route::delete('/chat/threads/{id}', [ChatThreadController::class, 'destroy']);
Route::post('/chat/messages', [ChatController::class, 'messages']);

Route::post('/warehouse/upload', [WarehouseController::class, 'upload']);
Route::post('/warehouse/resolve', [WarehouseController::class, 'resolve']);
Route::get('/warehouse/materials', [WarehouseController::class, 'materials']);
Route::post('/warehouse/discover', [WarehouseController::class, 'discover']);
Route::get('/warehouse/discover/{uploadId}', [WarehouseController::class, 'discoverResults']);
