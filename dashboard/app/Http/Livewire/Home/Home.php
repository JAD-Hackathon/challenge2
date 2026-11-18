<?php

namespace App\Http\Livewire\Home;

use App\Http\Controllers\API;
use Illuminate\Support\Facades\URL;
use Livewire\Component;
use Livewire\WithFileUploads;

class Home extends Component
{
    use WithFileUploads;

    public $aba = '1';

    public $file;
    public $points = [];

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
                    return URL::asset(
                        'build/resources/imagens/icons/caixote-lixo.png'
                    );
                }
                break;

            case 'recycling_island':
                if ($category === 'waste') {
                    return URL::asset(
                        'build/resources/imagens/icons/lixos-variados.png'
                    );
                }
                break;

            case 'underground':
                if ($category === 'waste') {
                    return URL::asset(
                        'build/resources/imagens/icons/caixote-de-lixo.png'
                    );
                }
                break;
        }

        return null;
    }

    public function mount()
    {
        $this->aba = request()->query('aba', '1');

        // dd(API::getData('elements'));

        $this->points = array_map(fn ($element) => [
            'lat' => (float) $element['latitude'],
            'lng' => (float) $element['longitude'],
            'name' => $element['name'],
            'category' => $element['category'],
            'icon' => self::setIcon($element['category'],$element['type']),
        ], API::getData('elements'));

    }

    public function changeAba($aba)
    {
        $this->aba = $aba;
    }

    public function processFile()
    {
        $this->validate([
            'file' => 'required|mimes:.mp4,.jpg,.png,.jpeg|max:1024', // 1MB Max
        ],
        [
            'file.required' => 'Selecione um arquivo para upload.',
            'file.mimes' => 'Apenas arquivos MP4, JPG, PNG e JPEG são permitidos.',
            'file.max' => 'O tamanho do arquivo não deve exceder 1MB.',
        ]);

        
        session()->flash('message', 'File uploaded successfully!');
    }

    public function ex

    public function render()
    {
        return view('livewire.home.home', [
            'legend' => self::legend(),
        ])->extends('layouts.app');
    }
}
