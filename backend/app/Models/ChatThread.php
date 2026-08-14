<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Relations\HasOne;

class ChatThread extends Model
{
    use HasUuids;

    public $incrementing = false;

    protected $keyType = 'string';

    protected $fillable = [
        'title',
        'user_id',
    ];

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    public function messages(): HasMany
    {
        return $this->hasMany(ChatMessage::class, 'thread_id')->orderBy('created_at');
    }

    public static function ownedBy(User $user, string $id): self
    {
        $thread = static::query()
            ->where('id', $id)
            ->where('user_id', $user->id)
            ->first();

        if ($thread === null) {
            abort(404, 'Thread not found.');
        }

        return $thread;
    }

    public function latestMessage(): HasOne
    {
        return $this->hasOne(ChatMessage::class, 'thread_id')->latestOfMany('created_at');
    }
}
