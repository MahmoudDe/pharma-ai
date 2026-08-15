<?php

use App\Http\Controllers\Api\AuthController;
use App\Http\Controllers\Api\ChatController;
use App\Http\Controllers\Api\ChatThreadController;
use App\Http\Controllers\Api\CorpusController;
use App\Http\Controllers\Api\FormulationController;
use App\Http\Controllers\Api\SourceController;
use App\Http\Controllers\Api\WarehouseController;
use Illuminate\Support\Facades\Http;
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
        $response = Http::timeout(10)
            ->acceptJson()
            ->get("{$baseUrl}/health/ready");

        return response()->json($response->json() ?? [], $response->status());
    } catch (Throwable $e) {
        return response()->json(['ready' => false, 'message' => $e->getMessage()], 502);
    }
});

Route::middleware('throttle:auth')->group(static function () {
    Route::post('/auth/register', [AuthController::class, 'register']);
    Route::post('/auth/login', [AuthController::class, 'login']);
});

Route::middleware('auth:sanctum')->group(static function () {
    Route::post('/auth/logout', [AuthController::class, 'logout']);
    Route::get('/auth/me', [AuthController::class, 'me']);
    Route::patch('/auth/profile', [AuthController::class, 'updateProfile']);
    Route::patch('/auth/password', [AuthController::class, 'updatePassword']);
    Route::delete('/auth/account', [AuthController::class, 'destroy']);

    Route::get('/chat/threads', [ChatThreadController::class, 'index']);
    Route::post('/chat/threads', [ChatThreadController::class, 'store']);
    Route::get('/chat/threads/{id}', [ChatThreadController::class, 'show']);
    Route::patch('/chat/threads/{id}', [ChatThreadController::class, 'update']);
    Route::delete('/chat/threads/{id}', [ChatThreadController::class, 'destroy']);
    Route::post('/chat/messages', [ChatController::class, 'messages']);
    Route::post('/chat/messages/stream', [ChatController::class, 'messagesStream']);
    Route::post('/chat/messages/{messageId}/feedback', [ChatController::class, 'feedback']);
});

Route::get('/corpus/stats', [CorpusController::class, 'stats']);
Route::get('/corpus/ingest-quality', [CorpusController::class, 'ingestQuality']);
Route::get('/corpus/manifest', [CorpusController::class, 'manifest']);
Route::post('/corpus/ingest', [CorpusController::class, 'startIngest']);
Route::get('/corpus/ingest', [CorpusController::class, 'listIngestJobs']);
Route::get('/corpus/ingest/{jobId}', [CorpusController::class, 'getIngestJob']);
Route::get('/formulations', [FormulationController::class, 'index']);
Route::get('/formulations/review', [FormulationController::class, 'review']);
Route::post('/formulations/search', [FormulationController::class, 'search']);
Route::post('/formulations/compare', [FormulationController::class, 'compare']);
Route::get('/formulations/prices', [FormulationController::class, 'prices']);
Route::post('/formulations/prices/upload', [FormulationController::class, 'uploadPrices']);
Route::get('/formulations/{formulationId}', [FormulationController::class, 'show']);
Route::patch('/formulations/{formulationId}', [FormulationController::class, 'patch']);
Route::post('/formulations/{formulationId}/substitutions', [FormulationController::class, 'substitutions']);
Route::post('/formulations/{formulationId}/compliance', [FormulationController::class, 'compliance']);
Route::get('/formulations/{formulationId}/cost', [FormulationController::class, 'cost']);
Route::get('/kbs/report/{formulationId}', [FormulationController::class, 'kbsReport']);
Route::post('/kbs/validate/{formulationId}', [FormulationController::class, 'kbsValidate']);
Route::get('/kbs/rules', [FormulationController::class, 'kbsRules']);
Route::get('/sources/{docId}', [SourceController::class, 'show'])->where('docId', '[^/]+');

Route::post('/warehouse/upload', [WarehouseController::class, 'upload']);
Route::post('/warehouse/resolve', [WarehouseController::class, 'resolve']);
Route::get('/warehouse/materials', [WarehouseController::class, 'materials']);
Route::patch('/warehouse/materials/{materialId}', [WarehouseController::class, 'setAlias']);
Route::post('/warehouse/discover', [WarehouseController::class, 'discover']);
Route::get('/warehouse/discover/{uploadId}', [WarehouseController::class, 'discoverResults']);
