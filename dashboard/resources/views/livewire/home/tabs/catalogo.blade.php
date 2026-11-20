<div>
    @include('livewire.home.partials.alerts')

    <h1>Catálogo</h1>

    <button type="button" wire:click="toggleMonitor"
        class="btn {{ $souMonitor ? 'btn-danger' : 'btn-primary' }}">Sou Monitor</button>

    <div class="row g-3 mt-2">
        {{-- SIDEBAR: lista com scroll próprio --}}
        <div class="col-md-5 col-lg-4">
            <div class="catalog-sidebar">
                @php $filtered = $this->filtered; @endphp
                <div class="catalog-sidebar-header">
                    Elementos
                    <span class="badge text-bg-primary rounded-pill">
                        {{ count($filtered) }}@if (count($filtered) !== count($elementos ?? [])) / {{ count($elementos) }}@endif
                    </span>
                </div>

                {{-- FILTROS --}}
                <div class="catalog-filters">
                    <div class="input-group input-group-sm mb-2">
                        <span class="input-group-text"><i class="bi bi-search"></i></span>
                        <input type="search" class="form-control" placeholder="Pesquisar por nome…"
                            wire:model.live.debounce.300ms="search">
                    </div>

                    <div class="row g-2 mb-2">
                        <div class="col-6">
                            <select class="form-select form-select-sm" wire:model.live="filterCategory" aria-label="Categoria">
                                <option value="">Todas as categorias</option>
                                <option value="sign">Sinais</option>
                                <option value="light">Iluminação</option>
                                <option value="waste">Resíduos</option>
                            </select>
                        </div>
                        <div class="col-6">
                            <select class="form-select form-select-sm" wire:model.live="filterStatus" aria-label="Estado">
                                <option value="">Todos os estados</option>
                                <option value="auto">Por rever</option>
                                <option value="verified">Verificados</option>
                                <option value="corrected">Corrigidos</option>
                            </select>
                        </div>
                    </div>

                    <label class="form-label small d-flex justify-content-between mb-0">
                        <span>Confiança até</span>
                        <strong>{{ $maxConfidence }}%</strong>
                    </label>
                    <input type="range" class="form-range" min="0" max="100" step="5"
                        wire:model.live.debounce.150ms="maxConfidence">

                    <div class="d-flex gap-2 align-items-center">
                        <select class="form-select form-select-sm" wire:model.live="sort" aria-label="Ordenar">
                            <option value="confidence_asc">Menor confiança primeiro</option>
                            <option value="confidence_desc">Maior confiança primeiro</option>
                            <option value="name">Nome (A–Z)</option>
                        </select>
                        <button type="button" class="btn btn-sm btn-outline-warning text-nowrap" wire:click="filterToReview"
                            title="Por rever, menor confiança primeiro">
                            <i class="bi bi-funnel"></i> Rever
                        </button>
                        <button type="button" class="btn btn-sm btn-outline-secondary" wire:click="clearFilters"
                            title="Limpar filtros" aria-label="Limpar filtros">
                            <i class="bi bi-x-lg"></i>
                        </button>
                    </div>
                </div>

                <div class="catalog-sidebar-list" wire:loading.class="opacity-50"
                    wire:target="search,filterCategory,filterStatus,maxConfidence,sort,filterToReview,clearFilters">
                    @forelse ($filtered as $item)
                        @php $selected = ($selectedElement['id'] ?? null) === $item['id']; @endphp
                        <button type="button" wire:key="el-{{ $item['id'] }}"
                            class="catalog-item {{ $selected ? 'active' : '' }}"
                            wire:click="selectElement('{{ Crypt::encrypt($item['id']) }}')">
                            @php $icon = \App\Support\Elementos::setIcon($item['category'], $item['type']); @endphp
                            @if ($icon)
                                <img src="{{ $icon }}" alt="" class="legend-icon">
                            @else
                                <i class="bi bi-geo-alt legend-icon text-center"></i>
                            @endif

                            <span class="catalog-item-text">
                                <span class="catalog-item-name">{{ $item['name'] }}</span>
                                <span class="catalog-item-confidence">
                                    <span class="confidence-bar">
                                        <span style="width: {{ round($item['confidence'] * 100) }}%"></span>
                                    </span>
                                    {{ round($item['confidence'] * 100) }}%
                                </span>
                            </span>
                        </button>
                    @empty
                        <p class="text-muted p-3 mb-0">
                            {{ count($elementos ?? []) ? 'Nenhum elemento corresponde aos filtros.' : 'Ainda não há elementos.' }}
                        </p>
                    @endforelse
                </div>
            </div>
        </div>

        {{-- DETALHE: fica fixo ao descer a página --}}
        <div class="col-md-7 col-lg-8 catalog-detail">
            <div wire:loading wire:target="selectElement" class="text-muted">A carregar...</div>

            @if ($selectedElement)
                @php
                    $el = $selectedElement;
                    $statusLabels = [
                        'auto' => ['Detetado automaticamente', 'secondary'],
                        'verified' => ['Verificado', 'success'],
                        'corrected' => ['Corrigido', 'info'],
                        'rejected' => ['Rejeitado', 'danger'],
                    ];
                    [$statusText, $statusColor] = $statusLabels[$el['status']] ?? [$el['status'], 'secondary'];
                @endphp

                <div class="card element-detail" wire:loading.class="opacity-50" wire:target="selectElement">
                    <div class="card-header d-flex align-items-center gap-2">
                        @if ($el['icon'])
                            <img src="{{ $el['icon'] }}" alt="" class="legend-icon">
                        @endif
                        <strong class="flex-grow-1">{{ $el['name'] }}</strong>
                        <button type="button" class="btn-close" aria-label="Fechar"
                            wire:click="closeElement"></button>


                    </div>
                    @if ($souMonitor && ! in_array($el['status'], ['verified', 'corrected']))

                        <div class="d-flex gap-2 p-2 border-bottom">
                            <button type="button" class="btn btn-outline-primary btn-sm flex-fill"
                                wire:click="startEdit" @disabled($editing)>
                                <i class="bi bi-pencil me-1"></i> Mudar informações
                            </button>
                            <button type="button" class="btn btn-danger btn-sm flex-fill"
                                wire:click="falsoPositivo('{{ Crypt::encrypt($el['id']) }}')"
                                wire:confirm="Tem a certeza que &quot;{{ $el['name'] }}&quot; é um falso positivo?&#10;&#10;O elemento deixa de aparecer no mapa e no catálogo."
                                wire:loading.attr="disabled" wire:target="falsoPositivo">
                                <i class="bi bi-x-octagon me-1"></i> Falso Positivo
                            </button>
                            <button type="button" class="btn btn-success btn-sm flex-fill"
                                wire:click="verificar('{{ Crypt::encrypt($el['id']) }}')"
                                wire:confirm="Tem a certeza que &quot;{{ $el['name'] }}&quot; vai ser verificado ?"
                                wire:loading.attr="disabled" wire:target="verificar">
                                <i class="bi bi-check me-1"></i>Verificar
                            </button>
                        </div>
                    @endif

                    {{-- Formulário "Mudar informações" (PATCH /elements/{id}) --}}
                    @if ($editing)
                        <form class="p-3 border-bottom bg-light" wire:submit="saveElement">
                            <div class="mb-2">
                                <label class="form-label small mb-1">Tipo</label>
                                <select class="form-select form-select-sm" wire:model.live="editForm.class">
                                    @foreach (\App\Support\Elementos::TYPES as $value => $label)
                                        <option value="{{ $value }}">{{ $label }}</option>
                                    @endforeach
                                </select>
                                @error('editForm.class') <span class="text-danger small">{{ $message }}</span> @enderror
                            </div>

                            {{-- Só o limite de velocidade tem um valor extra --}}
                            @if (($editForm['class'] ?? '') === 'sign.speed_limit')
                                <div class="mb-2">
                                    <label class="form-label small mb-1">Limite (km/h)</label>
                                    <input type="number" class="form-control form-control-sm" placeholder="ex.: 50"
                                        wire:model="editForm.limit">
                                    @error('editForm.limit') <span class="text-danger small">{{ $message }}</span> @enderror
                                </div>
                            @endif

                            <div class="row g-2 mb-3">
                                <div class="col-6">
                                    <label class="form-label small mb-1">Latitude</label>
                                    <input type="number" step="any" class="form-control form-control-sm" wire:model="editForm.latitude">
                                    @error('editForm.latitude') <span class="text-danger small">{{ $message }}</span> @enderror
                                </div>
                                <div class="col-6">
                                    <label class="form-label small mb-1">Longitude</label>
                                    <input type="number" step="any" class="form-control form-control-sm" wire:model="editForm.longitude">
                                    @error('editForm.longitude') <span class="text-danger small">{{ $message }}</span> @enderror
                                </div>
                            </div>

                            <div class="d-flex gap-2 justify-content-end">
                                <button type="button" class="btn btn-sm btn-outline-secondary" wire:click="cancelEdit">Cancelar</button>
                                <button type="submit" class="btn btn-sm btn-primary" wire:loading.attr="disabled" wire:target="saveElement">
                                    <span wire:loading.remove wire:target="saveElement">Guardar</span>
                                    <span wire:loading wire:target="saveElement">A guardar...</span>
                                </button>
                            </div>
                            <div class="form-text mt-2">Ao guardar, o elemento passa a "Corrigido" e o ML deixa de o alterar.</div>
                        </form>
                    @endif
                    {{-- Foto à esquerda, detalhes à direita (fica mais baixo) --}}
                    <div class="element-detail-content">
                    @if ($el['image_url'])
                        <x-photo-boxes class="element-detail-photo" :src="$el['image_url']" alt="Foto do elemento"
                            :boxes="! empty($el['bbox_xyxy']) ? [['bbox' => $el['bbox_xyxy'], 'label' => $el['name'], 'color' => $el['box_color'] ?? null]] : []" />
                    @endif

                    <div class="card-body">
                        <span class="badge text-bg-{{ $statusColor }} mb-3">{{ $statusText }}</span>

                        <dl class="row mb-0">
                            <dt class="col-sm-3 col-5">Confiança</dt>
                            <dd class="col-sm-3 col-7">{{ round($el['confidence'] * 100) }}%</dd>

                            <dt class="col-sm-3 col-5">Categoria</dt>
                            <dd class="col-sm-3 col-7">{{ \App\Support\Elementos::categoryLabel($el['category']) }}</dd>

                            <dt class="col-sm-3 col-5">Tipo</dt>
                            <dd class="col-sm-3 col-7">{{ \App\Support\Elementos::typeLabel($el['category'], $el['type']) }}</dd>

                            {{-- Atributos extra, ex.: limite de velocidade --}}
                            @foreach ($el['attributes'] ?? [] as $key => $value)
                                <dt class="col-sm-3 col-5">{{ \App\Support\Elementos::attributeLabel($key) }}</dt>
                                <dd class="col-sm-3 col-7">{{ \App\Support\Elementos::attributeValue($key, $value) }}</dd>
                            @endforeach

                            <dt class="col-sm-3 col-5">Localização</dt>
                            <dd class="col-sm-3 col-7">
                                <a href="https://www.openstreetmap.org/?mlat={{ $el['latitude'] }}&mlon={{ $el['longitude'] }}#map=19/{{ $el['latitude'] }}/{{ $el['longitude'] }}"
                                    target="_blank" rel="noopener noreferrer"
                                    x-data x-on:click.prevent="window.open($el.href, '_blank', 'noopener,noreferrer')">
                                    {{ number_format($el['latitude'], 6) }},
                                    {{ number_format($el['longitude'], 6) }}
                                </a>
                            </dd>

                            <dt class="col-sm-3 col-5">Deteções</dt>
                            <dd class="col-sm-3 col-7">{{ $el['observation_count'] }}
                                {{ $el['observation_count'] == 1 ? 'vez' : 'vezes' }}</dd>

                            <dt class="col-sm-3 col-5">Criado</dt>
                            <dd class="col-sm-3 col-7">
                                {{ \Carbon\Carbon::parse($el['created_at'])->format('d/m/Y H:i') }}</dd>

                            <dt class="col-sm-3 col-5">Atualizado</dt>
                            <dd class="col-sm-3 col-7">
                                {{ \Carbon\Carbon::parse($el['updated_at'])->format('d/m/Y H:i') }}</dd>
                        </dl>

                        {{-- Mapillary/KartaView são CC BY-SA: é obrigatório mostrar o crédito --}}
                        @if ($el['attribution'])
                            <p class="text-muted small mt-3 mb-0">Foto: {{ $el['attribution'] }}</p>
                        @endif
                    </div>
                    </div>
                </div>
            @else
                <p class="text-muted" wire:loading.remove wire:target="selectElement">
                    Selecione um elemento para ver mais informações.
                </p>
            @endif
        </div>
    </div>
</div>
