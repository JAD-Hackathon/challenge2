<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;

class API extends Controller
{
    public static function getData($endpoint)
    {
        $api = Http::get(env('API_URL') . "{$endpoint}");

        if ($api->successful()) {
            return $api->json() ?? [];
        }

        logger()->error("API request to '{$endpoint}' failed", ['status' => $api->status()]);

        return [];
    }
}
