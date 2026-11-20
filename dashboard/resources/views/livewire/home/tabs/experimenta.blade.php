<div>

    @include('livewire.home.partials.alerts')

    <h1>Aqui podes colocar uma foto/video e o vamos-te dizer onde é e o que aparece!</h1>

    <form>
        <div class="row">
            <div class="col-4">
                <label for="fileInput" class="form-label">Escolha fotos (até 20) ou um vídeo:</label>
                <input class="form-control" type="file" id="fileInput" wire:model.live="files" multiple
                    accept=".jpg,.jpeg,.png,.mp4,.mov">
                @error('files')
                    <span class="text-danger">{{ $message }}</span>
                @enderror
                @error('files.*')
                    <span class="text-danger">{{ $message }}</span>
                @enderror

                <div wire:loading wire:target="files" class="text-muted small mt-1">A carregar…</div>

                @if ($this->isVideo)
                    <label for="trackInput" class="form-label mt-3">Ficheiro GPX do vídeo:</label>
                    <input class="form-control" type="file" id="trackInput" wire:model="track" accept=".gpx">
                    @error('track')
                        <span class="text-danger">{{ $message }}</span>
                    @enderror
                @elseif (count($files) > 1)
                    <div class="text-muted small mt-1">{{ count($files) }} fotos selecionadas</div>
                @endif

                <button type="button" class="btn btn-primary mt-4" wire:click="processFile"
                    wire:loading.attr="disabled" wire:target="files,processFile">Enviar</button>

            </div>
        </div>
    </form>

    {{-- LOADING: ecrã desfocado enquanto a foto/vídeo é processada --}}
    <div wire:loading.flex wire:target="processFile" class="processing-overlay" role="status" aria-live="polite">
        <div class="processing-box">
            <div class="spinner-border text-primary mb-3" aria-hidden="true"></div>
            <h5 class="mb-1">A processar…</h5>
            <p class="text-muted mb-0">Estamos a analisar os teus ficheiros. Isto pode demorar alguns segundos,
                aguarda por favor.</p>
        </div>
    </div>

    {{-- MODAL: resultado do envio da imagem (aberto quando $result tem dados) --}}
    @if ($result)
        <div class="modal fade show d-block" tabindex="-1" role="dialog" aria-modal="true"
            wire:keydown.escape.window="closeResult">
            <div class="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            @if ($result['total'])
                                {{ $result['total'] }} elemento(s) encontrado(s)
                            @else
                                Nenhum elemento encontrado
                            @endif
                            @if (count($result['photos']) > 1)
                                <small class="text-muted">em {{ count($result['photos']) }} imagens</small>
                            @endif
                        </h5>
                        <button type="button" class="btn-close" aria-label="Fechar" wire:click="closeResult"></button>
                    </div>

                    <div class="modal-body">
                        @if (count($result['skipped']))
                            <div class="alert alert-warning">
                                Sem localização (EXIF ou Mapillary), não enviadas:
                                {{ implode(', ', $result['skipped']) }}
                            </div>
                        @endif

                        @forelse ($result['photos'] as $photo)
                            <div class="@if (! $loop->last) border-bottom pb-3 mb-3 @endif">
                                @if (count($result['photos']) > 1)
                                    <h6 class="mb-2">{{ $photo['name'] }}</h6>
                                @endif

                                @if ($photo['status'] === 'failed')
                                    <div class="alert alert-danger mb-0">
                                        Não foi possível processar: {{ $photo['error'] ?? 'erro desconhecido.' }}
                                    </div>
                                @else
                                    @if ($photo['status'] === 'duplicate')
                                        <div class="alert alert-info">Esta imagem já tinha sido enviada antes.</div>
                                    @endif

                                    {{-- Foto desfocada com as deteções --}}
                                    @if ($photo['image_url'])
                                        <x-photo-boxes class="mb-3" :src="$photo['image_url']" :boxes="$photo['boxes']"
                                            :alt="$photo['name']" />
                                    @endif

                                    @if (count($photo['elements']))
                                        <ul class="list-group">
                                            @foreach ($photo['elements'] as $element)
                                                <li class="list-group-item d-flex align-items-center gap-3">
                                                    @if ($element['icon'])
                                                        <img src="{{ $element['icon'] }}" alt="" class="legend-icon">
                                                    @endif
                                                    <span class="flex-grow-1">{{ $element['name'] }}</span>
                                                    <span class="badge text-bg-light">{{ $element['confidence'] }}%
                                                        confiança</span>
                                                </li>
                                            @endforeach
                                        </ul>
                                    @else
                                        <p class="text-muted mb-0">
                                            Não detetámos sinais, iluminação nem contentores nesta imagem.
                                        </p>
                                    @endif
                                @endif
                            </div>
                        @empty
                            <p class="text-muted mb-0">
                                Não detetámos sinais, iluminação nem contentores neste vídeo.
                            </p>
                        @endforelse
                    </div>

                    <div class="modal-footer">
                        <button type="button" class="btn btn-primary" wire:click="closeResult">Fechar</button>
                    </div>
                </div>
            </div>
        </div>
        <div class="modal-backdrop fade show" wire:click="closeResult"></div>
    @endif
</div>
