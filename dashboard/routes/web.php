<?php

use App\Http\Controllers\MapillaryDownload;
use App\Http\Livewire\Home\Home;
use Illuminate\Support\Facades\Route;

Route::get('/', Home::class)->name('home');

Route::get('/dev/mapillary', MapillaryDownload::class)->name('dev.mapillary');
