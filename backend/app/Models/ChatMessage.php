<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class ChatMessage extends Model
{
    use HasUuids;

    public $incrementing = false;

    public $timestamps = false;

    protected $keyType = 'string';

    protected $fillable = [
        'thread_id',
        'role',
        'content',
        'cited_evidence',
        'suggested_next_actions',
        'structured_formulation',
        'structured_formulations',
        'feedback_rating',
        'created_at',
    ];

    protected $casts = [
        'cited_evidence' => 'array',
        'suggested_next_actions' => 'array',
        'structured_formulation' => 'array',
        'structured_formulations' => 'array',
        'created_at' => 'datetime',
    ];

    public function thread(): BelongsTo
    {
        return $this->belongsTo(ChatThread::class, 'thread_id');
    }
}
