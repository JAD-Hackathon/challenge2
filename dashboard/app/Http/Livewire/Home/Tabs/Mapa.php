<?php

namespace App\Http\Livewire\Home\Tabs;

use App\Http\Controllers\API;
use App\Support\Elementos;
use Livewire\Component;

// Separador "Página Inicial": estatísticas, mapa, legenda e exportação
class Mapa extends Component
{
    public $points = [];

    public function mount()
    {
        $elements = API::getData('elements');

        if (isset($elements['error'])) {
            session()->now('error', "Não foi possível carregar os elementos: {$elements['error']}");
            $elements = [];
        }

        $this->points = array_map(fn ($element) => [
            'id' => $element['id'],
            'lat' => (float) $element['latitude'],
            'lng' => (float) $element['longitude'],
            'name' => $element['name'],
            'category' => $element['category'],
            'icon' => Elementos::setIcon($element['category'], $element['type']),
        ], $elements);
    }

    public function exportGeoJSON($table = 'elements')
    {
        $geojson = API::getFile("export/{$table}.geojson");

        if ($geojson === null) {
            session()->flash('error', 'Não foi possível exportar o GeoJSON.');
            return;
        }

        return response()->streamDownload(
            fn () => print($geojson),
            "{$table}.geojson",
            ['Content-Type' => 'application/geo+json'],
        );
    }

    public function exportCSV($table = 'elements')
    {
        $csv = API::getFile("export/{$table}.csv");

        if ($csv === null) {
            session()->flash('error', 'Não foi possível exportar o CSV.');
            return;
        }

        return response()->streamDownload(
            fn () => print($csv),
            "{$table}.csv",
            ['Content-Type' => 'text/csv'],
        );
    }

    public function render()
    {
        return view('livewire.home.tabs.mapa', [
            'legend' => Elementos::legend(),
        ]);
    }
}
