<?php

namespace App\Http\Livewire\Home;

use Livewire\Component;

// Página principal: cabeçalho + navegação entre separadores.
// Cada separador é um componente em Tabs/ (Mapa, Experimenta, Catalogo).
class Home extends Component
{
    public $aba = '1';

    public function mount()
    {
        $this->aba = request()->query('aba', '1');
    }

    public function changeAba($aba)
    {
        $this->aba = $aba;
    }

    public function render()
    {
        return view('livewire.home.home')->extends('layouts.app');
    }
}
