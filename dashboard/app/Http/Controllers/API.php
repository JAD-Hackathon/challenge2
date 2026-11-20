<?php

namespace App\Http\Controllers;

use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;

class API extends Controller
{
    public static function getData($endpoint)
    {
        try {
            $api = Http::get(env('API_URL') . "{$endpoint}");
        } catch (ConnectionException $e) {
            logger()->error("API request to '{$endpoint}' failed: {$e->getMessage()}");

            return ['error' => 'Não foi possível ligar à API.', 'status' => 0];
        }

        if ($api->successful()) {
            return $api->json() ?? [];
        }

        $error = $api->json('detail') ?? $api->reason();
        if (is_array($error)) {
            $error = implode('; ', array_column($error, 'msg'));
        }

        logger()->error("API request to '{$endpoint}' failed", ['status' => $api->status(), 'error' => $error]);

        return ['error' => $error, 'status' => $api->status()];
    }

    public static function getFile($endpoint)
    {
        $api = Http::get(env('API_URL') . "{$endpoint}");

        if ($api->successful()) {
            return $api->body();
        }

        logger()->error("API request to '{$endpoint}' failed", ['status' => $api->status()]);

        return null;
    }

    public static function sendFiles($endpoint, array $files, array $fields = [])
    {
        $request = Http::timeout(600);

        // ['images' => [$f1, $f2]] anexa cada ficheiro com o mesmo nome de campo; null é ignorado
        foreach ($files as $name => $file) {
            foreach (is_array($file) ? $file : [$file] as $f) {
                if ($f) {
                    $request = $request->attach($name, fopen($f->getRealPath(), 'r'), $f->getClientOriginalName());
                }
            }
        }

        $api = $request->post(env('API_URL') . "{$endpoint}", $fields);

        if (! $api->successful()) {
            logger()->error("API upload to '{$endpoint}' failed", ['status' => $api->status(), 'body' => $api->body()]);
        }

        return ['ok' => $api->successful(), 'status' => $api->status(), 'data' => $api->json() ?? []];
    }

    // POST com JSON (ou sem corpo). Igual ao getData: dados, ou ['error' => ..., 'status' => ...]
    public static function postData($endpoint, array $data = [])
    {
        return self::sendJson('post', $endpoint, $data);
    }

    // PATCH com JSON: altera só os campos enviados
    public static function patchData($endpoint, array $data)
    {
        return self::sendJson('patch', $endpoint, $data);
    }

    private static function sendJson($method, $endpoint, array $data)
    {
        try {
            $api = Http::asJson()->{$method}(env('API_URL') . "{$endpoint}", $data);
        } catch (ConnectionException $e) {
            logger()->error("API request to '{$endpoint}' failed: {$e->getMessage()}");

            return ['error' => 'Não foi possível ligar à API.', 'status' => 0];
        }

        if ($api->successful()) {
            return $api->json() ?? [];
        }

        $error = $api->json('detail') ?? $api->reason();
        if (is_array($error)) {
            $error = implode('; ', array_column($error, 'msg'));
        }

        logger()->error("API request to '{$endpoint}' failed", ['status' => $api->status(), 'error' => $error]);

        return ['error' => $error, 'status' => $api->status()];
    }
}
