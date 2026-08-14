<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\User;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Hash;
use Illuminate\Validation\Rule;
use Illuminate\Validation\ValidationException;
use Laravel\Sanctum\PersonalAccessToken;

class AuthController extends Controller
{
    public function register(Request $request): JsonResponse
    {
        $validated = $request->validate([
            'name' => ['required', 'string', 'max:80'],
            'email' => ['required', 'string', 'email:filter', 'max:255', 'unique:users,email'],
            'password' => ['required', 'string', 'min:8', 'confirmed'],
        ]);

        $user = User::query()->create([
            'name' => trim($validated['name']),
            'email' => strtolower($validated['email']),
            'password' => $validated['password'],
        ]);

        return response()->json($this->tokenPayload($user), 201);
    }

    public function login(Request $request): JsonResponse
    {
        $validated = $request->validate([
            'email' => ['required', 'string', 'email:filter'],
            'password' => ['required', 'string'],
        ]);

        $user = User::query()->where('email', strtolower($validated['email']))->first();

        if ($user === null || ! Hash::check($validated['password'], $user->password)) {
            throw ValidationException::withMessages([
                'email' => ['Those credentials do not match our records.'],
            ]);
        }

        $user->tokens()->where('name', 'web')->delete();

        return response()->json($this->tokenPayload($user));
    }

    public function logout(Request $request): JsonResponse
    {
        $token = $this->actor($request)->currentAccessToken();
        if ($token instanceof PersonalAccessToken) {
            $token->delete();
        }

        return response()->json(['ok' => true]);
    }

    public function me(Request $request): JsonResponse
    {
        return response()->json(['user' => $this->userPayload($this->actor($request))]);
    }

    public function updateProfile(Request $request): JsonResponse
    {
        $user = $this->actor($request);

        $validated = $request->validate([
            'name' => ['required', 'string', 'max:80'],
            'email' => [
                'required',
                'string',
                'email:filter',
                'max:255',
                Rule::unique('users', 'email')->ignore($user->id),
            ],
        ]);

        $user->name = trim($validated['name']);
        $user->email = strtolower($validated['email']);
        $user->save();

        return response()->json(['user' => $this->userPayload($user)]);
    }

    public function updatePassword(Request $request): JsonResponse
    {
        $user = $this->actor($request);

        $validated = $request->validate([
            'current_password' => ['required', 'string'],
            'password' => ['required', 'string', 'min:8', 'confirmed'],
        ]);

        if (! Hash::check($validated['current_password'], $user->password)) {
            throw ValidationException::withMessages([
                'current_password' => ['The current password is incorrect.'],
            ]);
        }

        $user->password = $validated['password'];
        $user->save();
        $user->tokens()->delete();

        return response()->json($this->tokenPayload($user));
    }

    public function destroy(Request $request): JsonResponse
    {
        $user = $this->actor($request);

        $validated = $request->validate([
            'password' => ['required', 'string'],
        ]);

        if (! Hash::check($validated['password'], $user->password)) {
            throw ValidationException::withMessages([
                'password' => ['The password is incorrect.'],
            ]);
        }

        $user->tokens()->delete();
        $user->delete();

        return response()->json(null, 204);
    }

    private function actor(Request $request): User
    {
        $user = $request->user();
        if (! $user instanceof User) {
            abort(401);
        }

        return $user;
    }

    /**
     * @return array{token: string, user: array{id: int, name: string, email: string, created_at: string|null}}
     */
    private function tokenPayload(User $user): array
    {
        return [
            'token' => $user->createToken('web')->plainTextToken,
            'user' => $this->userPayload($user),
        ];
    }

    /**
     * @return array{id: int, name: string, email: string, created_at: string|null}
     */
    private function userPayload(User $user): array
    {
        return [
            'id' => $user->id,
            'name' => $user->name,
            'email' => $user->email,
            'created_at' => $user->created_at?->toIso8601String(),
        ];
    }
}
