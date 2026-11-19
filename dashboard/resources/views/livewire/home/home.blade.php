@section('title', 'Home')
<div>
    @include('layouts.css')
    <header class="home-header">
        <h1 class="home-title">Desafio 2</h1>
        <p class="home-subtitle">Hackathon Aveiro 2026</p>
    </header>

    <nav class="home-nav">
        <button type="button" class="home-nav-btn {{ $aba == '1' ? 'active' : '' }}" wire:click="changeAba('1')">Página
            Inicial</button>
        <button type="button" class="home-nav-btn {{ $aba == '2' ? 'active' : '' }}"
            wire:click="changeAba('2')">Experimenta</button>
        <button type="button" class="home-nav-btn {{ $aba == '3' ? 'active' : '' }}"
            wire:click="changeAba('3')">Catálogo</button>
    </nav>

    {{-- Cada separador é um componente: app/Http/Livewire/Home/Tabs/*.php --}}
    <div class="container py-4">
        @if ($aba == '1')
            <livewire:home.tabs.mapa key="tab-mapa" />
        @elseif ($aba == '2')
            <livewire:home.tabs.experimenta key="tab-experimenta" />
        @elseif ($aba == '3')
            <livewire:home.tabs.catalogo key="tab-catalogo" />
        @endif
    </div>
</div>

{{-- Script do mapa: fica aqui para estar sempre carregado, seja qual for o separador inicial --}}
@push('scripts')

    <script>
        let map = null;

        function imageIcon(url) {
            return L.icon({
                iconUrl: url,
                iconSize: [24, 24], // tamanho no mapa
                iconAnchor: [16, 32], // ponto da imagem que fica na coordenada (base ao centro)
                popupAnchor: [0, -32], // popup abre por cima do ícone
            });
        }

        function initMap() {
            const el = document.getElementById('map');

            if (!el) {
                if (map) {
                    map.remove();
                    map = null;
                }
                return;
            }

            if (map && map.getContainer() === el) return;

            if (map) map.remove();

            // INICIO MAPA -> CENTRO AVEIRO
            map = L.map(el).setView([40.6405, -8.6538], 14);

            L.tileLayer(
                'https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png?key={{ config('services.carto.key') }}', {
                    attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
                    maxNativeZoom: 18,
                    maxZoom: 20,
                },
            ).addTo(map);

            // Pontos vindos do PHP ($points no Home.php)
            const points = JSON.parse(el.dataset.points || '[]');
            points.forEach((p) => {
                const marker = p.icon ?
                    L.marker([p.lat, p.lng], {
                        icon: imageIcon(p.icon)
                    }) :
                    L.marker([p.lat, p.lng]);
                marker.addTo(map).bindPopup(p.name);
            });

            if (points.length > 1) {
                map.fitBounds(points.map((p) => [p.lat, p.lng]), {
                    padding: [30, 30]
                });
            }
        }

        initMap();

        Livewire.hook('commit', ({
            succeed
        }) => {
            succeed(() => requestAnimationFrame(initMap));
        });
    </script>
@endpush
