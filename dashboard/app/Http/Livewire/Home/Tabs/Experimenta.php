<?php

namespace App\Http\Livewire\Home\Tabs;

use App\Http\Controllers\API;
use App\Http\Controllers\Controller;
use App\Support\Elementos;
use Livewire\Component;
use Livewire\WithFileUploads;

// Separador "Experimenta": envio de foto/vídeo e modal com o resultado
class Experimenta extends Component
{
    use WithFileUploads;

    public $file;

    // Localização da foto (lida do EXIF)
    public $lat;
    public $lon;
    public $heading = 0;

    // Resultado do último envio, mostrado no modal (null = modal fechado)
    public $result = null;

    public function updatedFile()
    {
        $this->lat = $this->lon = null;
        $this->heading = 0;

        $extension = strtolower($this->file?->getClientOriginalExtension() ?? '');
        if (! in_array($extension, ['jpg', 'jpeg'])) {
            return; // PNG não tem EXIF
        }

        $exif = @exif_read_data($this->file->getRealPath());

        if (! empty($exif['GPSLatitude']) && ! empty($exif['GPSLongitude'])) {
            $this->lat = round(Controller::gpsToDecimal($exif['GPSLatitude'], $exif['GPSLatitudeRef'] ?? 'N'), 6);
            $this->lon = round(Controller::gpsToDecimal($exif['GPSLongitude'], $exif['GPSLongitudeRef'] ?? 'E'), 6);
        }

        if (isset($exif['GPSImgDirection'])) {
            $this->heading = round(fmod(Controller::exifFraction($exif['GPSImgDirection']), 360), 1);
        }
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

        $extension = $this->file->getClientOriginalExtension();

        if (in_array($extension, ['mp4', 'mov'])) {
            $video = API::getData('videos', [
                'file' => $this->file,
                'track' => $this->file->getClientOriginalName(),
            ]);
        } elseif (in_array($extension, ['jpg', 'jpeg', 'png'])) {
            $exif = @exif_read_data($this->file->getRealPath());

            if ($exif === false) {
                session()->flash('error', 'Não foi possível ler os metadados da imagem.');
                return;
            }

            if (! isset($exif['GPSLatitude'], $exif['GPSLatitudeRef'], $exif['GPSLongitude'], $exif['GPSLongitudeRef'])) {
                session()->flash('error', 'A imagem não tem localização GPS. Use uma foto tirada com a localização ativada.');
                return;
            }

            if (! isset($exif['GPSImgDirection'])) {
                session()->flash('error', 'A imagem não tem a direção da câmara (GPSImgDirection).');
                return;
            }

            // LATITUDE
            $latitude = Controller::gpsToDecimal($exif['GPSLatitude'], $exif['GPSLatitudeRef']);

            // LONGITUDE
            $longitude = Controller::gpsToDecimal($exif['GPSLongitude'], $exif['GPSLongitudeRef']);

            // HEADING (0–360, "360" passa a 0)
            $heading = fmod(Controller::exifFraction($exif['GPSImgDirection']), 360);

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
        ];
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
