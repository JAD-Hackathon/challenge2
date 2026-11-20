<?php

namespace App\Support;

use Illuminate\Support\Facades\URL;

// Coisas dos elementos usadas em vários separadores (mapa, experimenta, catálogo)
class Elementos
{
    // Tipos que a API aceita ("categoria.tipo" => nome). Igual a api/app/core/taxonomy.py
    // Nomes em português das categorias, atributos e valores que a API devolve em inglês
    const CATEGORIES = [
        'sign' => 'Sinalização',
        'light' => 'Iluminação',
        'waste' => 'Resíduos',
    ];

    const ATTRIBUTES = [
        'limit' => 'Limite',
        'color' => 'Cor',
        'subtype' => 'Subtipo',
        'material' => 'Material',
        'condition' => 'Estado',
    ];

    const VALUES = [
        'blue' => 'Azul',
        'green' => 'Verde',
        'yellow' => 'Amarelo',
        'grey' => 'Cinzento',
        'gray' => 'Cinzento',
        'brown' => 'Castanho',
        'red' => 'Vermelho',
        'black' => 'Preto',
        'white' => 'Branco',
    ];

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
            ['sign', 'other', 'Outros Sinais']
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
    // Ícone de cada tipo; se não houver ícone para o tipo (ou o ficheiro não existir), usa sign.png
    public static function setIcon($category, $type, $subtype = null)
    {
        $file = match ("{$category}.{$type}") {
            // SINAIS
            'sign.speed_limit' => $subtype ? "{$subtype}_km.png" : 'limite-de-velocidade.png',
            'sign.stop' => 'stop.png',
            'sign.yield' => 'cedencia-passagem.png',
            'sign.other' => 'outros-sinais.png',
            // LUZES
            'light.street_pole' => 'poste-de-iluminacao.png',
            'light.street_lamp' => 'luz.png',
            // LIXOS
            'waste.general' => $subtype ? "{$subtype}_trash.png" : 'caixote-de-lixo.png',
            'waste.recycling_island' => 'ecoponto.png',
            'waste.underground' => 'underground_trash.png',
            default => null,
        };

        return self::iconUrl($file);
    }

    // ICON URL
    private static function iconUrl(?string $file): string
    {
        if (! $file || ! is_file(resource_path("imagens/icons/{$file}"))) {
            $file = 'sign.png';
        }

        return URL::asset("build/resources/imagens/icons/{$file}");
    }

    public static function categoryLabel($category)
    {
        return self::CATEGORIES[$category] ?? ucfirst((string) $category);
    }

    // "light.street_pole" (ou categoria + tipo) -> "Poste de luz"
    public static function typeLabel($category, $type = null)
    {
        $key = $type === null ? $category : "{$category}.{$type}";

        return self::TYPES[$key] ?? ucfirst(str_replace(['.', '_'], [' / ', ' '], (string) $key));
    }

    public static function attributeLabel($key)
    {
        return self::ATTRIBUTES[$key] ?? ucfirst(str_replace('_', ' ', (string) $key));
    }

    public static function attributeValue($key, $value)
    {
        if ($key === 'limit') {
            return "{$value} km/h";
        }
        if (is_array($value)) {
            return implode(', ', array_map(fn ($v) => self::VALUES[$v] ?? $v, $value));
        }
        if (is_bool($value)) {
            return $value ? 'Sim' : 'Não';
        }

        return self::VALUES[$value] ?? $value;
    }

    // COR BOUNDING BOXUU8
    public static function boxColor($category)
    {
        return [
            'sign' => '#dc3545',
            'light' => '#ffc107',
            'waste' => '#198754',
        ][$category] ?? '#0d6efd';
    }

    // DEVOLVER O LINK DA IMAGEM
    public static function mediaUrl($path)
    {
        if (! $path) {
            return $path;
        }

        if (str_starts_with($path, 'http')) {
            $internal = parse_url(env('API_URL'));
            $url = parse_url($path);
            if (($url['host'] ?? null) !== ($internal['host'] ?? null)) {
                return $path;
            }
            $path = ($url['path'] ?? '') . (isset($url['query']) ? '?' . $url['query'] : '');
        }

        $api = parse_url(env('API_PUBLIC_URL', env('API_URL')));

        return $api['scheme'] . '://' . $api['host'] . (isset($api['port']) ? ':' . $api['port'] : '') . $path;
    }
}
