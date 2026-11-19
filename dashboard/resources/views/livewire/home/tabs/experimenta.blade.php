<div>
    @include('livewire.home.partials.alerts')

    <h1>Aqui podes colocar uma foto/video e o vamos-te dizer onde é e o que aparece!</h1>

    <form>
        <div class="row">
            <div class="col-4">
                <label for="fileInput" class="form-label">Escolha um ficheiro (imagem ou vídeo):</label>
                <input class="form-control" type="file" id="fileInput" wire:model="file"
                    mimes="jpg,jpeg,png,mp4">
                @error('file')
                    <span class="text-danger">{{ $message }}</span>
                @enderror
                <button type="button" class="btn btn-primary mt-4" wire:click="processFile">Enviar</button>

            </div>
        </div>
    </form>

    {{-- MODAL: resultado do envio da imagem (aberto quando $result tem dados) --}}
    @if ($result)
        <div class="modal fade show d-block" tabindex="-1" role="dialog" aria-modal="true"
            wire:keydown.escape.window="closeResult">
            <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            @if ($result['status'] === 'failed')
                                Não foi possível processar a imagem
                            @elseif (count($result['elements']))
                                {{ count($result['elements']) }} elemento(s) encontrado(s)
                            @else
                                Nenhum elemento encontrado
                            @endif
                        </h5>
                        <button type="button" class="btn-close" aria-label="Fechar"
                            wire:click="closeResult"></button>
                    </div>

                    <div class="modal-body">
                        @if ($result['status'] === 'failed')
                            <div class="alert alert-danger mb-0">{{ $result['error'] ?? 'Erro desconhecido.' }}</div>
                        @else
                            @if ($result['status'] === 'duplicate')
                                <div class="alert alert-info">Esta imagem já tinha sido enviada antes.</div>
                            @endif

                            @if (count($result['elements']))
                                <ul class="list-group">
                                    @foreach ($result['elements'] as $element)
                                        <li class="list-group-item d-flex align-items-center gap-3">
                                            @if ($element['icon'])
                                                <img src="{{ $element['icon'] }}" alt=""
                                                    class="legend-icon">
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

                    <div class="modal-footer">
                        <button type="button" class="btn btn-primary" wire:click="closeResult">Fechar</button>
                    </div>
                </div>
            </div>
        </div>
        <div class="modal-backdrop fade show" wire:click="closeResult"></div>
    @endif
</div>
