<?php

namespace App\Support;

use Illuminate\Support\Facades\URL;

// Coisas dos elementos usadas em vários separadores (mapa, experimenta, catálogo)
class Elementos
{
    // Tipos que a API aceita ("categoria.tipo" => nome). Igual a api/app/core/taxonomy.py
    const TYPES = [
        'sign.stop' => 'Stop',
        'sign.yield' => 'Cedência de passagem',
        'sign.speed_limit' => 'Limite de velocidade',
        'sign.other' => 'Outro sinal',
        'light.street_lamp' => 'Candeeiro',
        'light.street_pole' => 'Poste de luz',
        'waste.underground' => 'Contentor subterrâneo',
        'waste.recycling_island' => 'Ecoponto (ilha de reciclagem)',
        'waste.general' => 'Contentor indiferenciado',
    ];

    const LEGEND = [
        'Sinalização' => [
            ['sign', 'stop', 'Stop'],
            ['sign', 'yield', 'Cedência de passagem'],
            ['sign', 'speed_limit', 'Limite de velocidade'],
        ],
        'Iluminação' => [
            ['light', 'street_lamp', 'Candeeiro'],
            ['light', 'street_pole', 'Poste de luz'],
        ],
        'Resíduos' => [
            ['waste', 'general', 'Contentor indiferenciado'],
            ['waste', 'recycling_island', 'Ecoponto'],
            ['waste', 'underground', 'Contentor subterrâneo'],
        ],
    ];

    public static function legend()
    {
        return array_map(
            fn ($items) => array_map(fn ($item) => [
                'label' => $item[2],
                'icon' => self::setIcon($item[0], $item[1]),
            ], $items),
            self::LEGEND
        );
    }

    // REGRAS
    public static function setIcon($category, $type, $subtype = null)
    {
        switch ($type) {
            // SINAIS
            case 'speed_limit':
                if ($category === 'sign') {
                    if ($subtype) {
                        return URL::asset(
                            'build/resources/imagens/icons/' . $subtype . '_km.png'
                        );
                    }

                    return URL::asset(
                        'build/resources/imagens/icons/limite-de-velocidade.png'
                    );
                }
                break;

            case 'stop':
                if ($category === 'sign') {
                    return URL::asset(
                        'build/resources/imagens/icons/stop.png'
                    );
                }
                break;

            case 'yield':
                if ($category === 'sign') {
                    return URL::asset(
                        'build/resources/imagens/icons/cedencia-passagem.png'
                    );
                }
                break;

            // LUZES
            case 'street_pole':
                if ($category === 'light') {
                    return URL::asset(
                        'build/resources/imagens/icons/poste-de-iluminacao.png'
                    );
                }
                break;

            case 'street_lamp':
                if ($category === 'light') {
                    return URL::asset(
                        'build/resources/imagens/icons/luz.png'
                    );
                }
                break;

            // LIXOS
            case 'general':
                if ($category === 'waste') {
                    if ($subtype) {
                        return URL::asset(
                            'build/resources/imagens/icons/' . $subtype . '-trash.png'
                        );
                    } else {
                        return URL::asset(
                            'build/resources/imagens/icons/caixote-de-lixo.png'
                        );
                    }
                }
                break;

            case 'recycling_island':
                if ($category === 'waste') {
                    return URL::asset(
                        'build/resources/imagens/icons/ecoponto.png'
                    );
                }
                break;

            case 'underground':
                if ($category === 'waste') {
                    return URL::asset(
                        'build/resources/imagens/icons/underground_trash.png'
                    );
                }
                break;
        }

        return null;
    }

    // A API devolve image_url relativo ("/media/..."): junta o endereço da API
    public static function mediaUrl($path)
    {
        if (! $path || str_starts_with($path, 'http')) {
            return $path;
        }

        $api = parse_url(env('API_URL'));

        return $api['scheme'] . '://' . $api['host'] . (isset($api['port']) ? ':' . $api['port'] : '') . $path;
    }
}
