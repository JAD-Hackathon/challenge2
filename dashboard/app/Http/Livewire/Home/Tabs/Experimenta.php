<?php

namespace App\Http\Livewire\Home\Tabs;

use App\Http\Controllers\API;
use App\Support\Elementos;
use App\Support\PhotoLocation;
use Livewire\Component;
use Livewire\WithFileUploads;

// Separador "Experimenta": envio de foto/vídeo e modal com o resultado
class Experimenta extends Component
{
    use WithFileUploads;

    public $file;

    // Localização da foto: lida automaticamente (EXIF, Mapillary)
    public $lat;
    public $lon;
    public $heading;

    // Resultado do último envio, mostrado no modal (null = modal fechado)
    public $result = null;

    public function updatedFile()
    {
        $this->lat = $this->lon = $this->heading = null;
        $this->readLocation();
    }

    // Lê lat/lon/heading da foto (EXIF, depois Mapillary pelo nome do ficheiro)
    private function readLocation(): void
    {
        $extension = strtolower($this->file?->getClientOriginalExtension() ?? '');
        if (! in_array($extension, ['jpg', 'jpeg', 'png'])) {
            return; // vídeos: a localização vem do próprio ficheiro, no backend
        }

        $found = PhotoLocation::resolve($this->file->getRealPath(), $this->file->getClientOriginalName());
        logger()->info('Experimenta: localização da foto', ['file' => $this->file->getClientOriginalName()] + $found);

        $this->lat = $found['lat'];
        $this->lon = $found['lon'];
        $this->heading = $found['heading'];
    }

    public function processFile()
    {
        $this->validate([
            'file' => 'required|file|mimes:mp4,mov,jpg,jpeg,png|max:5120', // 5MB Max (extensões sem ponto)
        ],
        [
            'file.required' => 'Selecione um arquivo para upload.',
            'file.mimes' => 'Apenas arquivos MP4, JPG, PNG e JPEG são permitidos.',
            'file.max' => 'O tamanho do arquivo não deve exceder 5MB.',
        ]);

        $extension = strtolower($this->file->getClientOriginalExtension());

        if (in_array($extension, ['mp4', 'mov'])) {
            $video = API::getData('videos', [
                'file' => $this->file,
                'track' => $this->file->getClientOriginalName(),
            ]);
        } elseif (in_array($extension, ['jpg', 'jpeg', 'png'])) {
            // Volta a ler do ficheiro se os valores não ficaram guardados desde o upload
            if ($this->lat === null || $this->lon === null || $this->heading === null) {
                $this->readLocation();
            }

            // Sem localização (nem no EXIF, nem no Mapillary): não envia
            if ($this->lat === null || $this->lon === null || $this->heading === null) {
                return;
            }

            $latitude = (float) $this->lat;
            $longitude = (float) $this->lon;
            $heading = fmod((float) $this->heading, 360); // "360" passa a 0

            $imagem = API::sendFiles('images', ['images' => $this->file], [
                'metas' => json_encode([[
                    'lat' => $latitude,
                    'lon' => $longitude,
                    'heading' => $heading,
                ]]),
            ]);

            if (! $imagem['ok']) {
                $detail = $imagem['data']['detail'] ?? 'erro desconhecido';
                session()->flash('error', "Erro ao enviar a imagem ({$imagem['status']}): " . (is_string($detail) ? $detail : json_encode($detail)));
                return;
            }

            $this->showResult($imagem['data']);

            $this->file = null;
            $this->lat = $this->lon = $this->heading = null;
        } else {
            session()->flash('error', 'Tipo de arquivo não suportado.');
            return;
        }
    }

    private function showResult(array $data)
    {
        $image = $data['images'][0] ?? [];

        $this->result = [
            'status' => $image['status'] ?? 'failed', // processed | duplicate | failed
            'error' => $image['error'] ?? null,
            'elements' => array_map(fn ($element) => [
                'name' => $element['name'],
                'confidence' => round(($element['confidence'] ?? 0) * 100), // 0.87 -> 87
                'icon' => Elementos::setIcon($element['category'], $element['type']),
            ], $data['elements'] ?? []),
            'image_url' => null,
            'boxes' => [],
        ];

        if (($image['status'] ?? null) === 'failed' || empty($image['image_id'])) {
            return;
        }

        // Imagem desfocada + deteções (bbox_xyxy em píxeis dessa imagem, desenhadas com <x-photo-boxes>)
        $detail = API::getData('images/' . $image['image_id']);
        if (isset($detail['error'])) {
            return;
        }

        $names = collect($data['elements'] ?? [])->pluck('name', 'id');

        $this->result['image_url'] = Elementos::mediaUrl($detail['image_url'] ?? null);
        $this->result['boxes'] = array_map(fn ($obs) => [
            'bbox' => $obs['bbox_xyxy'],
            'label' => ($names[$obs['element_id'] ?? ''] ?? Elementos::typeLabel($obs['type'])) . ' · ' . round($obs['score'] * 100) . '%',
            'color' => Elementos::boxColor(explode('.', $obs['type'])[0]),
        ], $detail['observations'] ?? []);
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
