<?php

namespace Tests\Feature;

use App\Models\ChatThread;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Laravel\Sanctum\Sanctum;
use Tests\TestCase;

class AuthTest extends TestCase
{
    use RefreshDatabase;

    public function test_register_creates_user_and_returns_token(): void
    {
        $response = $this->postJson('/api/auth/register', [
            'name' => 'Sara Formulator',
            'email' => 'sara@example.com',
            'password' => 'secret123',
            'password_confirmation' => 'secret123',
        ]);

        $response->assertCreated()
            ->assertJsonStructure(['token', 'user' => ['id', 'name', 'email', 'created_at']]);

        $this->assertDatabaseHas('users', [
            'email' => 'sara@example.com',
            'name' => 'Sara Formulator',
        ]);
    }

    public function test_login_returns_token_for_valid_credentials(): void
    {
        $user = User::factory()->create([
            'email' => 'sara@example.com',
        ]);

        $response = $this->postJson('/api/auth/login', [
            'email' => 'sara@example.com',
            'password' => 'password',
        ]);

        $response->assertOk()
            ->assertJsonPath('user.email', $user->email)
            ->assertJsonStructure(['token', 'user']);
    }

    public function test_login_rejects_invalid_credentials(): void
    {
        User::factory()->create(['email' => 'sara@example.com']);

        $this->postJson('/api/auth/login', [
            'email' => 'sara@example.com',
            'password' => 'wrong-password',
        ])->assertUnprocessable();
    }

    public function test_me_requires_authentication(): void
    {
        $this->getJson('/api/auth/me')->assertUnauthorized();
    }

    public function test_authenticated_user_can_view_and_update_profile(): void
    {
        $user = User::factory()->create(['name' => 'Old Name']);
        Sanctum::actingAs($user);

        $this->getJson('/api/auth/me')
            ->assertOk()
            ->assertJsonPath('user.email', $user->email);

        $this->patchJson('/api/auth/profile', [
            'name' => 'New Name',
            'email' => 'new@example.com',
        ])
            ->assertOk()
            ->assertJsonPath('user.name', 'New Name')
            ->assertJsonPath('user.email', 'new@example.com');
    }

    public function test_password_update_rotates_token(): void
    {
        $user = User::factory()->create();
        $oldToken = $user->createToken('web')->plainTextToken;

        $response = $this->withToken($oldToken)->patchJson('/api/auth/password', [
            'current_password' => 'password',
            'password' => 'new-secret',
            'password_confirmation' => 'new-secret',
        ]);

        $response->assertOk()->assertJsonStructure(['token', 'user']);

        $this->flushHeaders();
        auth()->forgetGuards();

        $this->withToken($oldToken)->getJson('/api/auth/me')->assertUnauthorized();
        $this->withToken($response->json('token'))->getJson('/api/auth/me')->assertOk();
    }

    public function test_user_can_delete_account(): void
    {
        $user = User::factory()->create();
        $thread = ChatThread::query()->create([
            'user_id' => $user->id,
            'title' => 'My formula',
        ]);
        Sanctum::actingAs($user);

        $this->deleteJson('/api/auth/account', [
            'password' => 'password',
        ])->assertNoContent();

        $this->assertDatabaseMissing('users', ['id' => $user->id]);
        $this->assertDatabaseMissing('chat_threads', ['id' => $thread->id]);
    }

    public function test_chat_threads_are_isolated_per_user(): void
    {
        $owner = User::factory()->create();
        $stranger = User::factory()->create();
        $thread = ChatThread::query()->create([
            'user_id' => $owner->id,
            'title' => 'Private thread',
        ]);

        Sanctum::actingAs($stranger);

        $this->getJson('/api/chat/threads')
            ->assertOk()
            ->assertJsonCount(0, 'threads');

        $this->getJson("/api/chat/threads/{$thread->id}")->assertNotFound();
        $this->patchJson("/api/chat/threads/{$thread->id}", ['title' => 'Hijack'])->assertNotFound();
        $this->deleteJson("/api/chat/threads/{$thread->id}")->assertNotFound();

        Sanctum::actingAs($owner);
        $this->getJson("/api/chat/threads/{$thread->id}")
            ->assertOk()
            ->assertJsonPath('title', 'Private thread');
    }

    public function test_chat_routes_require_authentication(): void
    {
        $this->getJson('/api/chat/threads')->assertUnauthorized();
        $this->postJson('/api/chat/threads')->assertUnauthorized();
    }
}
