<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('chat_messages', function (Blueprint $table) {
            $table->json('structured_formulation')->nullable()->after('suggested_next_actions');
            $table->json('structured_formulations')->nullable()->after('structured_formulation');
        });
    }

    public function down(): void
    {
        Schema::table('chat_messages', function (Blueprint $table) {
            $table->dropColumn(['structured_formulation', 'structured_formulations']);
        });
    }
};
