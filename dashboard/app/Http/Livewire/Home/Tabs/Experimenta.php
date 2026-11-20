<?php

namespace App\Http\Livewire\Home\Tabs;

use App\Http\Controllers\API;
use App\Support\Elementos;
use App\Support\PhotoLocation;
use Livewire\Component;
use Livewire\WithFileUploads;

// Separador "Experimenta": envio de fotos (várias) ou de um vídeo, e modal com o resultado
class Experimenta extends Component
{
    use WithFileUploads;

    private const VIDEO_EXTENSIONS = ['mp4', 'mov'];
    private const MAX_PHOTOS = 20; // MAX_BATCH_SIZE da API

    public $files = [];
    public $track;

    public $result = null;

    public function updatedFiles()
    {
        $this->track = null;
        $this->resetErrorBag();
    }

    public function getIsVideoProperty(): bool
    {
        $first = $this->files[0] ?? null;

        return $first && in_array(self::extension($first), self::VIDEO_EXTENSIONS);
    }

    public function processFile()
    {
        $this->validate([
            'files' => 'required|array|min:1|max:' . self::MAX_PHOTOS,
            'files.*' => 'file|mimes:mp4,mov,jpg,jpeg,png|max:512000', // 500 MB
        ], [
            'files.required' => 'Selecione pelo menos um ficheiro.',
            'files.max' => 'Pode enviar no máximo ' . self::MAX_PHOTOS . ' fotos de cada vez.',
            'files.*.mimes' => 'Apenas ficheiros MP4, MOV, JPG, JPEG e PNG são permitidos.',
            'files.*.max' => 'Cada ficheiro não deve exceder 500 MB.',
        ]);

        $videos = array_filter($this->files, fn ($f) => in_array(self::extension($f), self::VIDEO_EXTENSIONS));

        if ($videos && count($this->files) > 1) {
            session()->flash('error', 'Os vídeos são enviados um de cada vez, sem fotos à mistura.');
            return;
        }

        $videos ? $this->sendVideo($this->files[0]) : $this->sendPhotos();
    }

    private function sendVideo($video): void
    {
        $response = API::sendFiles('videos', ['video' => $video, 'track' => $this->track]);

        if (! $response['ok']) {
            $this->flashApiError('o vídeo', $response);
            return;
        }

        // Só mostra os frames onde foi encontrado alguma coisa
        $this->showResult($response['data'], fn ($i) => 'Frame ' . ($i + 1), onlyWithDetections: true);

        $this->files = [];
        $this->track = null;
    }

    private function sendPhotos(): void
    {
        $photos = [];
        $metas = [];
        $skipped = [];

        // Fotos e metas são montados no mesmo ciclo: a API emparelha-os pela ordem
        foreach ($this->files as $photo) {
            $name = $photo->getClientOriginalName();
            $loc = PhotoLocation::resolve($photo->getRealPath(), $name);
            logger()->info('Experimenta: localização da foto', ['file' => $name] + $loc);

            // Sem localização (nem no EXIF, nem no Mapillary): fica de fora
            if ($loc['lat'] === null || $loc['lon'] === null || $loc['heading'] === null) {
                $skipped[] = $name;
                continue;
            }

            $photos[] = $photo;
            $metas[] = [
                'lat' => (float) $loc['lat'],
                'lon' => (float) $loc['lon'],
                'heading' => fmod((float) $loc['heading'], 360),
            ];
        }

        if (! $photos) {
            session()->flash('error', 'Nenhuma foto tem localização (EXIF ou Mapillary): ' . implode(', ', $skipped));
            return;
        }

        $response = API::sendFiles('images', ['images' => $photos], ['metas' => json_encode($metas)]);

        if (! $response['ok']) {
            $this->flashApiError(count($photos) > 1 ? 'as imagens' : 'a imagem', $response);
            return;
        }

        $this->showResult($response['data'], fn ($i) => $photos[$i]->getClientOriginalName(), skipped: $skipped);

        $this->files = [];
    }

    // Monta $result: uma entrada por imagem (ou frame), cada uma com a foto desfocada, as caixas e os seus elementos
    private function showResult(array $data, callable $nameFor, array $skipped = [], bool $onlyWithDetections = false): void
    {
        $elements = collect($data['elements'] ?? [])->keyBy('id');
        $photos = [];

        foreach ($data['images'] ?? [] as $i => $image) {
            $photo = [
                'name' => $nameFor($i),
                'status' => $image['status'] ?? 'failed', // processed | duplicate | failed
                'error' => $image['error'] ?? null,
                'elements' => [],
                'image_url' => null,
                'boxes' => [],
            ];

            if ($photo['status'] !== 'failed' && ! empty($image['image_id'])) {
                // Imagem desfocada + deteções (bbox_xyxy em píxeis dessa imagem, desenhadas com <x-photo-boxes>)
                $detail = API::getData('images/' . $image['image_id']);

                if (is_array($detail) && ! isset($detail['error'])) {
                    $observations = $detail['observations'] ?? [];

                    $photo['image_url'] = Elementos::mediaUrl($detail['image_url'] ?? null);
                    $photo['boxes'] = array_map(fn ($obs) => [
                        'bbox' => $obs['bbox_xyxy'],
                        'label' => ($elements[$obs['element_id'] ?? '']['name'] ?? Elementos::typeLabel($obs['type'])) . ' · ' . round($obs['score'] * 100) . '%',
                        'color' => Elementos::boxColor(explode('.', $obs['type'])[0]),
                    ], $observations);

                    // Elementos desta imagem = os que têm uma observação nela
                    $photo['elements'] = collect($observations)
                        ->pluck('element_id')->filter()->unique()
                        ->map(fn ($id) => $elements[$id] ?? null)->filter()
                        ->map(fn ($element) => [
                            'name' => $element['name'],
                            'confidence' => round(($element['confidence'] ?? 0) * 100), // 0.87 -> 87
                            'icon' => Elementos::setIcon($element['category'], $element['type']),
                        ])->values()->all();
                }
            }

            if ($onlyWithDetections && $photo['status'] !== 'failed' && ! $photo['boxes']) {
                continue;
            }

            $photos[] = $photo;
        }

        $this->result = [
            'photos' => $photos,
            'skipped' => $skipped,
            'total' => $elements->count(),
        ];
    }

    private function flashApiError(string $what, array $response): void
    {
        $detail = $response['data']['detail'] ?? 'erro desconhecido';
        session()->flash('error', "Erro ao enviar {$what} ({$response['status']}): " . (is_string($detail) ? $detail : json_encode($detail)));
    }

    private static function extension($file): string
    {
        return strtolower($file->getClientOriginalExtension());
    }

    public function closeResult()
    {
        $this->result = null;
    }

    public function render()
    {
        return view('livewire.home.tabs.experimenta');
    }
}
