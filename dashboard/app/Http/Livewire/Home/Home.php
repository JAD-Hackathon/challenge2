<?php

namespace App\Http\Livewire\Home;

use Livewire\Component;
use Livewire\WithFileUploads;

class Home extends Component
{
    use WithFileUploads;

    public $aba = '1';

    // EXEMPLO DE PONTOS NO MAPA
    public $points = [
        ['lat' => 40.6405, 'lng' => -8.6538, 'name' => 'Centro de Aveiro', 'type' => 'sinalizacao'],
        ['lat' => 40.6303, 'lng' => -8.6575, 'name' => 'Universidade de Aveiro', 'type' => 'semaforo'],
        ['lat' => 40.6412, 'lng' => -8.6510, 'name' => 'Semáforo Av. Lourenço Peixinho', 'type' => 'semaforo'],
        ['lat' => 40.6390, 'lng' => -8.6560, 'name' => 'Sinal de STOP', 'type' => 'sinalizacao'],
        ['lat' => 40.6420, 'lng' => -8.6575, 'name' => 'Candeeiro', 'type' => 'candeeiro'],
        ['lat' => 40.6375, 'lng' => -8.6520, 'name' => 'Elemento detetado', 'type' => 'sinalizacao'],
    ];

    public $file;

    public function mount()
    {
        $this->aba = request()->query('aba', '1');
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
