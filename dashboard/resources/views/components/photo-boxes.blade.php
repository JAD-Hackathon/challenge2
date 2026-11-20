{{--
    Foto com bounding boxes por cima.
    boxes: [['bbox' => [x1, y1, x2, y2] (píxeis da imagem), 'label' => '...', 'color' => '#hex'], ...]
    As dimensões reais da imagem só se sabem no browser (naturalWidth/Height): as caixas
    são posicionadas em % quando a imagem carrega, por isso acompanham qualquer tamanho.
--}}
@props(['src', 'boxes' => [], 'alt' => 'Foto'])

<div {{ $attributes->merge(['class' => 'position-relative']) }}
    x-data="{ w: 0, h: 0, size(img) { this.w = img.naturalWidth; this.h = img.naturalHeight } }"
    {{-- Clicar na foto: abre em grande com as bounding boxes --}}
    x-on:click="window.openPhotoLightbox?.(@js($src), @js($boxes))"
    style="cursor: zoom-in;" title="Clique para ver em grande">
    <img src="{{ $src }}" alt="{{ $alt }}" class="d-block w-100 h-auto rounded"
        x-on:load="size($el)" x-init="$el.complete && size($el)">

    @foreach ($boxes as $box)
        @php([$x1, $y1, $x2, $y2] = $box['bbox'])
        <div class="position-absolute pe-none" x-show="w" x-cloak
            x-bind:style="{ left: {{ $x1 }} / w * 100 + '%', top: {{ $y1 }} / h * 100 + '%', width: {{ $x2 - $x1 }} / w * 100 + '%', height: {{ $y2 - $y1 }} / h * 100 + '%' }"
            style="border: 2px solid {{ $box['color'] ?? '#0d6efd' }};">
            @if (! empty($box['label']))
                <span class="position-absolute bottom-100 start-0 px-1 text-white text-nowrap"
                    style="background: {{ $box['color'] ?? '#0d6efd' }}; font-size: .7rem;">{{ $box['label'] }}</span>
            @endif
        </div>
    @endforeach
</div>
