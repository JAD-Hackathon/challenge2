{{-- Mensagens de erro/sucesso (session()->flash / now) --}}
@if (session('error'))
    <div class="alert alert-danger">{{ session('error') }}</div>
@endif
@if (session('message'))
    <div class="alert alert-success">{{ session('message') }}</div>
@endif
