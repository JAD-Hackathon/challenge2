<?php

use App\Http\Livewire\Home\Home;
use Illuminate\Support\Facades\Route;

Route::get('/', Home::class)->name('home');
