<div>
    @include('livewire.home.partials.alerts')

    <h1>Aqui pode encontrar tudo o que já assinalamos!</h1>
    <a wire:click="exportGeoJSON" class="btn btn-primary mb-3">Exportar GeoJSON</a>
    <a wire:click="exportCSV" class="btn btn-secondary mb-3">Exportar CSV</a>
    @php
        $byCategory = array_count_values(array_column($points, 'category'));
        $stats = [
            [
                'label' => 'Elementos assinalados',
                'value' => count($points),
                'icon' => 'bi-geo-alt-fill',
                'color' => '#1b48a1',
            ],
            [
                'label' => 'Sinalização',
                'value' => $byCategory['sign'] ?? 0,
                'icon' => 'bi-sign-stop-fill',
                'color' => '#d63939',
            ],
            [
                'label' => 'Iluminação',
                'value' => $byCategory['light'] ?? 0,
                'icon' => 'bi-lightbulb-fill',
                'color' => '#e0a800',
            ],
            [
                'label' => 'Resíduos',
                'value' => $byCategory['waste'] ?? 0,
                'icon' => 'bi-trash3-fill',
                'color' => '#2f9e44',
            ],
        ];
    @endphp

    <div class="row g-3 my-3">
        @foreach ($stats as $stat)
            <div class="col-6 col-lg-3">
                <div class="stat-card" style="--stat-color: {{ $stat['color'] }}">
                    <div class="stat-icon">
                        <i class="bi {{ $stat['icon'] }}"></i>
                    </div>
                    <div>
                        <div class="stat-value">{{ $stat['value'] }}</div>
                        <div class="stat-label">{{ $stat['label'] }}</div>
                    </div>
                </div>
            </div>
        @endforeach
    </div>



    <div class="row g-3">

        <div class="col-12 col-lg-10">
            <div id="map" class="map-canvas" data-points='@json($points)' wire:ignore>
            </div>

        </div>
        <div class="col-12 col-lg-2">
            <div class="card">
                <div class="card-header">
                    Legenda:
                </div>

                <div class="card-body map-legend">
                    @foreach ($legend as $group => $items)
                        <div>
                            <h6 class="legend-group">{{ $group }}</h6>
                            <ul class="list-unstyled mb-3">
                                @foreach ($items as $item)
                                    <li class="legend-item">
                                        <img src="{{ $item['icon'] }}" alt="" class="legend-icon">
                                        {{ $item['label'] }}
                                    </li>
                                @endforeach
                            </ul>
                        </div>
                    @endforeach
                </div>
            </div>
        </div>

    </div>
</div>
