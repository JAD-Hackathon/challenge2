<?php

namespace App\Http\Controllers;

abstract class Controller
{
    // EXIF guarda graus/minutos/segundos como frações: ["40/1", "38/1", "2850/100"]
    public static function gpsToDecimal(array $gps, string $ref): float
    {
        $degrees = self::exifFraction($gps[0] ?? 0);
        $minutes = self::exifFraction($gps[1] ?? 0);
        $seconds = self::exifFraction($gps[2] ?? 0);

        $decimal = $degrees + ($minutes / 60) + ($seconds / 3600);

        if (in_array($ref, ['S', 'W'])) {
            $decimal *= -1;
        }

        return $decimal;
    }

    // "2850/100" -> 28.5. Nunca usar eval(): o EXIF vem do utilizador.
    public static function exifFraction($value): float
    {
        if (is_string($value) && str_contains($value, '/')) {
            [$num, $den] = explode('/', $value, 2);

            return (float) $den != 0 ? (float) $num / (float) $den : 0.0;
        }

        return (float) $value;
    }

}
