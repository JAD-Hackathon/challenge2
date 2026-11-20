@section('title', 'Home')
<div>
    @include('layouts.css')
    <header class="home-header">
        <div class="home-auth">
            @if (session('login'))
                <span class="home-auth-user"><i class="bi bi-person-circle"></i> {{ session('login.user') }}</span>
                <button type="button" class="btn btn-sm btn-outline-light" wire:click="logout">Sair</button>
            @else
                <button type="button" class="btn btn-sm btn-light" wire:click="openLogin">
                    <i class="bi bi-box-arrow-in-right"></i> Login
                </button>
            @endif
        </div>

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

    {{-- MODAL: login (aberto com $showLogin) --}}
    @if ($showLogin)
        <div class="modal fade show d-block" tabindex="-1" role="dialog" aria-modal="true"
            aria-labelledby="loginTitle" wire:keydown.escape.window="closeLogin">
            <div class="modal-dialog modal-dialog-centered">
                <form class="modal-content" wire:submit="login">
                    <div class="modal-header">
                        <h5 class="modal-title" id="loginTitle">Iniciar sessão</h5>
                        <button type="button" class="btn-close" aria-label="Fechar" wire:click="closeLogin"></button>
                    </div>

                    <div class="modal-body">
                        <div class="mb-3">
                            <label for="loginEmail" class="form-label">Email</label>
                            <input type="email" id="loginEmail" class="form-control @error('email') is-invalid @enderror"
                                wire:model="email" autocomplete="username" autofocus>
                            @error('email')
                                <div class="invalid-feedback">{{ $message }}</div>
                            @enderror
                        </div>

                        <div class="mb-3">
                            <label for="loginPassword" class="form-label">Palavra-passe</label>
                            <input type="password" id="loginPassword"
                                class="form-control @error('password') is-invalid @enderror" wire:model="password"
                                autocomplete="current-password">
                            @error('password')
                                <div class="invalid-feedback">{{ $message }}</div>
                            @enderror
                        </div>
                    </div>

                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" wire:click="closeLogin">Cancelar</button>
                        <button type="submit" class="btn btn-primary" wire:loading.attr="disabled" wire:target="login">
                            <span wire:loading wire:target="login" class="spinner-border spinner-border-sm me-1"
                                aria-hidden="true"></span>
                            Entrar
                        </button>
                    </div>
                </form>
            </div>
        </div>
        <div class="modal-backdrop fade show" wire:click="closeLogin"></div>
    @endif

    @php 

        $session = session('login')

    @endphp 

    {{ $session }}
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

        window.openPhotoLightbox = function (src, boxes = []) {
            const overlay = document.createElement('div');
            overlay.className = 'photo-lightbox';
            overlay.setAttribute('role', 'dialog');
            overlay.setAttribute('aria-modal', 'true');

            const frame = document.createElement('div');
            frame.className = 'photo-lightbox-frame';

            const img = document.createElement('img');
            img.src = src;
            img.alt = 'Foto em tamanho grande';
            frame.appendChild(img);

            img.addEventListener('load', () => {
                const w = img.naturalWidth, h = img.naturalHeight;
                boxes.forEach((b) => {
                    const [x1, y1, x2, y2] = b.bbox;
                    const box = document.createElement('div');
                    box.className = 'photo-lightbox-box';
                    Object.assign(box.style, {
                        left: `${x1 / w * 100}%`,
                        top: `${y1 / h * 100}%`,
                        width: `${(x2 - x1) / w * 100}%`,
                        height: `${(y2 - y1) / h * 100}%`,
                        borderColor: b.color || '#0d6efd',
                    });
                    if (b.label) {
                        const label = document.createElement('span');
                        label.textContent = b.label;
                        label.style.background = b.color || '#0d6efd';
                        box.appendChild(label);
                    }
                    frame.appendChild(box);
                });
            });

            const close = document.createElement('button');
            close.type = 'button';
            close.className = 'btn-close btn-close-white photo-lightbox-close';
            close.setAttribute('aria-label', 'Fechar');

            const onKey = (e) => e.key === 'Escape' && remove();
            const remove = () => {
                overlay.remove();
                document.removeEventListener('keydown', onKey);
            };
            overlay.addEventListener('click', (e) => (e.target === overlay || e.target === close) && remove());
            document.addEventListener('keydown', onKey);

            overlay.append(frame, close);
            document.body.appendChild(overlay);
            close.focus();
        };

        // Popup do marcador: nome, localização e foto onde foi identificado (com a caixa do elemento)
        function buildPopup(p, marker) {
            const root = document.createElement('div');
            root.className = 'map-popup';

            const title = document.createElement('strong');
            title.textContent = p.name;
            root.appendChild(title);

            const coords = `${p.lat.toFixed(6)}, ${p.lng.toFixed(6)}`;
            const location = document.createElement('div');
            location.className = 'map-popup-coords';
            location.innerHTML = '<i class="bi bi-geo-alt"></i> ';
            const link = document.createElement('a');
            link.href = `https://www.google.com/maps?q=${p.lat},${p.lng}`;
            link.target = '_blank';
            link.rel = 'noopener';
            link.textContent = coords;
            // Abre sempre num separador novo (o target sozinho não chega dentro do popup do Leaflet)
            link.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                window.open(link.href, '_blank', 'noopener,noreferrer');
            });
            location.appendChild(link);
            root.appendChild(location);

            if (p.image_url) {
                const photo = document.createElement('div');
                photo.className = 'map-popup-photo';

                const img = document.createElement('img');
                img.src = p.image_url;
                img.alt = `Foto onde foi identificado: ${p.name}`;
                photo.appendChild(img);

                // bbox_xyxy está em píxeis da foto: converte para % quando se sabe o tamanho real
                if (p.bbox) {
                    const box = document.createElement('div');
                    box.className = 'map-popup-box';
                    box.style.borderColor = p.color;
                    photo.appendChild(box);

                    img.addEventListener('load', () => {
                        const [x1, y1, x2, y2] = p.bbox;
                        const w = img.naturalWidth, h = img.naturalHeight;
                        Object.assign(box.style, {
                            left: `${x1 / w * 100}%`,
                            top: `${y1 / h * 100}%`,
                            width: `${(x2 - x1) / w * 100}%`,
                            height: `${(y2 - y1) / h * 100}%`,
                            display: 'block',
                        });
                        marker.getPopup()?.update(); // reajusta o popup à altura da foto
                    });
                }

                img.addEventListener('error', () => photo.remove());

                // Clicar na foto: abre em grande com a bounding box
                photo.title = 'Clique para ver em grande';
                photo.style.cursor = 'zoom-in';
                photo.addEventListener('click', () => openPhotoLightbox(p.image_url,
                    p.bbox ? [{ bbox: p.bbox, label: p.name, color: p.color }] : []));
                root.appendChild(photo);

                if (p.attribution) {
                    const credit = document.createElement('div');
                    credit.className = 'map-popup-credit';
                    credit.textContent = p.attribution;
                    root.appendChild(credit);
                }
            }

            return root;
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
                // Sem ícone atribuído: usa o sign.png
                const marker = L.marker([p.lat, p.lng], {
                    icon: imageIcon(p.icon || @js(asset('build/resources/imagens/icons/outros-sinais.png')))
                });
                // Conteúdo criado só uma vez: o popup.update() volta a chamar esta função e, sem cache,
                // recriava a foto a cada load (ciclo infinito; o clique caía numa foto já removida)
                let content = null;
                marker.addTo(map).bindPopup(() => (content ??= buildPopup(p, marker)), {
                    minWidth: 260,
                    maxWidth: 320,
                });
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
