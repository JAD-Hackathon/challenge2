<?php

namespace App\Support;

use App\Http\Controllers\Controller;
use Illuminate\Support\Facades\Http;
use Throwable;

/**
 * Finds where a photo was taken (lat, lon, heading), trying each source in turn:
 *   1. EXIF GPS tags (phones, cameras)
 *   2. Mapillary, when the file name contains a Mapillary image id (e.g. 1155336678213666.jpg)
 * Whatever is still missing is left null, for the user to fill in on the form.
 */
class PhotoLocation
{
    /** @return array{lat: ?float, lon: ?float, heading: ?float, source: ?string} */
    public static function resolve(string $path, string $originalName): array
    {
        $found = ['lat' => null, 'lon' => null, 'heading' => null, 'source' => null];

        foreach ([
            'EXIF' => fn () => self::fromExif($path),
            'Mapillary' => fn () => self::fromMapillary($originalName),
        ] as $source => $lookup) {
            $result = $lookup();
            if (! $result) {
                continue;
            }

            $usedThisSource = false;
            foreach (['lat', 'lon', 'heading'] as $key) {
                if ($found[$key] === null && isset($result[$key])) {
                    $found[$key] = $result[$key];
                    $usedThisSource = true;
                }
            }
            if ($usedThisSource) {
                $found['source'] = $found['source'] ? "{$found['source']} + {$source}" : $source;
            }

            if ($found['lat'] !== null && $found['heading'] !== null) {
                break;
            }
        }

        return $found;
    }

    private static function fromExif(string $path): ?array
    {
        // exif_read_data only reads JPEG/TIFF; PNG and others just return false
        $exif = @exif_read_data($path);
        if (! $exif) {
            return null;
        }

        $result = [];

        if (! empty($exif['GPSLatitude']) && ! empty($exif['GPSLongitude'])) {
            $result['lat'] = round(Controller::gpsToDecimal($exif['GPSLatitude'], $exif['GPSLatitudeRef'] ?? 'N'), 6);
            $result['lon'] = round(Controller::gpsToDecimal($exif['GPSLongitude'], $exif['GPSLongitudeRef'] ?? 'E'), 6);
        }

        // Direction the camera was pointing; some devices only write the destination bearing
        $direction = $exif['GPSImgDirection'] ?? $exif['GPSDestBearing'] ?? null;
        if ($direction !== null) {
            $result['heading'] = self::normaliseHeading(Controller::exifFraction($direction));
        }

        return $result ?: null;
    }

    private static function fromMapillary(string $originalName): ?array
    {
        $token = env('MAPILLARY_ACCESS_TOKEN');
        // Mapillary ids are long numbers; take the first run of 10+ digits in the name
        if (! $token || ! preg_match('/\d{10,}/', pathinfo($originalName, PATHINFO_FILENAME), $m)) {
            return null;
        }

        try {
            $response = Http::withHeaders(['Authorization' => "OAuth {$token}"])
                ->timeout(10)
                ->get("https://graph.mapillary.com/{$m[0]}", [
                    'fields' => 'computed_geometry,geometry,computed_compass_angle,compass_angle',
                ]);
        } catch (Throwable) {
            return null;
        }

        if (! $response->successful()) {
            return null;
        }

        $data = $response->json();
        $coords = ($data['computed_geometry'] ?? $data['geometry'] ?? [])['coordinates'] ?? null;
        $angle = $data['computed_compass_angle'] ?? $data['compass_angle'] ?? null;

        $result = [];
        if ($coords) {
            $result['lon'] = round($coords[0], 6);
            $result['lat'] = round($coords[1], 6);
        }
        if ($angle !== null) {
            $result['heading'] = self::normaliseHeading($angle);
        }

        return $result ?: null;
    }

    private static function normaliseHeading(float $degrees): float
    {
        return round(fmod(fmod($degrees, 360) + 360, 360), 1); // 0–360, "360" becomes 0
    }
}
