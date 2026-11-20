<?php

namespace App\Http\Livewire\Home;

use Illuminate\Support\Facades\RateLimiter;
use Illuminate\Support\Str;
use Livewire\Component;

// Página principal: cabeçalho + navegação entre separadores + modal de login.
// Cada separador é um componente em Tabs/ (Mapa, Experimenta, Catalogo).
class Home extends Component
{
    public $aba = '1';

    // Modal de login
    public $showLogin = false;
    public $email = '';
    public $password = '';

    public function mount()
    {
        $this->aba = request()->query('aba', '1');
    }

    public function changeAba($aba)
    {
        $this->aba = $aba;
    }

    public function openLogin()
    {
        $this->resetErrorBag();
        $this->showLogin = true;
    }

    public function closeLogin()
    {
        $this->reset('showLogin', 'password');
        $this->resetErrorBag();
    }

    public function login()
    {
        $this->validate([
            'email' => 'required|email',
            'password' => 'required',
        ], [
            'email.required' => 'Indique o email.',
            'email.email' => 'Email inválido.',
            'password.required' => 'Indique a palavra-passe.',
        ]);

        // Máximo 5 tentativas por minuto por email + IP
        $key = 'login:' . Str::lower($this->email) . '|' . request()->ip();
        if (RateLimiter::tooManyAttempts($key, 5)) {
            $this->addError('email', 'Demasiadas tentativas. Tente novamente em ' . RateLimiter::availableIn($key) . ' s.');
            return;
        }

        // Contas definidas em config/logins.php
        $account = collect(config('logins', []))->first(
            fn ($login) => Str::lower($login['user']) === Str::lower($this->email)
                && hash_equals((string) $login['password'], (string) $this->password)
        );

        if (! $account) {
            RateLimiter::hit($key);
            $this->addError('email', 'Email ou palavra-passe incorretos.');
            $this->password = '';
            return;
        }

        RateLimiter::clear($key);

        // Sessão sem base de dados: guarda só a conta do config/logins.php
        // Nas views: @if (session('login')) ... {{ session('login.user') }} / session('login.type')
        session()->regenerate();
        session(['login' => [
            'user' => Str::lower($account['user']),
            'type' => $account['type'] ?? null,
        ]]);

        // Recarrega a página para todos os separadores verem o utilizador autenticado
        return $this->redirect(route('home', ['aba' => $this->aba]));
    }

    public function logout()
    {
        session()->invalidate();
        session()->regenerateToken();

        return $this->redirect(route('home', ['aba' => $this->aba]));
    }

    public function render()
    {
        return view('livewire.home.home')->extends('layouts.app');
    }
}
