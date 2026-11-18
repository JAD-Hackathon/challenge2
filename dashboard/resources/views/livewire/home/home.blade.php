@section('title', 'Home')
<div>
    <style>
        .home-header {
            width: 100%;
            padding: 56px 16px 48px;
            text-align: center;
            background: linear-gradient(135deg, #0b1f4d 0%, #1b48a1 55%, #3b8beb 100%);
            color: #fff;
            box-shadow: 0 4px 18px rgba(11, 31, 77, .3);
        }

        .home-title {
            margin: 0;
            font-size: clamp(2.2rem, 6vw, 4rem);
            font-weight: 800;
            letter-spacing: 1px;
            text-transform: uppercase;
            text-shadow: 0 3px 10px rgba(0, 0, 0, .25);
        }

        .home-subtitle {
            margin: 12px 0 0;
            font-size: clamp(1rem, 2.2vw, 1.3rem);
            font-weight: 400;
            letter-spacing: 3px;
            text-transform: uppercase;
            opacity: .9;
        }

        .home-subtitle::before,
        .home-subtitle::after {
            content: "";
            display: inline-block;
            width: 40px;
            height: 2px;
            margin: 0 14px;
            vertical-align: middle;
            background: rgba(255, 255, 255, .7);
        }

        .home-nav {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 12px;
            padding: 24px 16px;
        }

        .home-nav-btn {
            min-width: 200px;
            padding: 12px 28px;
            border: 2px solid #1b48a1;
            border-radius: 999px;
            background: #fff;
            color: #1b48a1;
            font-weight: 600;
            font-size: 1rem;
            letter-spacing: .3px;
            box-shadow: 0 2px 6px rgba(0, 0, 0, .08);
            transition: background-color .2s, color .2s, transform .15s, box-shadow .2s;
        }

        .home-nav-btn:hover {
            background: #e8effb;
            transform: translateY(-2px);
            box-shadow: 0 6px 14px rgba(27, 72, 161, .2);
        }

        .home-nav-btn:focus-visible {
            outline: 3px solid rgba(27, 72, 161, .4);
            outline-offset: 2px;
        }

        .home-nav-btn.active {
            background: #1b48a1;
            color: #fff;
            box-shadow: 0 6px 14px rgba(27, 72, 161, .35);
        }

        @media (max-width: 576px) {
            .home-nav-btn {
                flex: 1 1 100%;
                min-width: 0;
            }
        }
    </style>

    <header class="home-header">
        <h1 class="home-title">Challenge 2</h1>
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

    <div class="container py-4">
        @if ($aba == '1')
            <h1>Aqui pode encontrar tudo o que já assinalamos!</h1>


            <div class="row">

                <div class="col-10">
                    <div id="map" data-points='@json($points)' style="height: 400px; width: 100%;" wire:ignore></div>

                </div>
                <div class="col-2">
                    <div class="card">
                        <div class="card-header">
                            Legenda:
                        </div>

                        <div class="card-body">
                            <ul class="list-unstyled mb-0">

                                <li class="mb-2">
                                    <i class="bi bi-signpost-2 me-2"></i>
                                    Sinalização
                                </li>

                                <li class="mb-2">
                                    <i class="bi bi-stoplights me-2"></i>
                                    Semáforo
                                </li>

                                <li class="mb-2">
                                    <i class="bi bi-lamp me-2"></i>
                                    Candeeiro
                                </li>

                                <li class="mb-2">
                                    <span style="color: blue;">●</span>
                                    Ponto de interesse
                                </li>

                                <li class="mb-2">
                                    <span style="color: red;">●</span>
                                    Elemento detetado
                                </li>

                            </ul>
                        </div>
                    </div>
                </div>

            </div>
        @elseif ($aba == '2')
            <h1>Aqui podes colocar uma foto/video e o vamos-te dizer onde é e o que aparece!</h1>

            <form>
                <div class="row">
                    <div class="col-4">
                        <label for="fileInput" class="form-label">Escolha um ficheiro (imagem ou vídeo):</label>
                        <input class="form-control" type="file" id="fileInput" wire:model="file" mimes="jpg,jpeg,png,mp4">
                        @error('file')
                            <span class="text-danger">{{ $message }}</span>
                        @enderror
                        <button type="button" class="btn btn-primary mt-4" wire:click="processFile">Enviar</button>

                    </div>
                </div>
            </form>

            {{-- @if ($file)
                <div class="mt-4">
                    <h5>Pré-visualização do ficheiro:</h5>
                    @if (in_array($file->getClientOriginalExtension(), ['jpg', 'jpeg', 'png', 'gif']))
                        <img src="{{ $file->temporaryUrl() }}" alt="Pré-visualização da imagem" class="img-fluid">
                    @elseif (in_array($file->getClientOriginalExtension(), ['mp4', 'mov', 'avi']))
                        <video controls class="img-fluid">
                            <source src="{{ $file->temporaryUrl() }}" type="video/mp4">
                            O seu navegador não suporta a reprodução de vídeos.
                        </video>
                    @else
                        <p>Tipo de ficheiro não suportado para pré-visualização.</p>
                    @endif
                </div>
            @endif --}}
        @elseif ($aba == '3')
            <h1>Catálogo</h1>
            <p>Este é o conteúdo da aba 3.</p>
        @endif
    </div>
</div>

@push('scripts')
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

    <style>
        .map-icon {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 32px;
            height: 32px;
            border: 2px solid #fff;
            border-radius: 50%;
            color: #fff;
            font-size: 16px;
            box-shadow: 0 2px 6px rgba(0, 0, 0, .35);
        }

        .map-dot {
            width: 16px;
            height: 16px;
            border: 2px solid #fff;
            border-radius: 50%;
            box-shadow: 0 1px 4px rgba(0, 0, 0, .4);
        }
    </style>

    <script>
        let map = null;

        // Ícone a partir de uma imagem (URL vindo do PHP)
        function imageIcon(url) {
            return L.icon({
                iconUrl: url,
                iconSize: [24, 24],    // tamanho no mapa
                iconAnchor: [16, 32],  // ponto da imagem que fica na coordenada (base ao centro)
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
                const marker = p.icon
                    ? L.marker([p.lat, p.lng], { icon: imageIcon(p.icon) })
                    : L.marker([p.lat, p.lng]);
                marker.addTo(map).bindPopup(p.name);
            });

            if (points.length > 1) {
                map.fitBounds(points.map((p) => [p.lat, p.lng]), { padding: [30, 30] });
            }
        }

        initMap();

        Livewire.hook('commit', ({ succeed }) => {
            succeed(() => requestAnimationFrame(initMap));
        });
    </script>
@endpush