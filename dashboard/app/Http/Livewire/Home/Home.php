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

    // REGRAS 
    public static function setIcon($type, $subtype = null)
    {
        switch ($type) {
            case 'speed_limit':
                if ($subtype === '30') {
                    return URL::asset('build/resources/imagens/icons/limite-de-velocidade-30.png');
                } elseif ($subtype === '50') {
                    return URL::asset('build/resources/imagens/icons/limite-de-velocidade-50.png');
                } elseif ($subtype === '60') {
                    return URL::asset('build/resources/imagens/icons/limite-de-velocidade-60.png');
                } elseif ($subtype === '70') {
                    return URL::asset('build/resources/imagens/icons/limite-de-velocidade-70.png');
                } elseif ($subtype === '80') {
                    return URL::asset('build/resources/imagens/icons/limite-de-velocidade-80.png');
                } elseif ($subtype === '90') {
                    return URL::asset('build/resources/imagens/icons/limite-de-velocidade-90.png');
                } elseif ($subtype === '100') {
                    return URL::asset('build/resources/imagens/icons/limite-de-velocidade-100.png');
                } elseif ($subtype === '110') {
                    return URL::asset('build/resources/imagens/icons/limite-de-velocidade-110.png');
                } else {
                    return URL::asset('build/resources/imagens/icons/limite-de-velocidade.png');
                }
            case 'stop':
                return URL::asset('build/resources/imagens/icons/stop.png');
            case 'yield':
                return URL::asset('build/resources/imagens/icons/cedencia-passagem.png');
            case 'street_pole':
                return URL::asset('build/resources/imagens/icons/luz.png');
            case 'traffic_light':
                return URL::asset('build/resources/imagens/icons/semaforo.png');
            ## LIXOS
            case 'general':
                return URL::asset('build/resources/imagens/icons/caixote-lixo.png');
            case 'recycling_island':
                return URL::asset('build/resources/imagens/icons/lixos-variados.png');
            case 'underground':
                return URL::asset('build/resources/imagens/icons/caixa-de-lixo.png');
            default:
                return null;
        }
    }

    public function mount()
    {
        $this->aba = request()->query('aba', '1');

        // dd(API::getData('elements'));

        $this->points = array_map(fn ($element) => [
            'lat' => (float) $element['latitude'],
            'lng' => (float) $element['longitude'],
            'name' => $element['name'],
            'type' => 'sinalizacao',
            'icon' => self::setIcon($element['type']),
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

    public function render()
    {
        return view('livewire.home.home')->extends('layouts.app');
    }
}
