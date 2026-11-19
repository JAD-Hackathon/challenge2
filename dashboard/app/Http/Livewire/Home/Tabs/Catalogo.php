<?php

namespace App\Http\Livewire\Home\Tabs;

use App\Http\Controllers\API;
use App\Support\Elementos;
use Illuminate\Contracts\Encryption\DecryptException;
use Illuminate\Support\Facades\Crypt;
use Livewire\Component;

// Separador "Catálogo": lista de elementos, detalhe, edição e falso positivo
class Catalogo extends Component
{
    public $elementos = [];

    public $souMonitor = false;

    public $selectedElement;

    // Edição do elemento selecionado ("Mudar informações")
    public $editing = false;
    public $editForm = [];

    public function mount()
    {
        $elements = API::getData('elements');

        if (isset($elements['error'])) {
            session()->now('error', "Não foi possível carregar os elementos: {$elements['error']}");
            $elements = [];
        }

        $this->elementos = $elements;
    }

    public function toggleMonitor()
    {
        if ($this->souMonitor) {
            $this->souMonitor = false;
        } else {
            $this->souMonitor = true;
        }
    }

    public function selectElement($id)
    {
        // decrypt lança exceção se o valor foi alterado (não devolve false)
        try {
            $id = Crypt::decrypt($id);
        } catch (DecryptException $e) {
            session()->flash('error', 'Id inválido.');
            return;
        }

        // GET /elements/{id}
        $element = API::getData("elements/{$id}");

        if (isset($element['error'])) {
            session()->flash('error', "Não foi possível carregar o elemento: {$element['error']}");
            $this->selectedElement = null;
            return;
        }

        // Campos já prontos para mostrar
        $element['icon'] = Elementos::setIcon($element['category'], $element['type']);
        $element['image_url'] = Elementos::mediaUrl($element['image_url'] ?? null);

        $this->selectedElement = $element;
        $this->editing = false;
    }

    public function closeElement()
    {
        $this->selectedElement = null;
        $this->editing = false;
    }

    // MUDAR INFORMAÇÕES: abre o formulário com os valores atuais
    public function startEdit()
    {
        $el = $this->selectedElement;

        $this->editForm = [
            'class' => "{$el['category']}.{$el['type']}",
            'limit' => $el['attributes']['limit'] ?? null,
            'latitude' => $el['latitude'],
            'longitude' => $el['longitude'],
        ];
        $this->resetValidation();
        $this->editing = true;
    }

    public function cancelEdit()
    {
        $this->editing = false;
    }

    public function saveElement()
    {
        $this->validate([
            'editForm.class' => 'required|in:' . implode(',', array_keys(Elementos::TYPES)),
            'editForm.limit' => 'nullable|integer|min:5|max:200',
            'editForm.latitude' => 'required|numeric|between:-90,90',
            'editForm.longitude' => 'required|numeric|between:-180,180',
        ], [
            'editForm.class.in' => 'Escolha um tipo da lista.',
            'editForm.limit.integer' => 'O limite tem de ser um número inteiro.',
            'editForm.latitude.between' => 'Latitude inválida.',
            'editForm.longitude.between' => 'Longitude inválida.',
        ]);

        [$category, $type] = explode('.', $this->editForm['class']);

        // PATCH /elements/{id}: o nome é recalculado pela API a partir do tipo
        $changes = [
            'category' => $category,
            'type' => $type,
            // os atributos são substituídos; só o limite de velocidade tem atributos
            'attributes' => $type === 'speed_limit' && $this->editForm['limit']
                ? ['limit' => (int) $this->editForm['limit']]
                : (object) [],
            'latitude' => (float) $this->editForm['latitude'],
            'longitude' => (float) $this->editForm['longitude'],
        ];

        $element = API::patchData("elements/{$this->selectedElement['id']}", $changes);

        if (isset($element['error'])) {
            session()->flash('error', "Não foi possível guardar: {$element['error']}");
            return;
        }

        $element['icon'] = Elementos::setIcon($element['category'], $element['type']);
        $element['image_url'] = Elementos::mediaUrl($element['image_url'] ?? null);
        $this->selectedElement = $element;
        $this->editing = false;

        // Atualiza a lista do catálogo (o mapa recarrega da API ao abrir o separador)
        $this->elementos = array_map(
            fn ($e) => $e['id'] === $element['id'] ? $element : $e,
            $this->elementos
        );

        session()->flash('message', "\"{$element['name']}\" foi atualizado.");
    }

    // FALSO POSITIVO
    public function falsoPositivo($id)
    {
        try {
            $id = Crypt::decrypt($id);
        } catch (DecryptException $e) {
            session()->flash('error', 'Id inválido.');
            return;
        }

        $element = API::postData("elements/{$id}/false-positive");

        if (isset($element['error'])) {
            session()->flash('error', "Não foi possível marcar como falso positivo: {$element['error']}");
            return;
        }

        $this->elementos = array_values(array_filter($this->elementos, fn ($e) => $e['id'] !== $id));
        $this->selectedElement = null;

        session()->flash('message', "\"{$element['name']}\" foi marcado como falso positivo.");
    }

    public function verificar($id)
    {
        try {
            $id = Crypt::decrypt($id);
        } catch (DecryptException $e) {
            session()->flash('error', 'Id inválido.');
            return;
        }

        $element = API::postData("elements/{$id}/verify");

        if (isset($element['error'])) {
            session()->flash('error', "Não foi possível marcar como verificado: {$element['error']}");
            return;
        }

        session()->flash('message', "\"{$element['name']}\" foi marcado como Verificado.");
        $this->selectedElement = null;
    }

    public function render()
    {
        return view('livewire.home.tabs.catalogo');
    }
}
