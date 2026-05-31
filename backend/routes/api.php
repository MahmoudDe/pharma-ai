<?php

use App\Http\Controllers\Api\ChatController;
use App\Http\Controllers\Api\ChatThreadController;
use Illuminate\Support\Facades\Route;

Route::get('/health', static function () {
    return response()->json([
        'status' => 'ok',
        'service' => 'backend',
    ]);
});

Route::get('/chat/threads', [ChatThreadController::class, 'index']);
Route::post('/chat/threads', [ChatThreadController::class, 'store']);
Route::get('/chat/threads/{id}', [ChatThreadController::class, 'show']);
Route::post('/chat/messages', [ChatController::class, 'messages']);
