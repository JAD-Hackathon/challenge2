<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use ZipArchive;

/**
 * Local-only helper: downloads 5-10 Mapillary photos as a ZIP.
 *
 * GET /dev/mapillary?n=8&bbox=minLon,minLat,maxLon,maxLat
 */
class MapillaryDownload extends Controller
{
    private const API = 'https://graph.mapillary.com/images';

    // Aveiro city centre (keep bboxes small: Mapillary rejects large areas)
    private const DEFAULT_BBOX = '-8.660,40.636,-8.645,40.645';

    public function __invoke(Request $request)
    {
        abort_unless(app()->environment('local'), 404);

        $token = env('MAPILLARY_ACCESS_TOKEN');
        abort_unless($token, 500, 'MAPILLARY_ACCESS_TOKEN is not set');

        $n = max(5, min(10, (int) $request->query('n', 8)));
        $bbox = $request->query('bbox', self::DEFAULT_BBOX);
        abort_unless(preg_match('/^-?\d+(\.\d+)?(,-?\d+(\.\d+)?){3}$/', $bbox), 422, 'bbox must be minLon,minLat,maxLon,maxLat');

        // Ask for more than needed so we can skip panoramas and images without a thumbnail
        $response = Http::withHeaders(['Authorization' => "OAuth {$token}"])
            ->timeout(30)
            ->get(self::API, [
                'bbox' => $bbox,
                'fields' => 'id,captured_at,computed_geometry,geometry,computed_compass_angle,compass_angle,is_pano,creator,thumb_2048_url',
                'limit' => 100,
            ]);

        abort_unless($response->successful(), 502, 'Mapillary error: ' . $response->body());

        $images = collect($response->json('data', []))
            ->filter(fn ($img) => ! ($img['is_pano'] ?? false) && ! empty($img['thumb_2048_url']))
            ->shuffle()
            ->take($n)
            ->values();

        abort_if($images->isEmpty(), 404, 'No Mapillary images found in this bbox');

        $zipPath = tempnam(sys_get_temp_dir(), 'mly') . '.zip';
        $zip = new ZipArchive();
        $zip->open($zipPath, ZipArchive::CREATE | ZipArchive::OVERWRITE);

        $manifest = [];
        foreach ($images as $img) {
            $photo = Http::timeout(30)->get($img['thumb_2048_url']);
            if (! $photo->successful()) {
                continue;
            }

            $zip->addFromString("{$img['id']}.jpg", $photo->body());

            $coords = ($img['computed_geometry'] ?? $img['geometry'] ?? [])['coordinates'] ?? [null, null];
            $manifest[] = [
                'id' => $img['id'],
                'file' => "{$img['id']}.jpg",
                'lon' => $coords[0],
                'lat' => $coords[1],
                'compass_angle' => $img['computed_compass_angle'] ?? $img['compass_angle'] ?? null,
                'captured_at' => isset($img['captured_at']) ? date(DATE_ATOM, intdiv($img['captured_at'], 1000)) : null,
                'author' => $img['creator']['username'] ?? null,
                'license' => 'CC BY-SA 4.0',
            ];
        }

        $zip->addFromString('manifest.json', json_encode($manifest, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));
        $zip->close();

        return response()
            ->download($zipPath, 'mapillary_' . now()->format('Ymd_His') . '.zip')
            ->deleteFileAfterSend();
    }
}
